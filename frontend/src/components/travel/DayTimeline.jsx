import { Landmark, Utensils, BedDouble, BusFront, MapPin, Star, ExternalLink, Footprints, Clock, Wallet } from 'lucide-react';
import { formatMoney, formatMinutes } from '../../lib/format';
import { ACTIVITY_CATEGORY_META } from '../../lib/constants';

const ICONS = {
  landmark: Landmark,
  utensils: Utensils,
  bed: BedDouble,
  bus: BusFront,
  'map-pin': MapPin,
};

function categoryIcon(cat) {
  return ICONS[ACTIVITY_CATEGORY_META[cat]?.icon] || MapPin;
}

/** Route leg shown between activities. */
function RouteLeg({ route }) {
  if (!route || (!route.distance_km && !route.duration_minutes)) return null;
  return (
    <div className="my-2 ml-4 flex items-center gap-2 text-[11px] text-slate-400">
      <span className="h-4 w-px bg-slate-200" aria-hidden="true" />
      <Footprints className="h-3.5 w-3.5" aria-hidden="true" />
      <span>
        {route.distance_km ? `${route.distance_km.toFixed(1)} km` : ''} {route.distance_km && route.duration_minutes ? '·' : ''}{' '}
        {route.duration_minutes ? `${Math.round(route.duration_minutes)} min` : ''}
        {route.travel_mode ? ` · ${route.travel_mode.toLowerCase()}` : ''}
      </span>
    </div>
  );
}

export default function DayTimeline({ days, currency = 'USD' }) {
  if (!days?.length) {
    return <p className="text-sm text-slate-500">No daily schedule recorded for this itinerary.</p>;
  }
  return (
    <ol className="space-y-5">
      {days.map((day) => (
        <li key={day.id} className="card print-full overflow-hidden">
          <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 bg-gradient-to-r from-navy-950 to-navy-800 px-5 py-4">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-ocean-300">Day {day.day_number}</p>
              <h3 className="mt-0.5 font-display text-lg font-bold text-white">{day.title}</h3>
              {day.summary ? <p className="mt-1 text-sm text-slate-300">{day.summary}</p> : null}
            </div>
            <div className="text-right">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Est. day cost</p>
              <p className="font-display text-base font-bold text-sand-300">{formatMoney(day.estimated_day_cost, currency)}</p>
            </div>
          </header>
          <div className="px-5 py-4">
            {day.activities?.length ? (
              <ul className="relative space-y-1 before:absolute before:left-[13px] before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-slate-200" style={{ listStyle: 'none' }}>
                {day.activities.map((a, idx) => {
                  const Icon = categoryIcon(a.category);
                  const meta = ACTIVITY_CATEGORY_META[a.category] || ACTIVITY_CATEGORY_META.other;
                  return (
                    <li key={a.id}>
                      <div className="flex gap-3">
                        <div className={`relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-white shadow-soft ${meta.color}`}>
                          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                        </div>
                        <div className="min-w-0 flex-1 pb-3">
                          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
                            {a.start_time ? (
                              <span className="flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-bold text-navy-900">
                                <Clock className="h-3 w-3" aria-hidden="true" />
                                {a.start_time.slice(0, 5)}
                                {a.end_time ? `–${a.end_time.slice(0, 5)}` : ''}
                              </span>
                            ) : null}
                            <h4 className="font-semibold text-navy-950">{a.name}</h4>
                            {a.estimated_cost > 0 ? (
                              <span className="flex items-center gap-0.5 text-xs font-semibold text-ocean-700">
                                <Wallet className="h-3 w-3" aria-hidden="true" /> {formatMoney(a.estimated_cost, currency)}
                              </span>
                            ) : null}
                          </div>
                          {a.description ? <p className="mt-1 text-sm leading-relaxed text-slate-600">{a.description}</p> : null}
                          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                            {a.address ? (
                              <span className="flex items-center gap-1">
                                <MapPin className="h-3 w-3" aria-hidden="true" /> {a.address}
                              </span>
                            ) : null}
                            {a.rating ? (
                              <span className="flex items-center gap-1 font-medium text-amber-600">
                                <Star className="h-3 w-3 fill-amber-500 text-amber-500" aria-hidden="true" /> {a.rating.toFixed(1)}
                              </span>
                            ) : null}
                            {a.google_maps_uri ? (
                              <a
                                href={a.google_maps_uri}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 font-medium text-ocean-700 hover:underline"
                              >
                                Open in Maps <ExternalLink className="h-3 w-3" aria-hidden="true" />
                              </a>
                            ) : null}
                          </div>
                          {a.notes ? <p className="mt-1.5 rounded-lg bg-sand-50 px-2.5 py-1.5 text-xs text-sand-900">💡 {a.notes}</p> : null}
                        </div>
                      </div>
                      {idx < day.activities.length - 1 && a.route_to_next ? <RouteLeg route={a.route_to_next} /> : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">A free day — explore as you wish.</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
