import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  UserRound, Phone, CalendarDays, Coins, Home, Gauge, Accessibility,
  Save, LogOut, MapPin, BookmarkX, Sparkles, ArrowLeft,
} from 'lucide-react';
import { usersAPI } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { PageTransition } from '../components/ui/Reveal';
import { CardSkeleton, EmptyState } from '../components/ui/States';
import Button from '../components/ui/Button';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { Input, Select, Textarea } from '../components/ui/Form';
import { CURRENCIES, ACCOMMODATION_OPTIONS, TRANSPORTATION_OPTIONS, BUDGET_LEVEL_OPTIONS, INTEREST_OPTIONS, DIETARY_OPTIONS } from '../lib/constants';
import { initials } from '../lib/format';

function ChipGroup({ options, selected, onToggle, label }) {
  return (
    <div>
      <p className="label">{label}</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
        {options.map((o) => {
          const on = selected.includes(o);
          return (
            <button key={o} type="button" onClick={() => onToggle(o)} className={`chip ${on ? 'chip-on' : 'chip-off'}`} aria-pressed={on}>
              {o.replace(/_/g, ' ')}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function Profile() {
  const { profile, updateProfile, logout } = useAuth();
  const toast = useToast();

  const [pForm, setPForm] = useState(null);
  const [prefForm, setPrefForm] = useState(null);
  const [prefsExist, setPrefsExist] = useState(true);
  const [saved, setSaved] = useState(null);
  const [busyProfile, setBusyProfile] = useState(false);
  const [busyPrefs, setBusyPrefs] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);

  useEffect(() => {
    if (profile) {
      setPForm({
        full_name: profile.full_name || '',
        phone: profile.phone || '',
        avatar_url: profile.avatar_url || '',
        date_of_birth: profile.date_of_birth || '',
        preferred_currency: profile.preferred_currency || 'INR',
      });
    }
  }, [profile]);

  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    usersAPI
      .preferences(ctrl.signal)
      .then((p) => {
        if (!alive) return;
        setPrefForm({
          home_city: p.home_city || '',
          interests: p.interests || [],
          activity_preferences: p.activity_preferences || [],
          accommodation_preference: p.accommodation_preference || 'midrange_hotel',
          transportation_preference: p.transportation_preference || 'mixed',
          budget_level: p.budget_level || 'moderate',
          dietary_preferences: p.dietary_preferences || [],
          accessibility_needs: p.accessibility_needs || '',
          currency: p.currency || 'INR',
        });
      })
      .catch((err) => {
        if (err.status === 404 && alive) {
          setPrefsExist(false);
          setPrefForm({
            home_city: '', interests: [], activity_preferences: [],
            accommodation_preference: 'midrange_hotel', transportation_preference: 'mixed',
            budget_level: 'moderate', dietary_preferences: [], accessibility_needs: '', currency: 'INR',
          });
        } else if (alive) {
          toast.error('Preferences unavailable', err.message);
        }
      });
    usersAPI
      .savedDestinations(ctrl.signal)
      .then((d) => alive && setSaved(d.items || []))
      .catch(() => alive && setSaved([]));
    return () => {
      alive = false;
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveProfile = async (e) => {
    e.preventDefault();
    setBusyProfile(true);
    try {
      const patch = {
        full_name: pForm.full_name.trim() || undefined,
        phone: pForm.phone.trim() || undefined,
        avatar_url: pForm.avatar_url.trim() || undefined,
        date_of_birth: pForm.date_of_birth || undefined,
        preferred_currency: pForm.preferred_currency,
      };
      const updated = await usersAPI.updateMe(patch);
      updateProfile(updated);
      toast.success('Profile saved');
    } catch (err) {
      toast.error('Could not save profile', err.message);
    } finally {
      setBusyProfile(false);
    }
  };

  const savePrefs = async () => {
    setBusyPrefs(true);
    try {
      await usersAPI.savePreferences({
        home_city: prefForm.home_city.trim() || undefined,
        interests: prefForm.interests,
        activity_preferences: prefForm.activity_preferences,
        accommodation_preference: prefForm.accommodation_preference,
        transportation_preference: prefForm.transportation_preference,
        budget_level: prefForm.budget_level,
        dietary_preferences: prefForm.dietary_preferences,
        accessibility_needs: prefForm.accessibility_needs.trim() || undefined,
        currency: prefForm.currency,
      });
      setPrefsExist(true);
      toast.success('Preferences saved', 'The planner will use these on your next trip.');
    } catch (err) {
      toast.error('Could not save preferences', err.message);
    } finally {
      setBusyPrefs(false);
    }
  };

  const removeSaved = async (placeId, name) => {
    try {
      await usersAPI.removeSavedDestination(placeId);
      setSaved((prev) => prev.filter((s) => s.place_id !== placeId));
      toast.info('Removed', `${name || 'Place'} was removed from saved places.`);
    } catch (err) {
      toast.error('Could not remove', err.message);
    }
  };

  return (
    <PageTransition>
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <Link to="/dashboard" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-navy-950">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Dashboard
        </Link>
        <h1 className="font-display text-3xl font-extrabold sm:text-4xl">Profile & settings</h1>

        {/* Profile card */}
        <section className="card mt-6 p-6" aria-labelledby="profile-heading">
          <h2 id="profile-heading" className="mb-5 flex items-center gap-2 font-display text-lg font-bold">
            <UserRound className="h-5 w-5 text-ocean-600" aria-hidden="true" /> Account information
          </h2>
          {!pForm ? (
            <CardSkeleton lines={3} />
          ) : (
            <form onSubmit={saveProfile} className="space-y-4">
              <div className="flex items-center gap-4">
                {pForm.avatar_url ? (
                  <img src={pForm.avatar_url} alt="Your avatar" className="h-16 w-16 rounded-2xl object-cover" />
                ) : (
                  <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-ocean-500 to-navy-900 font-display text-xl font-bold text-white">
                    {initials(pForm.full_name || profile?.email)}
                  </span>
                )}
                <div className="min-w-0">
                  <p className="font-semibold text-navy-950">{profile?.email}</p>
                  <p className="text-xs text-slate-500">Signed in via {profile?.provider === 'email' ? 'email & password' : profile?.provider || 'email'}</p>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Full name" icon={UserRound} maxLength={120} value={pForm.full_name} onChange={(e) => setPForm((f) => ({ ...f, full_name: e.target.value }))} />
                <Input label="Phone" icon={Phone} maxLength={30} value={pForm.phone} onChange={(e) => setPForm((f) => ({ ...f, phone: e.target.value }))} />
                <Input label="Date of birth" type="date" icon={CalendarDays} value={pForm.date_of_birth} onChange={(e) => setPForm((f) => ({ ...f, date_of_birth: e.target.value }))} />
                <Select label="Preferred currency" icon={Coins} options={CURRENCIES} value={pForm.preferred_currency} onChange={(e) => setPForm((f) => ({ ...f, preferred_currency: e.target.value }))} />
              </div>
              <Input
                label="Avatar URL (optional)"
                type="url"
                placeholder="https://…"
                maxLength={2048}
                value={pForm.avatar_url}
                onChange={(e) => setPForm((f) => ({ ...f, avatar_url: e.target.value }))}
                hint="A public image URL — uploaded files are not supported by the profile API yet."
              />
              <Button type="submit" loading={busyProfile}>
                <Save className="h-4 w-4" aria-hidden="true" /> Save profile
              </Button>
            </form>
          )}
        </section>

        {/* Preferences */}
        <section className="card mt-8 p-6" aria-labelledby="prefs-heading">
          <h2 id="prefs-heading" className="mb-1 flex items-center gap-2 font-display text-lg font-bold">
            <Gauge className="h-5 w-5 text-ocean-600" aria-hidden="true" /> Travel preferences
          </h2>
          <p className="mb-5 text-sm text-slate-600">
            {prefsExist ? 'These defaults pre-fill the AI planner for every new trip.' : 'You have no saved preferences yet — set them below.'}
          </p>
          {!prefForm ? (
            <CardSkeleton lines={4} />
          ) : (
            <div className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Home city" icon={Home} maxLength={160} value={prefForm.home_city} onChange={(e) => setPrefForm((f) => ({ ...f, home_city: e.target.value }))} />
                <Select label="Budget level" icon={Coins} options={BUDGET_LEVEL_OPTIONS} value={prefForm.budget_level} onChange={(e) => setPrefForm((f) => ({ ...f, budget_level: e.target.value }))} />
                <Select label="Accommodation" options={ACCOMMODATION_OPTIONS} value={prefForm.accommodation_preference} onChange={(e) => setPrefForm((f) => ({ ...f, accommodation_preference: e.target.value }))} />
                <Select label="Transportation" options={TRANSPORTATION_OPTIONS} value={prefForm.transportation_preference} onChange={(e) => setPrefForm((f) => ({ ...f, transportation_preference: e.target.value }))} />
              </div>
              <ChipGroup label="Interests" options={INTEREST_OPTIONS} selected={prefForm.interests} onToggle={(o) => setPrefForm((f) => ({ ...f, interests: f.interests.includes(o) ? f.interests.filter((x) => x !== o) : [...f.interests, o] }))} />
              <ChipGroup label="Dietary preferences" options={DIETARY_OPTIONS} selected={prefForm.dietary_preferences} onToggle={(o) => setPrefForm((f) => ({ ...f, dietary_preferences: f.dietary_preferences.includes(o) ? f.dietary_preferences.filter((x) => x !== o) : [...f.dietary_preferences, o] }))} />
              <Textarea label="Accessibility needs" icon={Accessibility} maxLength={500} value={prefForm.accessibility_needs} onChange={(e) => setPrefForm((f) => ({ ...f, accessibility_needs: e.target.value }))} />
              <Button onClick={savePrefs} loading={busyPrefs}>
                <Save className="h-4 w-4" aria-hidden="true" /> Save preferences
              </Button>
            </div>
          )}
        </section>

        {/* Saved places */}
        <section className="card mt-8 p-6" aria-labelledby="saved-heading">
          <h2 id="saved-heading" className="mb-5 flex items-center gap-2 font-display text-lg font-bold">
            <MapPin className="h-5 w-5 text-ocean-600" aria-hidden="true" /> Saved places
          </h2>
          {saved === null ? (
            <CardSkeleton lines={2} />
          ) : saved.length ? (
            <ul className="space-y-2.5">
              {saved.map((s) => (
                <li key={s.id} className="flex items-center gap-3 rounded-xl border border-slate-100 p-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sand-100 text-sm font-bold text-sand-900">
                    {s.name?.[0] || '?'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-navy-950">{s.name}</p>
                    {s.address ? <p className="truncate text-xs text-slate-500">{s.address}</p> : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => removeSaved(s.place_id, s.name)}
                    className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                    aria-label={`Remove ${s.name || 'saved place'}`}
                  >
                    <BookmarkX className="h-4 w-4" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              compact
              icon={Sparkles}
              title="No saved places yet"
              message="Explore destinations and tap Save place to build your bucket list."
              action={<Link to="/explore" className="btn btn-outline">Explore destinations</Link>}
            />
          )}
        </section>

        {/* Session */}
        <section className="mt-8 rounded-2xl border border-rose-100 bg-rose-50/60 p-6">
          <h2 className="font-display text-lg font-bold text-rose-900">Session</h2>
          <p className="mt-1 text-sm text-rose-700/80">
            Signing out revokes your 7-day session token on the server immediately.
          </p>
          <Button variant="danger" className="mt-4" onClick={() => setLogoutOpen(true)}>
            <LogOut className="h-4 w-4" aria-hidden="true" /> Sign out
          </Button>
        </section>

        <ConfirmDialog
          open={logoutOpen}
          onClose={() => setLogoutOpen(false)}
          onConfirm={async () => {
            setLogoutOpen(false);
            await logout();
            window.location.href = '/';
          }}
          title="Sign out?"
          message="You'll need to sign in again to see your trips. Any unsaved form input will be lost."
          confirmLabel="Sign out"
          danger={false}
        />
      </div>
    </PageTransition>
  );
}
