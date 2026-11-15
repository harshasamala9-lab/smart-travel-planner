import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import {
  ArrowLeft, Printer, FileDown, Share2, Pencil, Trash2, Sparkles, TriangleAlert,
  Users, CalendarRange, Wallet, Gauge, Link2, LinkIcon, Copy, RotateCcw, Check,
} from 'lucide-react';
import { itinerariesAPI, BASE } from '../lib/api';
import { useToast } from '../context/ToastContext';
import { PageTransition } from '../components/ui/Reveal';
import { ErrorState } from '../components/ui/States';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import DayTimeline from '../components/travel/DayTimeline';
import AnimatedMap from '../components/travel/AnimatedMap';
import BudgetBreakdown from '../components/travel/BudgetBreakdown';
import WeatherCard from '../components/travel/WeatherCard';
import { formatDateRange, tripDays, tripNights, formatMoney } from '../lib/format';
import { ITINERARY_STATUS } from '../lib/constants';

function ShareModal({ itinerary, open, onClose }) {
  const toast = useToast();
  const [links, setLinks] = useState(null);
  const [creating, setCreating] = useState(false);
  const [expiry, setExpiry] = useState(7);

  const load = () => {
    itinerariesAPI
      .listShares(itinerary.id)
      .then((d) => setLinks(Array.isArray(d) ? d : d.items || []))
      .catch(() => setLinks([]));
  };

  useEffect(() => {
    if (open && itinerary?.id) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, itinerary?.id]);

  const create = async () => {
    setCreating(true);
    try {
      const share = await itinerariesAPI.createShare(itinerary.id, Number(expiry));
      const url = share.share_url || `${BASE}${share.api_path}`;
      setLinks((prev) => [...(prev || []), { ...share, token: undefined }]);
      await navigator.clipboard.writeText(url).catch(() => {});
      toast.success('Share link created', 'The private link was copied to your clipboard.');
      load();
    } catch (err) {
      toast.error('Could not create link', err.message);
    } finally {
      setCreating(false);
    }
  };

  const revoke = async () => {
    try {
      await itinerariesAPI.revokeShares(itinerary.id);
      toast.info('Links revoked', 'Existing share links no longer work.');
      load();
    } catch (err) {
      toast.error('Could not revoke', err.message);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Share this itinerary">
      <p className="text-sm text-slate-600">
        Anyone with the private link can read this itinerary — no account needed. Only an
        irreversible hash of the token is stored server-side.
      </p>
      <div className="mt-4 flex items-end gap-2.5">
        <label className="flex-1">
          <span className="label">Expires in</span>
          <select value={expiry} onChange={(e) => setExpiry(e.target.value)} className="input cursor-pointer">
            {[1, 7, 30, 90, 365].map((d) => (
              <option key={d} value={d}>{d} day{d > 1 ? 's' : ''}</option>
            ))}
          </select>
        </label>
        <Button onClick={create} loading={creating} className="mb-0">
          <Link2 className="h-4 w-4" aria-hidden="true" />
          Create link
        </Button>
      </div>

      <div className="mt-5 space-y-2.5">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Active links</p>
        {links === null ? (
          <div className="skeleton h-12" />
        ) : links.length ? (
          <ul className="space-y-2">
            {links.map((s) => (
              <li key={s.id} className="flex items-center gap-3 rounded-xl border border-slate-100 px-3.5 py-2.5 text-sm">
                <LinkIcon className="h-4 w-4 shrink-0 text-ocean-600" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold text-navy-950">Expires {s.expires_at ? new Date(s.expires_at).toLocaleDateString() : '—'}</span>
                  <span className="block text-xs text-slate-500">Created {s.created_at ? new Date(s.created_at).toLocaleString() : '—'}</span>
                </span>
                {s.share_url || s.api_path ? (
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(s.share_url || `${BASE}${s.api_path}`);
                      toast.info('Copied', 'Share link copied.');
                    }}
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-navy-950"
                    aria-label="Copy share link"
                  >
                    <Copy className="h-4 w-4" aria-hidden="true" />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-xl bg-slate-50 p-4 text-center text-sm text-slate-500">No active links.</p>
        )}
        {links?.length ? (
          <Button variant="outline" size="sm" onClick={revoke} className="w-full justify-center">
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Revoke all links
          </Button>
        ) : null}
      </div>
    </Modal>
  );
}

function EditModal({ itinerary, open, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({ title: '', summary: '', status: '', total_budget: '' });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open && itinerary) {
      setForm({
        title: itinerary.title || '',
        summary: itinerary.summary || '',
        status: itinerary.status || 'generated',
        total_budget: itinerary.total_budget ?? '',
      });
    }
  }, [open, itinerary]);

  const save = async () => {
    setBusy(true);
    try {
      const patch = {};
      if (form.title.trim() && form.title !== itinerary.title) patch.title = form.title.trim();
      if (form.summary !== itinerary.summary) patch.summary = form.summary;
      if (form.status !== itinerary.status) patch.status = form.status;
      if (Number(form.total_budget) > 0 && Number(form.total_budget) !== itinerary.total_budget) {
        patch.total_budget = Number(form.total_budget);
      }
      if (!Object.keys(patch).length) {
        onClose();
        return;
      }
      await itinerariesAPI.update(itinerary.id, patch);
      toast.success('Itinerary updated');
      onSaved();
      onClose();
    } catch (err) {
      toast.error('Update failed', err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Edit itinerary">
      <div className="space-y-4">
        <label className="block">
          <span className="label">Title</span>
          <input className="input" maxLength={160} value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
        </label>
        <label className="block">
          <span className="label">Summary</span>
          <textarea className="input" rows={2} maxLength={3000} value={form.summary} onChange={(e) => setForm((f) => ({ ...f, summary: e.target.value }))} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">Status</span>
            <select className="input cursor-pointer" value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
              {['draft', 'generated', 'saved', 'archived'].map((s) => (
                <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">Total budget</span>
            <input className="input" type="number" min="1" value={form.total_budget} onChange={(e) => setForm((f) => ({ ...f, total_budget: e.target.value }))} />
          </label>
        </div>
        <p className="text-xs text-slate-400">
          Changing the budget recalculates the estimate. Full day-by-day editing replaces all days, so it stays out of this quick editor.
        </p>
      </div>
      <div className="mt-6 flex justify-end gap-2.5">
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button onClick={save} loading={busy}>Save changes</Button>
      </div>
    </Modal>
  );
}

export default function ItineraryDetail() {
  const { id } = useParams();
  const location = useLocation();
  const toast = useToast();
  const [itinerary, setItinerary] = useState(location.state?.itinerary || null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(!location.state?.itinerary);
  const [shareOpen, setShareOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const fresh = Boolean(location.state?.fresh);

  useEffect(() => {
    if (itinerary) return undefined;
    let alive = true;
    const ctrl = new AbortController();
    itinerariesAPI
      .get(id, ctrl.signal)
      .then((data) => alive && (setItinerary(data), setLoading(false)))
      .catch((err) => {
        if (err.name === 'AbortError') return;
        if (alive) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => {
      alive = false;
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (fresh && itinerary) {
      toast.success('Itinerary saved to My Trips', 'You can edit, share or export it any time.');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exportPdf = async () => {
    setDownloading(true);
    try {
      const res = await itinerariesAPI.pdf(itinerary.id);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${itinerary.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'itinerary'}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('PDF exported', 'A printable trip book has been downloaded.');
    } catch (err) {
      toast.error('PDF export failed', err.message);
    } finally {
      setDownloading(false);
    }
  };

  const deleteTrip = async () => {
    setDeleting(true);
    try {
      await itinerariesAPI.remove(itinerary.id);
      toast.info('Itinerary deleted', 'Days, activities and share links were removed with it.');
      window.location.href = '/itineraries';
    } catch (err) {
      toast.error('Delete failed', err.message);
      setDeleting(false);
    }
  };

  if (error) {
    return (
      <PageTransition>
        <div className="mx-auto max-w-3xl px-4 py-16">
          <ErrorState message={error} />
          <div className="mt-5 text-center">
            <Link to="/itineraries" className="btn btn-outline">Back to My Trips</Link>
          </div>
        </div>
      </PageTransition>
    );
  }

  if (loading || !itinerary) {
    return (
      <PageTransition>
        <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-label="Loading itinerary">
          <svg className="h-10 w-10 animate-spin text-ocean-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </div>
      </PageTransition>
    );
  }

  const status = ITINERARY_STATUS[itinerary.status] || ITINERARY_STATUS.draft;
  const budget = itinerary.budget_estimate;
  const currency = itinerary.currency;
  const meta = itinerary.generation_metadata || {};
  const recs = itinerary.recommendations || {};

  return (
    <PageTransition>
      <article className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="no-print mb-4 flex items-center justify-between">
          <Link to="/itineraries" className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-navy-950">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> My Trips
          </Link>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <Printer className="h-4 w-4" aria-hidden="true" /> Print
            </Button>
            <Button variant="outline" size="sm" onClick={exportPdf} loading={downloading}>
              <FileDown className="h-4 w-4" aria-hidden="true" /> PDF
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShareOpen(true)}>
              <Share2 className="h-4 w-4" aria-hidden="true" /> Share
            </Button>
            <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
              <Pencil className="h-4 w-4" aria-hidden="true" /> Edit
            </Button>
            <Button variant="outline" size="sm" onClick={() => setDeleteOpen(true)} className="text-rose-600 hover:border-rose-300">
              <Trash2 className="h-4 w-4" aria-hidden="true" /> Delete
            </Button>
          </div>
        </div>

        {/* Header */}
        <header className="card print-full p-6 sm:p-8">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className={`badge ${status.class}`}>{status.label}</span>
            {fresh ? <span className="badge bg-ocean-600 text-white"><Sparkles className="h-3 w-3" aria-hidden="true" /> Freshly generated</span> : null}
          </div>
          <h1 className="mt-3 font-display text-3xl font-extrabold sm:text-4xl">{itinerary.title}</h1>
          {itinerary.summary ? <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-slate-600">{itinerary.summary}</p> : null}
          <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { icon: CalendarRange, label: 'Dates', value: formatDateRange(itinerary.start_date, itinerary.end_date) },
              { icon: Sparkles, label: 'Length', value: `${tripDays(itinerary.start_date, itinerary.end_date)} days · ${tripNights(itinerary.start_date, itinerary.end_date)} nights` },
              { icon: Users, label: 'Travellers', value: String(itinerary.travellers) },
              { icon: Wallet, label: 'Budget', value: budget ? formatMoney(budget.total, budget.currency) : formatMoney(itinerary.total_budget, currency) },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="rounded-xl bg-slate-50 p-3.5">
                <dt className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-500">
                  <Icon className="h-3.5 w-3.5 text-ocean-600" aria-hidden="true" />
                  {label}
                </dt>
                <dd className="mt-1 text-sm font-semibold text-navy-950">{value}</dd>
              </div>
            ))}
          </dl>
          {itinerary.interests?.length ? (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {itinerary.interests.map((i) => (
                <span key={i} className="chip chip-off cursor-default">{i.replace(/_/g, ' ')}</span>
              ))}
              <span className="chip cursor-default bg-navy-100 text-navy-800">
                <Gauge className="h-3 w-3" aria-hidden="true" /> {itinerary.pace}
              </span>
            </div>
          ) : null}
        </header>

        {itinerary.destination_latitude != null && itinerary.destination_longitude != null ? (
          <div className="mt-6">
            <AnimatedMap
              title={itinerary.destination_name}
              latitude={itinerary.destination_latitude}
              longitude={itinerary.destination_longitude}
              points={(itinerary.days || [])
                .flatMap((day) => day.activities || [])
                .filter((activity) => activity.latitude != null && activity.longitude != null)
                .slice(0, 12)
                .map((activity) => ({
                  name: activity.name,
                  latitude: activity.latitude,
                  longitude: activity.longitude,
                }))}
            />
          </div>
        ) : null}

        {/* Warnings */}
        {itinerary.warnings?.length ? (
          <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <h2 className="flex items-center gap-2 text-sm font-bold text-amber-800">
              <TriangleAlert className="h-4 w-4" aria-hidden="true" /> Things to know
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1 text-xs leading-relaxed text-amber-800">
              {itinerary.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.55fr_1fr] lg:items-start">
          {/* Days */}
          <section aria-labelledby="days-heading" className="min-w-0">
            <h2 id="days-heading" className="sr-only">Daily schedule</h2>
            <DayTimeline days={itinerary.days} currency={currency} />
          </section>

          {/* Sidebar */}
          <aside className="no-print space-y-6 lg:sticky lg:top-24">
            <BudgetBreakdown budget={budget} totalBudget={itinerary.total_budget} currency={currency} />
            {itinerary.weather_summary ? <WeatherCard weather={itinerary.weather_summary} /> : null}

            {recs.attractions?.length || recs.restaurants?.length ? (
              <div className="card p-5">
                <h2 className="mb-3 font-display text-lg font-bold">Worth considering</h2>
                {recs.attractions?.length ? (
                  <div className="mb-4">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Attractions</p>
                    <ul className="mt-2 space-y-1.5 text-sm">
                      {recs.attractions.slice(0, 4).map((r) => (
                        <li key={r.place_id || r.name} className="flex items-baseline justify-between gap-2">
                          <span className="truncate text-navy-950">{r.name}</span>
                          {r.rating ? <span className="shrink-0 text-xs font-semibold text-amber-600">{r.rating.toFixed(1)}★</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {recs.restaurants?.length ? (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Restaurants</p>
                    <ul className="mt-2 space-y-1.5 text-sm">
                      {recs.restaurants.slice(0, 4).map((r) => (
                        <li key={r.place_id || r.name} className="flex items-baseline justify-between gap-2">
                          <span className="truncate text-navy-950">{r.name}</span>
                          {r.rating ? <span className="shrink-0 text-xs font-semibold text-amber-600">{r.rating.toFixed(1)}★</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            {Object.keys(meta).length ? (
              <details className="card p-5 text-sm">
                <summary className="cursor-pointer font-display font-bold">Generation details</summary>
                <dl className="mt-3 space-y-1.5 text-xs text-slate-600">
                  {meta.ai_attempts != null ? <div className="flex justify-between"><dt>AI attempts</dt><dd>{meta.ai_attempts}</dd></div> : null}
                  {meta.generation_time_seconds != null ? <div className="flex justify-between"><dt>Generation time</dt><dd>{meta.generation_time_seconds}s</dd></div> : null}
                  {Array.isArray(meta.data_sources) ? <div className="flex justify-between"><dt>Data sources</dt><dd className="text-right">{meta.data_sources.join(', ')}</dd></div> : null}
                </dl>
              </details>
            ) : null}
          </aside>
        </div>

        <ShareModal itinerary={itinerary} open={shareOpen} onClose={() => setShareOpen(false)} />
        <EditModal
          itinerary={itinerary}
          open={editOpen}
          onClose={() => setEditOpen(false)}
          onSaved={async () => {
            const updated = await itinerariesAPI.get(itinerary.id);
            setItinerary(updated);
          }}
        />
        <ConfirmDialog
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
          onConfirm={deleteTrip}
          busy={deleting}
          title="Delete this itinerary?"
          message="This permanently removes the itinerary with all of its days, activities and share links. This cannot be undone."
          confirmLabel="Delete forever"
        />
      </article>
    </PageTransition>
  );
}
