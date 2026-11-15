import { Link } from 'react-router-dom';
import { CalendarRange, Users, Wallet, ArrowRight, MapPin } from 'lucide-react';
import { formatDateRange, tripDays, formatMoney, tripBucket } from '../../lib/format';
import { ITINERARY_STATUS } from '../../lib/constants';

const BUCKET_LABEL = { upcoming: 'Upcoming', active: 'Happening now', completed: 'Completed' };

export default function ItineraryCard({ itinerary, className = '' }) {
  const status = ITINERARY_STATUS[itinerary.status] || ITINERARY_STATUS.draft;
  const bucket = tripBucket(itinerary);
  const budget = itinerary.budget_estimate;
  return (
    <Link
      to={`/itineraries/${itinerary.id}`}
      className={`card card-hover group relative block overflow-hidden p-5 ${className}`}
      aria-label={`Open ${itinerary.title}`}
    >
      {bucket !== 'archived' && BUCKET_LABEL[bucket] ? (
        <span className="absolute right-4 top-4 badge bg-ocean-50 text-ocean-700">{BUCKET_LABEL[bucket]}</span>
      ) : null}
      <span className={`badge ${status.class}`}>{status.label}</span>
      <h3 className="mt-2.5 line-clamp-1 pr-16 font-display text-lg font-bold text-navy-950">{itinerary.title}</h3>
      <p className="mt-1 flex items-center gap-1.5 text-sm text-slate-500">
        <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span className="line-clamp-1">{itinerary.destination_name}</span>
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-600">
        <span className="flex items-center gap-1.5">
          <CalendarRange className="h-3.5 w-3.5 text-ocean-600" aria-hidden="true" />
          {formatDateRange(itinerary.start_date, itinerary.end_date)} · {tripDays(itinerary.start_date, itinerary.end_date)} days
        </span>
        <span className="flex items-center gap-1.5">
          <Users className="h-3.5 w-3.5 text-ocean-600" aria-hidden="true" />
          {itinerary.travellers}
        </span>
        <span className="flex items-center gap-1.5">
          <Wallet className="h-3.5 w-3.5 text-ocean-600" aria-hidden="true" />
          {budget ? formatMoney(budget.total, budget.currency) : formatMoney(itinerary.total_budget, itinerary.currency)}
        </span>
      </div>
      <p className="mt-3 flex items-center gap-1 text-xs font-semibold text-ocean-700 transition-transform duration-200 group-hover:translate-x-0.5">
        View itinerary <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </p>
    </Link>
  );
}
