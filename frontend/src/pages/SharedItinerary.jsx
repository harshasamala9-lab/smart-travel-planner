import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Link2, CalendarRange, Users, Wallet, Lock, ArrowLeft } from 'lucide-react';
import { sharedAPI } from '../lib/api';
import DayTimeline from '../components/travel/DayTimeline';
import BudgetBreakdown from '../components/travel/BudgetBreakdown';
import WeatherCard from '../components/travel/WeatherCard';
import { PageTransition } from '../components/ui/Reveal';
import { ErrorState } from '../components/ui/States';
import { formatDateRange, tripDays } from '../lib/format';
import { ITINERARY_STATUS } from '../lib/constants';

/** Public, read-only view behind a private share token. */
export default function SharedItinerary() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState('');

  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    sharedAPI
      .get(token, ctrl.signal)
      .then((d) => alive && setData(d))
      .catch((err) => {
        if (err.name === 'AbortError' || !alive) return;
        setError(err.message);
        setErrorCode(err.code || '');
      });
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, [token]);

  if (error) {
    return (
      <PageTransition>
        <div className="mx-auto max-w-3xl px-4 py-16">
          <ErrorState
            compact
            message={errorCode === 'not_found' ? 'This share link is invalid, expired or was revoked.' : error}
          />
          <p className="mt-4 text-center text-sm text-slate-500">
            <a href="/" className="inline-flex items-center gap-1.5 font-semibold text-ocean-700 hover:underline">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to Smart Travel Planner
            </a>
          </p>
        </div>
      </PageTransition>
    );
  }

  if (!data) {
    return (
      <PageTransition>
        <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-label="Loading shared itinerary">
          <svg className="h-10 w-10 animate-spin text-ocean-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </div>
      </PageTransition>
    );
  }

  const status = ITINERARY_STATUS[data.status] || ITINERARY_STATUS.draft;

  return (
    <PageTransition>
      <article className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <span className="badge bg-navy-100 text-navy-800"><Lock className="h-3 w-3" aria-hidden="true" /> Shared read-only view</span>
          <span className={`badge ${status.class}`}>{status.label}</span>
        </div>
        <header className="card print-full p-6 sm:p-8">
          <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.16em] text-ocean-600">
            <Link2 className="h-3.5 w-3.5" aria-hidden="true" /> Shared itinerary
          </p>
          <h1 className="mt-2 font-display text-3xl font-extrabold sm:text-4xl">{data.title}</h1>
          {data.summary ? <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-slate-600">{data.summary}</p> : null}
          <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { icon: CalendarRange, label: 'Dates', value: formatDateRange(data.start_date, data.end_date) },
              { icon: SparkleIcon, label: 'Length', value: `${tripDays(data.start_date, data.end_date)} days` },
              { icon: Users, label: 'Travellers', value: String(data.travellers) },
              { icon: Wallet, label: 'Budget', value: data.budget_estimate ? `${data.currency} ${data.budget_estimate.total?.toLocaleString()}` : `${data.currency}` },
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
        </header>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.55fr_1fr] lg:items-start">
          <section>
            <DayTimeline days={data.days} currency={data.currency} />
          </section>
          <aside className="space-y-6 lg:sticky lg:top-24">
            <BudgetBreakdown budget={data.budget_estimate} totalBudget={data.total_budget} currency={data.currency} />
            {data.weather_summary ? <WeatherCard weather={data.weather_summary} /> : null}
          </aside>
        </div>

        <p className="mt-10 text-center text-xs text-slate-400">
          Generated with Smart Travel Planner · all monetary values are planning estimates
        </p>
      </article>
    </PageTransition>
  );
}

function SparkleIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
    </svg>
  );
}
