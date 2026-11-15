import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  MapPin, Star, Globe, Phone, Clock3, BookmarkPlus, BookmarkCheck,
  Utensils, Landmark, ArrowLeft, ExternalLink, Wallet,
  CalendarRange, BookOpen,
} from 'lucide-react';
import { destinationsAPI, usersAPI, weatherAPI } from '../lib/api';
import SmartImage from '../components/ui/SmartImage';
import AnimatedMap from '../components/travel/AnimatedMap';
import { PageTransition } from '../components/ui/Reveal';
import { CardSkeleton, EmptyState, ErrorState, SkeletonBox } from '../components/ui/States';
import { useToast } from '../context/ToastContext';

const PRICE = { free: 'Free', inexpensive: 'Budget-friendly', moderate: 'Moderate', expensive: 'Upscale', very_expensive: 'Luxury' };

function PlaceRow({ place, icon }) {
  return (
    <li className="flex items-center gap-3 rounded-xl border border-slate-100 p-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-navy-950">{place.name}</p>
        <p className="truncate text-xs text-slate-500">{place.formatted_address || place.types?.join(', ')}</p>
      </div>
      {place.rating ? (
        <span className="flex shrink-0 items-center gap-1 text-xs font-semibold text-amber-600">
          <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" aria-hidden="true" />
          {place.rating.toFixed(1)}
        </span>
      ) : null}
    </li>
  );
}

export default function DestinationDetail() {
  const { placeId } = useParams();
  const toast = useToast();
  const [place, setPlace] = useState(null);
  const [attractions, setAttractions] = useState(null);
  const [restaurants, setRestaurants] = useState(null);
  const [weather, setWeather] = useState(null);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    setPlace(null);
    setAttractions(null);
    setRestaurants(null);
    setWeather(null);
    setError('');
    (async () => {
      try {
        const details = await destinationsAPI.details(placeId, ctrl.signal);
        if (!alive) return;
        setPlace(details);
        destinationsAPI
          .nearby(placeId, 'attractions', { limit: 8 }, ctrl.signal)
          .then((d) => alive && setAttractions(d))
          .catch(() => alive && setAttractions({ items: [] }));
        destinationsAPI
          .nearby(placeId, 'restaurants', { limit: 8 }, ctrl.signal)
          .then((d) => alive && setRestaurants(d))
          .catch(() => alive && setRestaurants({ items: [] }));
        weatherAPI
          .get(details.name || details.formatted_address || 'destination', {}, ctrl.signal)
          .then((w) => alive && setWeather(w))
          .catch(() => alive && setWeather(null));
      } catch (err) {
        if (err.name !== 'AbortError' && alive) setError(err.message);
      }
    })();
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, [placeId]);

  useEffect(() => {
    let alive = true;
    usersAPI
      .savedDestinations()
      .then((d) => alive && setSaved(new Set((d.items || []).map((s) => s.place_id))))
      .catch(() => alive && setSaved(new Set()));
    return () => {
      alive = false;
    };
  }, []);

  const toggleSave = async () => {
    if (!place) return;
    setSaving(true);
    try {
      if (saved?.has(place.place_id)) {
        await usersAPI.removeSavedDestination(place.place_id);
        setSaved((prev) => new Set([...prev].filter((id) => id !== place.place_id)));
        toast.info('Removed', `${place.name} is no longer in your saved places.`);
      } else {
        await usersAPI.saveDestination({ place_id: place.place_id });
        setSaved((prev) => new Set([...(prev || []), place.place_id]));
        toast.success('Saved!', `${place.name} added to your saved places.`);
      }
    } catch (err) {
      toast.error('Could not update saved places', err.message);
    } finally {
      setSaving(false);
    }
  };

  if (error) {
    return (
      <PageTransition>
        <div className="mx-auto max-w-3xl px-4 py-16">
          <ErrorState message={error} onRetry={() => window.location.reload()} />
        </div>
      </PageTransition>
    );
  }

  if (!place) {
    return (
      <PageTransition>
        <div className="mx-auto max-w-5xl px-4 py-10" aria-busy="true">
          <SkeletonBox className="mb-6 aspect-[21/9] rounded-3xl" />
          <div className="space-y-3">
            <SkeletonBox className="h-7 w-1/2" />
            <SkeletonBox className="h-4 w-1/3" />
            <SkeletonBox className="h-3 w-2/3" />
          </div>
        </div>
      </PageTransition>
    );
  }

  const isSaved = saved?.has(place.place_id);
  const isCurated = place.place_id.startsWith('curated-') || place.source === 'Curated travel catalog';
  const typeLabel = place.travel_type
    ? place.travel_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : null;
  const tags = (place.types || []).filter((t) => t !== 'travel_destination' && t !== place.travel_type).slice(0, 8);

  return (
    <PageTransition>
      <article className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        <Link to="/explore" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-navy-950">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to explore
        </Link>

        {/* Hero photo: curated Wikimedia image or the Google photo proxy */}
        <SmartImage
          src={place.image_url || undefined}
          photoName={place.photo_names?.[0]}
          alt={place.image_alt || place.name}
          ratio="aspect-[21/9] max-sm:aspect-[4/3]"
          maxWidth={1200}
          eager
          className="rounded-3xl shadow-lift"
        />
        {place.image_credit ? (
          <p className="mt-2 px-1 text-right text-[11px] text-slate-400">
            Photo: {place.image_credit}
          </p>
        ) : null}

        <header className="mt-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-3xl font-extrabold sm:text-4xl">{place.name}</h1>
              {typeLabel ? (
                <span className="badge bg-ocean-100 text-ocean-800">{typeLabel}</span>
              ) : null}
              {isCurated ? (
                <span className="badge bg-sand-200 text-sand-900">Travel guide</span>
              ) : null}
            </div>
            <p className="mt-1.5 flex items-center gap-1.5 text-sm text-slate-600">
              <MapPin className="h-4 w-4 text-ocean-600" aria-hidden="true" />
              {place.formatted_address || 'Location details from Google Places'}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
              {place.rating ? (
                <span className="flex items-center gap-1 font-semibold text-amber-600">
                  <Star className="h-4 w-4 fill-amber-500 text-amber-500" aria-hidden="true" />
                  {place.rating.toFixed(1)}
                  <span className="font-normal text-slate-400">({place.user_rating_count?.toLocaleString()} reviews)</span>
                </span>
              ) : null}
              {place.price_level ? (
                <span className="flex items-center gap-1 text-slate-600">
                  <Wallet className="h-4 w-4 text-ocean-600" aria-hidden="true" />
                  {PRICE[place.price_level] || place.price_level}
                </span>
              ) : null}
              {place.open_now != null ? (
                <span className={place.open_now ? 'font-semibold text-ocean-700' : 'font-semibold text-rose-500'}>
                  {place.open_now ? 'Open now' : 'Currently closed'}
                </span>
              ) : null}
              {place.best_time ? (
                <span className="flex items-center gap-1 text-slate-600">
                  <CalendarRange className="h-4 w-4 text-ocean-600" aria-hidden="true" />
                  Best time: {place.best_time}
                </span>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={toggleSave}
            disabled={saving || saved === null}
            className={`btn ${isSaved ? 'btn-outline' : 'btn-primary'}`}
            aria-pressed={Boolean(isSaved)}
          >
            {isSaved ? <BookmarkCheck className="h-4 w-4" aria-hidden="true" /> : <BookmarkPlus className="h-4 w-4" aria-hidden="true" />}
            {isSaved ? 'Saved' : 'Save place'}
          </button>
        </header>

        {place.editorial_summary ? (
          <p className="mt-4 max-w-3xl text-[15px] leading-relaxed text-slate-600">{place.editorial_summary}</p>
        ) : null}

        {isCurated ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="card flex items-start gap-3 p-4">
              <CalendarRange className="mt-0.5 h-5 w-5 shrink-0 text-ocean-600" aria-hidden="true" />
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Best time to visit</p>
                <p className="mt-0.5 text-sm font-semibold text-navy-950">{place.best_time || 'Year-round'}</p>
              </div>
            </div>
            <div className="card flex items-start gap-3 p-4">
              <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-ocean-600" aria-hidden="true" />
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Country</p>
                <p className="mt-0.5 text-sm font-semibold text-navy-950">{place.country || '—'}</p>
              </div>
            </div>
            <div className="card flex items-start gap-3 p-4">
              <BookOpen className="mt-0.5 h-5 w-5 shrink-0 text-ocean-600" aria-hidden="true" />
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Travel style</p>
                <p className="mt-0.5 text-sm font-semibold capitalize text-navy-950">{place.travel_type?.replace(/_/g, ' ') || 'Destination'}</p>
              </div>
            </div>
          </div>
        ) : null}

        {/* Info grid */}
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="card p-5">
            <h2 className="mb-3 font-display text-lg font-bold">Details</h2>
            <ul className="space-y-2.5 text-sm">
              {place.website_uri ? (
                <li className="flex items-start gap-2.5">
                  <Globe className="mt-0.5 h-4 w-4 shrink-0 text-ocean-600" aria-hidden="true" />
                  <a href={place.website_uri} target="_blank" rel="noopener noreferrer" className="break-all font-medium text-ocean-700 hover:underline">
                    {isCurated ? 'Read the Wikipedia destination guide' : place.website_uri.replace(/^https?:\/\//, '')}
                  </a>
                </li>
              ) : null}
              {place.national_phone_number ? (
                <li className="flex items-start gap-2.5">
                  <Phone className="mt-0.5 h-4 w-4 shrink-0 text-ocean-600" aria-hidden="true" />
                  <a href={`tel:${place.national_phone_number.replace(/\s/g, '')}`} className="font-medium text-navy-950 hover:underline">
                    {place.national_phone_number}
                  </a>
                </li>
              ) : null}
              {place.current_opening_hours?.length || place.opening_hours?.length ? (
                <li className="flex items-start gap-2.5">
                  <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-ocean-600" aria-hidden="true" />
                  <div>
                    {(place.current_opening_hours || place.opening_hours).slice(0, 7).map((h, i) => (
                      <p key={i} className={i === 0 ? 'font-semibold text-navy-950' : 'text-slate-500'}>{h}</p>
                    ))}
                  </div>
                </li>
              ) : null}
              {place.google_maps_uri ? (
                <li className="flex items-start gap-2.5">
                  <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-ocean-600" aria-hidden="true" />
                  <a href={place.google_maps_uri} target="_blank" rel="noopener noreferrer" className="font-medium text-ocean-700 hover:underline">
                    Open in Google Maps
                  </a>
                </li>
              ) : null}
              {tags.length ? (
                <li className="flex flex-wrap gap-1.5 pt-1">
                  {tags.map((t) => (
                    <span key={t} className="badge bg-slate-100 text-slate-600">{t.replace(/_/g, ' ')}</span>
                  ))}
                </li>
              ) : null}
              {place.source ? (
                <li className="pt-1 text-[11px] text-slate-400">Data source: {place.source}</li>
              ) : null}
            </ul>
          </div>

          {/* Animated, dependency-free map with a direct Google Maps hand-off. */}
          <AnimatedMap
            title={place.name}
            latitude={place.latitude}
            longitude={place.longitude}
          />
        </div>

        {/* Weather (only when the backend returns real data) */}
        {weather ? (
          <div className="mt-6">
            <WeatherInline weather={weather} placeName={place.name} />
          </div>
        ) : null}

        {/* Nearby */}
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <section aria-labelledby="near-attractions">
            <h2 id="near-attractions" className="mb-3 flex items-center gap-2 font-display text-xl font-bold">
              <Landmark className="h-5 w-5 text-ocean-600" aria-hidden="true" /> Nearby attractions
            </h2>
            {attractions === null ? (
              <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <SkeletonBox key={i} className="h-16" />)}</div>
            ) : attractions.items?.length ? (
              <ul className="space-y-2">{attractions.items.slice(0, 8).map((p) => <PlaceRow key={p.place_id} place={p} icon={<Landmark className="h-4 w-4" aria-hidden="true" />} />)}</ul>
            ) : attractions.message ? (
              <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-500">
                {attractions.message}
              </p>
            ) : (
              <EmptyState compact icon={Landmark} title="No attractions listed" message="Nothing nearby matched Google's attraction categories." />
            )}
          </section>
          <section aria-labelledby="near-restaurants">
            <h2 id="near-restaurants" className="mb-3 flex items-center gap-2 font-display text-xl font-bold">
              <Utensils className="h-5 w-5 text-ocean-600" aria-hidden="true" /> Nearby restaurants
            </h2>
            {restaurants === null ? (
              <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <SkeletonBox key={i} className="h-16" />)}</div>
            ) : restaurants.items?.length ? (
              <ul className="space-y-2">{restaurants.items.slice(0, 8).map((p) => <PlaceRow key={p.place_id} place={p} icon={<Utensils className="h-4 w-4" aria-hidden="true" />} />)}</ul>
            ) : restaurants.message ? (
              <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-500">
                {restaurants.message}
              </p>
            ) : (
              <EmptyState compact icon={Utensils} title="No restaurants listed" message="Nothing nearby matched Google's restaurant categories." />
            )}
          </section>
        </div>
      </article>
    </PageTransition>
  );
}

function WeatherInline({ weather, placeName }) {
  const current = weather.current || {};
  const covered = weather.forecast_covers_requested_dates;
  return (
    <div className="card p-5">
      <h2 className="mb-2 font-display text-lg font-bold">Weather in {placeName}</h2>
      <p className="text-sm text-slate-600">
        {current.temp_c != null || current.temp != null ? (
          <>
            <strong className="font-display text-xl font-bold text-navy-950">{current.temp_c ?? current.temp}°</strong>{' '}
            {current.description || current.condition}
          </>
        ) : (
          'Current conditions unavailable.'
        )}
      </p>
      <p className={`mt-2 text-[11px] ${covered ? 'text-ocean-700' : 'text-amber-700'}`}>
        {covered
          ? 'Forecast covers your requested range.'
          : covered === false
            ? 'Forecast horizon reached — values beyond it are indicative only.'
            : 'No reliable forecast available for the requested dates.'}
      </p>
    </div>
  );
}
