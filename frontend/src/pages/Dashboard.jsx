import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sparkles, Briefcase, CalendarClock, Wallet, Compass, MapPin,
  FileDown, Clock3, TrendingUp, ChevronRight, Plane,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { itinerariesAPI, analyticsAPI, usersAPI } from '../lib/api';
import { greeting, formatDateRange, tripDays, formatMoney, tripBucket } from '../lib/format';
import ItineraryCard from '../components/travel/ItineraryCard';
import { CardSkeleton, EmptyState, ErrorState } from '../components/ui/States';
import { PageTransition } from '../components/ui/Reveal';
import SmartImage from '../components/ui/SmartImage';
import { IMAGES } from '../lib/images';

const QUICK_ACTIONS = [
  { to: '/planner', icon: Sparkles, label: 'Plan a new trip', tint: 'bg-ocean-600' },
  { to: '/explore', icon: Compass, label: 'Explore destinations', tint: 'bg-navy-800' },
  { to: '/itineraries', icon: Briefcase, label: 'Open My Trips', tint: 'bg-sand-500' },
];

export default function Dashboard() {
  const { profile } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [stats, setStats] = useState(null);
  const [trips, setTrips] = useState(null);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    (async () => {
      try {
        const [a, list, sv] = await Promise.all([
          analyticsAPI.me(ctrl.signal),
          itinerariesAPI.list(6, 0, ctrl.signal),
          usersAPI.savedDestinations(ctrl.signal),
        ]);
        if (!alive) return;
        setStats(a);
        setTrips(list);
        setSaved(sv);
      } catch (err) {
        if (!alive || err.name === 'AbortError') return;
        setError(err.message || 'Could not load your dashboard.');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, []);

  const upcoming = (trips?.items || []).filter((t) => ['upcoming', 'active'].includes(tripBucket(t)));
  const recent = trips?.items || [];

  const exportCsv = async () => {
    try {
      const res = await analyticsAPI.exportCsv();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'smart-travel-trips.csv';
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Report downloaded', 'One row per itinerary, saved as CSV.');
    } catch (err) {
      toast.error('Export failed', err.message);
    }
  };

  return (
    <PageTransition>
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Greeting */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-ocean-700">{greeting()},</p>
            <h1 className="font-display text-3xl font-extrabold sm:text-4xl">
              {profile?.full_name?.split(' ')[0] || 'traveler'} <Plane className="inline h-7 w-7 text-ocean-500" aria-hidden="true" />
            </h1>
            <p className="mt-1 text-sm text-slate-600">Where are we sending you next?</p>
          </div>
          <button type="button" onClick={exportCsv} className="btn btn-outline">
            <FileDown className="h-4 w-4" aria-hidden="true" />
            Export CSV
          </button>
        </div>

        {error ? (
          <div className="mt-6">
            <ErrorState message={error} onRetry={() => navigate(0)} />
          </div>
        ) : null}

        {/* Stats */}
        <div className="mt-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} lines={1} />)
            : [
                { icon: Briefcase, label: 'Planned trips', value: stats?.total_itineraries ?? 0, sub: 'all time' },
                { icon: CalendarClock, label: 'Upcoming', value: stats?.upcoming_trips ?? 0, sub: 'dates in the future' },
                { icon: Clock3, label: 'In progress', value: stats?.active_trips ?? 0, sub: 'happening now' },
                { icon: TrendingUp, label: 'Completed', value: stats?.completed_trips ?? 0, sub: 'journeys done' },
              ].map(({ icon: Icon, label, value, sub }) => (
                <div key={label} className="card p-5">
                  <div className="flex items-center justify-between">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ocean-50 text-ocean-600">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </span>
                  </div>
                  <p className="mt-3 font-display text-3xl font-extrabold text-navy-950">{value}</p>
                  <p className="text-sm font-semibold text-slate-600">{label}</p>
                  <p className="text-[11px] text-slate-400">{sub}</p>
                </div>
              ))}
        </div>

        {/* Quick actions */}
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {QUICK_ACTIONS.map(({ to, icon: Icon, label, tint }) => (
            <Link
              key={to}
              to={to}
              className="card card-hover group flex items-center gap-4 p-4"
            >
              <span className={`flex h-11 w-11 items-center justify-center rounded-xl ${tint} text-white`}>
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <span className="font-semibold text-navy-950">{label}</span>
              <ChevronRight className="ml-auto h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
            </Link>
          ))}
        </div>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1.6fr_1fr]">
          {/* Upcoming + recent */}
          <section aria-labelledby="dash-trips">
            <div className="mb-4 flex items-center justify-between">
              <h2 id="dash-trips" className="font-display text-xl font-bold">
                {upcoming.length ? 'Upcoming journeys' : 'Your itineraries'}
              </h2>
              <Link to="/itineraries" className="text-sm font-semibold text-ocean-700 hover:underline">
                View all
              </Link>
            </div>
            {loading ? (
              <div className="space-y-4">
                {Array.from({ length: 2 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
              </div>
            ) : (upcoming.length ? upcoming : recent).length ? (
              <div className="space-y-4">
                {(upcoming.length ? upcoming : recent).slice(0, 4).map((t) => (
                  <ItineraryCard key={t.id} itinerary={t} />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Sparkles}
                title="No trips yet"
                message="Let the AI plan your first journey — it takes about two minutes."
                action={
                  <Link to="/planner" className="btn btn-primary">
                    <Sparkles className="h-4 w-4" aria-hidden="true" />
                    Plan a trip
                  </Link>
                }
              />
            )}
          </section>

          {/* Side: budget + saved */}
          <aside className="space-y-6">
            {stats?.currencies?.length ? (
              <div className="card p-5">
                <h2 className="flex items-center gap-2 font-display text-lg font-bold">
                  <Wallet className="h-5 w-5 text-ocean-600" aria-hidden="true" />
                  Budget snapshot
                </h2>
                <ul className="mt-3 space-y-3">
                  {stats.currencies.slice(0, 3).map((c) => (
                    <li key={c.currency} className="flex items-baseline justify-between text-sm">
                      <span className="font-semibold text-navy-950">{c.currency}</span>
                      <span className="text-slate-600">
                        {formatMoney(c.estimated_cost, c.currency)}
                        <span className="text-xs text-slate-400"> of {formatMoney(c.planned_budget, c.currency)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11px] text-slate-400">Planning estimates per currency — never converted across currencies.</p>
              </div>
            ) : null}

            <div className="card p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 font-display text-lg font-bold">
                  <MapPin className="h-5 w-5 text-ocean-600" aria-hidden="true" />
                  Saved places
                </h2>
                <Link to="/profile" className="text-xs font-semibold text-ocean-700 hover:underline">
                  Manage
                </Link>
              </div>
              {saved === null ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => <div key={i} className="skeleton h-9" />)}
                </div>
              ) : saved.items?.length ? (
                <ul className="space-y-2.5">
                  {saved.items.slice(0, 5).map((s) => (
                    <li key={s.id} className="flex items-center gap-2.5 text-sm">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sand-100 text-xs font-bold text-sand-900">
                        {s.name?.[0] || '?'}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-navy-950">{s.name}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">
                  Nothing saved yet. Open any destination and tap{' '}
                  <span className="font-semibold text-navy-950">Save place</span>.
                </p>
              )}
            </div>

            <div className="relative overflow-hidden rounded-2xl">
              <SmartImage src={IMAGES.maldives.src} alt="" ratio="aspect-[16/9]" />
              <div className="absolute inset-0 bg-gradient-to-t from-navy-950/85 to-transparent" />
              <div className="absolute bottom-0 p-4">
                <p className="text-[11px] font-bold uppercase tracking-wider text-ocean-300">Inspiration</p>
                <p className="font-display text-lg font-bold text-white">The Maldives is calling</p>
                <Link to="/explore?q=Maldives" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-white hover:underline">
                  Explore <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                </Link>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </PageTransition>
  );
}
