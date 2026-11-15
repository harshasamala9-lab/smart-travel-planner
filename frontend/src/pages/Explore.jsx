import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Search, Compass, Hotel, Utensils, Landmark, SlidersHorizontal, X, Sparkles,
  Building2, Waves, Trees, MapPin, ArrowRight,
} from 'lucide-react';
import { useDebounce } from '../hooks/useDebounce';
import { destinationsAPI } from '../lib/api';
import DestinationCard from '../components/travel/DestinationCard';
import { EmptyState, ErrorState, SkeletonBox } from '../components/ui/States';
import SmartImage from '../components/ui/SmartImage';
import { PageTransition } from '../components/ui/Reveal';
import { SHOWCASE_DESTINATIONS, TRAVEL_STYLES } from '../lib/constants';
import { IMAGES } from '../lib/images';

const CATEGORIES = [
  { id: 'all', label: 'All', icon: Compass },
  { id: 'city', label: 'Cities', icon: Building2 },
  { id: 'beach', label: 'Beaches', icon: Waves },
  { id: 'nature', label: 'Nature', icon: Trees },
  { id: 'historical', label: 'History', icon: Landmark },
  { id: 'food', label: 'Food', icon: Utensils },
  { id: 'stay', label: 'Stays', icon: Hotel },
];

const CATEGORY_TYPES = {
  beach: ['beach', 'island'],
  nature: ['nature', 'mountain'],
  historical: ['historical'],
  city: ['city'],
  food: ['food'],
  stay: ['stay'],
};

const FALLBACK_FEATURED = SHOWCASE_DESTINATIONS.slice(0, 12).map((d) => {
  const slug = d.name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return {
    place_id: `curated-${slug}`,
    name: d.name,
    country: d.country,
    description: d.tag,
    image_url: IMAGES[d.imageKey]?.src,
    image_alt: IMAGES[d.imageKey]?.alt,
    travel_type: 'city',
    source: 'Curated travel catalog',
  };
});

export default function Explore() {
  const [params, setParams] = useSearchParams();
  const urlQuery = params.get('q') || '';

  const [input, setInput] = useState(urlQuery);
  const [category, setCategory] = useState('all');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [featured, setFeatured] = useState(null);
  const [featuredLoading, setFeaturedLoading] = useState(true);
  const debounced = useDebounce(input, 400);
  const abortRef = useRef(null);

  useEffect(() => {
    setInput(urlQuery);
  }, [urlQuery]);

  const searchTerm = debounced.trim();
  const showFeatured = searchTerm.length < 2;

  // Featured travel guides for the idle state (public endpoint, no key needed).
  useEffect(() => {
    if (!showFeatured) return undefined;
    const ctrl = new AbortController();
    let alive = true;
    setFeaturedLoading(true);
    destinationsAPI
      .featured(12, category, ctrl.signal)
      .then((data) => {
        if (!alive) return;
        setFeatured(data?.items?.length ? data.items : FALLBACK_FEATURED);
        setFeaturedLoading(false);
      })
      .catch(() => {
        if (!alive) return;
        setFeatured(FALLBACK_FEATURED);
        setFeaturedLoading(false);
      });
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, [showFeatured, category, retryCount]);

  // Debounced, cancelable travel search against the backend.
  useEffect(() => {
    if (showFeatured) {
      setResults(null);
      setError('');
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    setError('');
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    destinationsAPI
      .search(searchTerm, 16, ctrl.signal, category)
      .then((data) => {
        if (ctrl.signal.aborted) return;
        setResults(data);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setError(err.message);
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [searchTerm, category, retryCount, showFeatured]);

  const filtered = useMemo(() => {
    const items = results?.items || [];
    if (category === 'all') return items;
    const allowed = CATEGORY_TYPES[category];
    if (!allowed) return items;
    return items.filter((p) => !p.travel_type || allowed.includes(p.travel_type));
  }, [results, category]);

  const submit = (e) => {
    e.preventDefault();
    setParams(input.trim() ? { q: input.trim() } : {});
  };

  const clearSearch = () => {
    setInput('');
    setParams({});
    setResults(null);
  };

  const applySuggestion = (value) => {
    setInput(value);
    setParams({ q: value });
  };

  return (
    <PageTransition>
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header + search */}
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="font-display text-3xl font-extrabold sm:text-4xl">Explore destinations</h1>
          <p className="mt-2 text-sm text-slate-600">
            Travel-only search across cities, islands, beaches, landmarks and food scenes.
            Curated guides work everywhere — live places appear when Google Maps is connected.
          </p>
          <form onSubmit={submit} className="relative mx-auto mt-6 flex max-w-xl" role="search">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Try 'Kyoto', 'beaches', 'Jaipur', 'honeymoon'…"
              aria-label="Search travel destinations"
              className="w-full rounded-xl border border-slate-300 bg-white py-3.5 pl-12 pr-10 text-[15px] shadow-soft focus:border-ocean-500 focus:outline-none focus:ring-4 focus:ring-ocean-500/10"
            />
            {input ? (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            ) : null}
          </form>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5">
            <span className="mr-1 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">Ideas</span>
            {TRAVEL_STYLES.map((style) => (
              <button
                key={style.query}
                type="button"
                onClick={() => applySuggestion(style.query)}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 transition-colors hover:border-ocean-300 hover:text-ocean-800"
              >
                {style.label}
              </button>
            ))}
          </div>
        </div>

        {/* Category filter */}
        <div className="no-scrollbar mx-auto mt-8 flex max-w-4xl items-center justify-center gap-2 overflow-x-auto pb-1">
          <SlidersHorizontal className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          {CATEGORIES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setCategory(id)}
              className={`chip ${category === id ? 'chip-on' : 'chip-off'} shrink-0`}
              aria-pressed={category === id}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>

        {/* Idle: featured travel guides */}
        {showFeatured ? (
          <div className="mt-8">
            <p className="mb-4 flex items-center justify-center gap-1.5 text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              {category === 'all' ? 'Editor-picked travel guides' : `Top ${CATEGORIES.find((c) => c.id === category)?.label.toLowerCase()} guides`}
            </p>
            {featuredLoading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-busy="true" aria-label="Loading featured destinations">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="card overflow-hidden">
                    <SkeletonBox className="aspect-[4/3] rounded-none" />
                    <div className="space-y-2 p-4">
                      <SkeletonBox className="h-3.5 w-2/3" />
                      <SkeletonBox className="h-3 w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {(featured || []).map((place) => (
                  <DestinationCard key={place.place_id} place={place} />
                ))}
              </div>
            )}
            <div className="mt-8 text-center">
              <Link to="/planner" className="btn btn-outline">
                Plan a trip instead <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        ) : (
          /* Search results */
          <div className="mt-8">
            {loading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-busy="true" aria-label="Searching">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="card overflow-hidden">
                    <SkeletonBox className="aspect-[4/3] rounded-none" />
                    <div className="space-y-2 p-4">
                      <SkeletonBox className="h-3.5 w-2/3" />
                      <SkeletonBox className="h-3 w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : error ? (
              <ErrorState
                message={error}
                onRetry={() => setRetryCount((c) => c + 1)}
                busy={loading}
              />
            ) : filtered.length ? (
              <>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-slate-600">
                    <strong className="font-semibold text-navy-950">{results?.count ?? filtered.length}</strong>{' '}
                    travel {results?.count === 1 ? 'match' : 'matches'} for “{searchTerm}”
                  </p>
                  {results?.source ? (
                    <span className="badge bg-slate-100 text-slate-500">{results.source}</span>
                  ) : null}
                </div>
                {results?.message ? (
                  <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    {results.message}
                  </p>
                ) : null}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {filtered.map((p) => (
                    <DestinationCard key={p.place_id} place={p} />
                  ))}
                </div>
              </>
            ) : (
              <div className="mx-auto max-w-xl">
                <EmptyState
                  icon={Compass}
                  title={results?.message ? 'Travel-only search' : 'No matches found'}
                  message={
                    results?.message
                      || `Nothing matched “${searchTerm}”${category !== 'all' ? ` in ${category}` : ''}. Try a destination name or a travel style.`
                  }
                  action={
                    <button type="button" onClick={clearSearch} className="btn btn-outline">
                      Clear search
                    </button>
                  }
                />
                {results?.suggestions?.length ? (
                  <div className="mt-5">
                    <p className="mb-2 flex items-center justify-center gap-1.5 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
                      <MapPin className="h-3.5 w-3.5" aria-hidden="true" /> Try instead
                    </p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {results.suggestions.map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => applySuggestion(suggestion)}
                          className="chip chip-off"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )}
      </div>
    </PageTransition>
  );
}
