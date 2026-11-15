import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles, MapPin, CalendarRange, Users, Wallet, Home, Lightbulb,
  BedDouble, BusFront, Gauge, Utensils, Accessibility, MessageSquare, ArrowRight,
  Loader2, Search,
} from 'lucide-react';
import { destinationsAPI, itinerariesAPI, usersAPI } from '../lib/api';
import { useDebounce } from '../hooks/useDebounce';
import { useToast } from '../context/ToastContext';
import { PageTransition } from '../components/ui/Reveal';
import AIThinking from '../components/ui/AIThinking';
import { Input, Select, Textarea } from '../components/ui/Form';
import {
  ACCOMMODATION_OPTIONS, TRANSPORTATION_OPTIONS, PACE_OPTIONS, INTEREST_OPTIONS,
  ACTIVITY_OPTIONS, DIETARY_OPTIONS, CURRENCIES, DEFAULT_CURRENCY,
  MAX_TRIP_DAYS, MAX_TRAVELLERS,
} from '../lib/constants';
import { todayISO, tripDays } from '../lib/format';

function ChipGroup({ options, selected, onToggle, max, label }) {
  return (
    <div>
      <p className="label">{label}</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
        {options.map((o) => {
          const on = selected.includes(o);
          return (
            <button
              key={o}
              type="button"
              onClick={() => onToggle(o)}
              className={`chip ${on ? 'chip-on' : 'chip-off'}`}
              aria-pressed={on}
              disabled={!on && selected.length >= max}
            >
              {o.replace(/_/g, ' ')}
            </button>
          );
        })}
      </div>
      <p className="hint">{selected.length}/{max ?? 20} selected</p>
    </div>
  );
}

export default function Planner() {
  const toast = useToast();
  const navigate = useNavigate();

  // Form state — mirrors GenerateItineraryRequest exactly.
  const [form, setForm] = useState({
    destination: '',
    destination_place_id: null,
    start_date: '',
    end_date: '',
    travellers: 2,
    total_budget: '',
    currency: DEFAULT_CURRENCY,
    origin: '',
    pace: 'balanced',
    accommodation_preference: 'midrange_hotel',
    transportation_preference: 'mixed',
    accessibility_needs: '',
    additional_notes: '',
    include_routes: true,
  });
  const [interests, setInterests] = useState(['history', 'food']);
  const [activities, setActivities] = useState([]);
  const [dietary, setDietary] = useState([]);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  // Apply the traveler's saved preferences as planner defaults. A 404 simply
  // means they haven't saved any preferences yet — keep the built-in defaults.
  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    usersAPI
      .preferences(ctrl.signal)
      .then((p) => {
        if (!alive) return;
        setForm((f) => ({
          ...f,
          currency: p.currency || f.currency,
          origin: p.home_city || f.origin,
          accommodation_preference: p.accommodation_preference || f.accommodation_preference,
          transportation_preference: p.transportation_preference || f.transportation_preference,
          accessibility_needs: p.accessibility_needs || f.accessibility_needs,
        }));
        if (p.interests?.length) setInterests(p.interests);
        if (p.activity_preferences?.length) setActivities(p.activity_preferences);
        if (p.dietary_preferences?.length) setDietary(p.dietary_preferences);
      })
      .catch(() => {
        /* 404 or unavailable — built-in defaults remain */
      });
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, []);

  // Destination suggestions (real Google Places through the backend).
  const [suggestions, setSuggestions] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const debouncedDest = useDebounce(form.destination, 450);
  const abortRef = useRef(null);
  const justPicked = useRef(false);

  useEffect(() => {
    const q = debouncedDest.trim();
    if (justPicked.current) {
      justPicked.current = false;
      return undefined;
    }
    if (q.length < 2) {
      setSuggestions(null);
      return undefined;
    }
    setSuggesting(true);
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    destinationsAPI
      .search(q, 5, ctrl.signal)
      .then((d) => {
        if (ctrl.signal.aborted) return;
        setSuggestions(d.items || []);
        setSuggesting(false);
      })
      .catch(() => {
        if (!ctrl.signal.aborted) {
          setSuggestions(null);
          setSuggesting(false);
        }
      });
    return () => ctrl.abort();
  }, [debouncedDest]);

  const set = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
    if (key === 'destination') {
      setForm((f) => ({ ...f, destination: value, destination_place_id: null }));
    }
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const pickSuggestion = (p) => {
    justPicked.current = true;
    setForm((f) => ({ ...f, destination: p.name, destination_place_id: p.place_id }));
    setSuggestions(null);
  };

  const validate = () => {
    const errs = {};
    if (!form.destination.trim() || form.destination.trim().length < 2) errs.destination = 'Where are you going? Enter a destination.';
    if (!form.start_date) errs.start_date = 'Pick a departure date.';
    else if (form.start_date < todayISO()) errs.start_date = 'Departure can\u2019t be in the past.';
    if (!form.end_date) errs.end_date = 'Pick a return date.';
    else if (form.end_date < form.start_date) errs.end_date = 'Return must be on or after departure.';
    else if (tripDays(form.start_date, form.end_date) > MAX_TRIP_DAYS) {
      errs.end_date = `Trips longer than ${MAX_TRIP_DAYS} days aren't supported.`;
    }
    if (!form.travellers || form.travellers < 1 || form.travellers > MAX_TRAVELLERS) {
      errs.travellers = `Travellers must be between 1 and ${MAX_TRAVELLERS}.`;
    }
    if (!form.total_budget || Number(form.total_budget) <= 0) errs.total_budget = 'Enter a total budget above zero.';
    else if (Number(form.total_budget) > 1_000_000_000_000) errs.total_budget = 'That budget is beyond the supported range.';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return; // duplicate submission guard
    if (!validate()) {
      toast.error('Almost there', 'Please fix the highlighted fields.');
      return;
    }
    setSubmitting(true);
    const payload = {
      destination: form.destination.trim(),
      destination_place_id: form.destination_place_id || undefined,
      start_date: form.start_date,
      end_date: form.end_date,
      travellers: Number(form.travellers),
      total_budget: Number(form.total_budget),
      currency: form.currency,
      interests,
      activities,
      accommodation_preference: form.accommodation_preference,
      transportation_preference: form.transportation_preference,
      pace: form.pace,
      origin: form.origin.trim() || undefined,
      dietary_preferences: dietary,
      accessibility_needs: form.accessibility_needs.trim() || undefined,
      additional_notes: form.additional_notes.trim() || undefined,
      include_routes: form.include_routes,
    };
    try {
      const itinerary = await itinerariesAPI.generate(payload);
      toast.success('Itinerary ready!', 'Your day-by-day plan has been generated.');
      navigate(`/itineraries/${itinerary.id}`, { replace: true, state: { fresh: true } });
    } catch (err) {
      setSubmitting(false);
      toast.error('Generation failed', err.message || 'The AI planner could not complete this trip. Try again or adjust the dates.');
    }
  };

  if (submitting) {
    return (
      <PageTransition>
        <div className="flex min-h-[70vh] items-center justify-center px-4">
          <div>
            <AIThinking destination={`${form.destination.trim()} itinerary`} />
            <p className="mx-auto mt-6 max-w-sm text-center text-xs text-slate-400">
              Real Google Places data is being fetched, validated and ordered — this usually takes 20–60 seconds. Please keep this tab open.
            </p>
          </div>
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 text-center">
          <p className="mb-2 flex items-center justify-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-ocean-600">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> AI trip planner
          </p>
          <h1 className="font-display text-3xl font-extrabold sm:text-4xl">Plan your next journey</h1>
          <p className="mx-auto mt-2 max-w-xl text-sm text-slate-600">
            Every field below maps to the real planning engine. The more you share, the sharper the itinerary.
          </p>
        </header>

        <form onSubmit={submit} className="space-y-8" noValidate>
          {/* The trip ------------------------------------------------------ */}
          <section className="card p-6" aria-labelledby="s-essentials">
            <h2 id="s-essentials" className="mb-5 flex items-center gap-2 font-display text-lg font-bold">
              <MapPin className="h-5 w-5 text-ocean-600" aria-hidden="true" /> The essentials
            </h2>
            <div className="space-y-4">
              {/* Destination with suggestions */}
              <div className="relative">
                <Input
                  label="Destination"
                  placeholder="e.g. Kyoto, Japan"
                  icon={MapPin}
                  value={form.destination}
                  onChange={set('destination')}
                  error={errors.destination}
                  autoComplete="off"
                  required
                />
                {suggesting ? (
                  <span className="absolute right-3 top-[2.4rem] text-slate-400">
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  </span>
                ) : null}
                {suggestions?.length ? (
                  <ul className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lift" role="listbox" aria-label="Destination suggestions">
                    {suggestions.map((s) => (
                      <li key={s.place_id} role="option" aria-selected={false}>
                        <button
                          type="button"
                          onClick={() => pickSuggestion(s)}
                          className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm hover:bg-ocean-50"
                        >
                          <Search className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
                          <span className="min-w-0">
                            <span className="block truncate font-semibold text-navy-950">{s.name}</span>
                            <span className="block truncate text-xs text-slate-500">{s.formatted_address}</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p className="hint">Pick a suggestion so the planner can resolve the exact place.</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="Departure date"
                  type="date"
                  icon={CalendarRange}
                  min={todayISO()}
                  value={form.start_date}
                  onChange={set('start_date')}
                  error={errors.start_date}
                  required
                />
                <Input
                  label="Return date"
                  type="date"
                  icon={CalendarRange}
                  min={form.start_date || todayISO()}
                  value={form.end_date}
                  onChange={set('end_date')}
                  error={errors.end_date}
                  hint={form.start_date && form.end_date && !errors.end_date ? `${tripDays(form.start_date, form.end_date)} days` : undefined}
                  required
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <Input
                  label="Travellers"
                  type="number"
                  icon={Users}
                  min="1"
                  max={String(MAX_TRAVELLERS)}
                  step="1"
                  value={form.travellers}
                  onChange={set('travellers')}
                  error={errors.travellers}
                  required
                />
                <Input
                  label="Total budget"
                  type="number"
                  icon={Wallet}
                  min="1"
                  step="1"
                  placeholder="2500"
                  value={form.total_budget}
                  onChange={set('total_budget')}
                  error={errors.total_budget}
                  required
                />
                <Select label="Currency" options={CURRENCIES} value={form.currency} onChange={set('currency')} />
              </div>

              <Input
                label="Starting from (optional)"
                placeholder="e.g. London"
                icon={Home}
                maxLength={160}
                value={form.origin}
                onChange={set('origin')}
                hint="Used to estimate transport to your destination."
              />
            </div>
          </section>

          {/* Style ---------------------------------------------------------- */}
          <section className="card p-6" aria-labelledby="s-style">
            <h2 id="s-style" className="mb-5 flex items-center gap-2 font-display text-lg font-bold">
              <Gauge className="h-5 w-5 text-ocean-600" aria-hidden="true" /> Your travel style
            </h2>
            <div className="space-y-4">
              <Select
                label="Pace"
                icon={Gauge}
                options={PACE_OPTIONS}
                value={form.pace}
                onChange={set('pace')}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <Select
                  label="Accommodation preference"
                  icon={BedDouble}
                  options={ACCOMMODATION_OPTIONS}
                  value={form.accommodation_preference}
                  onChange={set('accommodation_preference')}
                />
                <Select
                  label="Transportation preference"
                  icon={BusFront}
                  options={TRANSPORTATION_OPTIONS}
                  value={form.transportation_preference}
                  onChange={set('transportation_preference')}
                />
              </div>
              <ChipGroup label="Interests" options={INTEREST_OPTIONS} selected={interests} onToggle={(o) => setInterests((prev) => (prev.includes(o) ? prev.filter((x) => x !== o) : [...prev, o]))} />
              <ChipGroup label="Specific activities" options={ACTIVITY_OPTIONS} selected={activities} onToggle={(o) => setActivities((prev) => (prev.includes(o) ? prev.filter((x) => x !== o) : [...prev, o]))} />
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 p-3.5">
                <input
                  type="checkbox"
                  checked={form.include_routes}
                  onChange={set('include_routes')}
                  className="h-4 w-4 rounded border-slate-300 text-ocean-600 focus:ring-ocean-500"
                />
                <span className="text-sm">
                  <span className="font-semibold text-navy-950">Include routes between stops</span>
                  <span className="block text-xs text-slate-500">Adds walking / transit legs with real distances and durations.</span>
                </span>
              </label>
            </div>
          </section>

          {/* Requirements ---------------------------------------------------- */}
          <section className="card p-6" aria-labelledby="s-requirements">
            <h2 id="s-requirements" className="mb-5 flex items-center gap-2 font-display text-lg font-bold">
              <Lightbulb className="h-5 w-5 text-ocean-600" aria-hidden="true" /> Requirements (optional)
            </h2>
            <div className="space-y-4">
              <ChipGroup label="Dietary preferences" options={DIETARY_OPTIONS} selected={dietary} onToggle={(o) => setDietary((prev) => (prev.includes(o) ? prev.filter((x) => x !== o) : [...prev, o]))} />
              <Textarea
                label="Accessibility needs"
                placeholder="e.g. Step-free access where possible"
                icon={Accessibility}
                maxLength={500}
                value={form.accessibility_needs}
                onChange={set('accessibility_needs')}
              />
              <Textarea
                label="Anything else the planner should know"
                placeholder="e.g. Avoid very early starts; we love night markets."
                icon={MessageSquare}
                maxLength={1000}
                value={form.additional_notes}
                onChange={set('additional_notes')}
              />
            </div>
          </section>

          <div className="flex flex-col items-center gap-3 pb-4">
            <button type="submit" className="btn btn-primary w-full max-w-md justify-center py-3.5 text-base shadow-glow" disabled={submitting}>
              <Sparkles className="h-5 w-5" aria-hidden="true" />
              Generate my itinerary
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </button>
            <p className="text-xs text-slate-400">
              Typical generation takes 20–60 seconds. Every stop is validated against real Google Places data.
            </p>
          </div>
        </form>
      </div>
    </PageTransition>
  );
}
