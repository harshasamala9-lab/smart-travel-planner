import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Plus, Briefcase, Compass } from 'lucide-react';
import { itinerariesAPI } from '../lib/api';
import ItineraryCard from '../components/travel/ItineraryCard';
import { EmptyState, ErrorState, CardSkeleton } from '../components/ui/States';
import { PageTransition } from '../components/ui/Reveal';
import { tripBucket } from '../lib/format';

const TABS = [
  { id: 'all', label: 'All' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'active', label: 'Happening now' },
  { id: 'completed', label: 'Completed' },
  { id: 'draft', label: 'Drafts' },
  { id: 'archived', label: 'Archived' },
];

export default function MyTrips() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('all');
  const [query, setQuery] = useState('');

  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    (async () => {
      try {
        const list = await itinerariesAPI.list(50, 0, ctrl.signal);
        if (alive) setData(list);
      } catch (err) {
        if (err.name !== 'AbortError' && alive) setError(err.message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, []);

  const counts = useMemo(() => {
    const c = { all: data?.items?.length || 0, upcoming: 0, active: 0, completed: 0, draft: 0, archived: 0 };
    (data?.items || []).forEach((t) => {
      c[tripBucket(t)] += 1;
    });
    return c;
  }, [data]);

  const visible = useMemo(() => {
    let items = data?.items || [];
    if (tab !== 'all') items = items.filter((t) => tripBucket(t) === tab);
    const q = query.trim().toLowerCase();
    if (q) {
      items = items.filter(
        (t) =>
          t.title?.toLowerCase().includes(q) ||
          t.destination_name?.toLowerCase().includes(q)
      );
    }
    return items;
  }, [data, tab, query]);

  return (
    <PageTransition>
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl font-extrabold sm:text-4xl">My trips</h1>
            <p className="mt-1 text-sm text-slate-600">Every itinerary you've generated, in one place.</p>
          </div>
          <Link to="/planner" className="btn btn-primary">
            <Plus className="h-4 w-4" aria-hidden="true" />
            New trip
          </Link>
        </div>

        {/* Search */}
        <div className="relative mt-6 max-w-md">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by title or destination…"
            aria-label="Search my trips"
            className="input pl-10"
          />
        </div>

        {/* Tabs */}
        <div className="no-scrollbar mt-5 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Filter trips">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`chip shrink-0 ${tab === id ? 'chip-on' : 'chip-off'}`}
            >
              {label}
              <span className={`rounded-full px-1.5 text-[10px] ${tab === id ? 'bg-white/25' : 'bg-slate-200/70'}`}>{counts[id]}</span>
            </button>
          ))}
        </div>

        <div className="mt-6">
          {loading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
              {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={() => window.location.reload()} />
          ) : visible.length ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {visible.map((t) => <ItineraryCard key={t.id} itinerary={t} />)}
            </div>
          ) : query || tab !== 'all' ? (
            <EmptyState
              icon={Compass}
              title="Nothing here"
              message={query ? `No trips match "${query}".` : `No ${TABS.find((t) => t.id === tab)?.label.toLowerCase()} trips yet.`}
              action={
                <button type="button" onClick={() => { setQuery(''); setTab('all'); }} className="btn btn-outline">
                  Show all trips
                </button>
              }
            />
          ) : (
            <EmptyState
              icon={Briefcase}
              title="Your first trip awaits"
              message="Generate an AI itinerary and it will be saved here automatically."
              action={
                <Link to="/planner" className="btn btn-primary">
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Plan a trip
                </Link>
              }
            />
          )}
        </div>
      </div>
    </PageTransition>
  );
}
