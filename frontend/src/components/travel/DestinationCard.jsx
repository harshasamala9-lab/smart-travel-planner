import { Link } from 'react-router-dom';
import { MapPin, Star, DollarSign, CalendarRange, BookOpen } from 'lucide-react';
import SmartImage from '../ui/SmartImage';

const PRICE_LABEL = { free: 'Free', inexpensive: '€', moderate: '€€', expensive: '€€€', very_expensive: '€€€€' };

const TRAVEL_TYPE_LABEL = {
  city: 'City',
  beach: 'Beach',
  island: 'Island',
  nature: 'Nature',
  mountain: 'Mountains',
  historical: 'Historic',
  food: 'Food',
  stay: 'Stay',
  attraction: 'Attraction',
};

/** Destination card: curated travel guides or live Google Places results. */
export default function DestinationCard({ place, className = '' }) {
  const photoName = place.photo_names?.[0] || null;
  const typeLabel = TRAVEL_TYPE_LABEL[place.travel_type];
  const isCurated = Boolean(place.image_url);

  return (
    <Link
      to={`/destinations/${encodeURIComponent(place.place_id)}`}
      className={`card card-hover group block overflow-hidden ${className}`}
      aria-label={`Open ${place.name}`}
    >
      <div className="relative">
        <SmartImage
          src={place.image_url || undefined}
          photoName={photoName}
          alt={place.image_alt || place.name}
          ratio="aspect-[4/3]"
          imgClassName="transition-transform duration-500 group-hover:scale-[1.04]"
        />
        {typeLabel || isCurated ? (
          <div className="absolute left-2.5 top-2.5 flex flex-wrap gap-1.5">
            {typeLabel ? (
              <span className="rounded-full bg-navy-950/70 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white backdrop-blur-sm">
                {typeLabel}
              </span>
            ) : null}
            {isCurated ? (
              <span className="flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ocean-800 backdrop-blur-sm">
                <BookOpen className="h-2.5 w-2.5" aria-hidden="true" /> Guide
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="p-4">
        <h3 className="line-clamp-1 font-display text-[15px] font-bold text-navy-950">{place.name}</h3>
        <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
          <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span className="line-clamp-1">
            {place.country || place.formatted_address || 'Location on the map'}
          </span>
        </p>
        {place.description ? (
          <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500">{place.description}</p>
        ) : null}
        <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {place.rating ? (
            <span className="flex items-center gap-1 font-semibold text-amber-600">
              <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" aria-hidden="true" />
              {place.rating.toFixed(1)}
              {place.user_rating_count ? <span className="font-normal text-slate-400">({place.user_rating_count.toLocaleString()})</span> : null}
            </span>
          ) : null}
          {place.price_level ? (
            <span className="flex items-center gap-0.5 text-slate-500">
              <DollarSign className="h-3.5 w-3.5" aria-hidden="true" />
              {PRICE_LABEL[place.price_level] || place.price_level}
            </span>
          ) : null}
          {place.open_now != null ? (
            <span className={place.open_now ? 'font-semibold text-ocean-700' : 'text-rose-500'}>
              {place.open_now ? 'Open now' : 'Closed'}
            </span>
          ) : null}
          {place.best_time ? (
            <span className="flex items-center gap-1 text-slate-500">
              <CalendarRange className="h-3.5 w-3.5" aria-hidden="true" />
              {place.best_time}
            </span>
          ) : null}
        </div>
      </div>
    </Link>
  );
}
