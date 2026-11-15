// ---------------------------------------------------------------------------
// Shared domain constants — all values mirror the backend enums exactly.
// ---------------------------------------------------------------------------

// India-first: INR is the default currency for all new trips and profiles.
// The remaining currencies stay selectable so worldwide trips can still be
// budgeted in local currency (mirrors the backend enum exactly).
export const CURRENCIES = [
  'INR', 'USD', 'EUR', 'GBP', 'AED', 'SGD', 'THB', 'JPY', 'AUD', 'CAD',
  'CHF', 'CNY', 'NZD', 'ZAR', 'KRW', 'BRL', 'MXN', 'SEK', 'NOK', 'DKK',
];

export const DEFAULT_CURRENCY = 'INR';

export const ACCOMMODATION_OPTIONS = [
  { value: 'none', label: 'No accommodation needed' },
  { value: 'hostel', label: 'Hostel' },
  { value: 'budget_hotel', label: 'Budget hotel' },
  { value: 'midrange_hotel', label: 'Mid-range hotel' },
  { value: 'luxury_hotel', label: 'Luxury hotel' },
  { value: 'apartment', label: 'Apartment / rental' },
  { value: 'homestay', label: 'Homestay' },
];

export const TRANSPORTATION_OPTIONS = [
  { value: 'none', label: 'No preference' },
  { value: 'walking', label: 'Walking' },
  { value: 'public_transport', label: 'Public transport' },
  { value: 'taxi_rideshare', label: 'Taxi / rideshare' },
  { value: 'rental_car', label: 'Rental car' },
  { value: 'mixed', label: 'Mixed' },
];

export const PACE_OPTIONS = [
  { value: 'relaxed', label: 'Relaxed — fewer, longer stops' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'packed', label: 'Packed — see as much as possible' },
];

export const BUDGET_LEVEL_OPTIONS = [
  { value: 'economy', label: 'Economy' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'premium', label: 'Premium' },
];

export const INTEREST_OPTIONS = [
  'history', 'food', 'art', 'culture', 'nature', 'beaches', 'nightlife',
  'shopping', 'adventure', 'architecture', 'museums', 'photography',
  'music', 'wildlife', 'wellness', 'literature', 'festivals', 'coffee',
];

export const ACTIVITY_OPTIONS = [
  'temples', 'markets', 'landmarks', 'walking tours', 'food tours', 'hiking',
  'beaches', 'museums', 'day trips', 'scenic viewpoints', 'parks', 'harbors',
];

export const DIETARY_OPTIONS = [
  'vegetarian', 'vegan', 'pescatarian', 'halal', 'kosher',
  'gluten_free', 'dairy_free', 'nut_allergy',
];

export const ITINERARY_STATUS = {
  draft: { label: 'Draft', class: 'bg-slate-200 text-slate-700' },
  generated: { label: 'Generated', class: 'bg-ocean-100 text-ocean-800' },
  saved: { label: 'Saved', class: 'bg-sand-200 text-sand-900' },
  archived: { label: 'Archived', class: 'bg-slate-200 text-slate-500' },
};

export const ACTIVITY_CATEGORY_META = {
  attraction: { icon: 'landmark', label: 'Attraction', color: 'bg-cyan-100 text-cyan-800' },
  restaurant: { icon: 'utensils', label: 'Food', color: 'bg-amber-100 text-amber-800' },
  hotel: { icon: 'bed', label: 'Stay', color: 'bg-violet-100 text-violet-800' },
  transport: { icon: 'bus', label: 'Transport', color: 'bg-slate-200 text-slate-700' },
  other: { icon: 'map-pin', label: 'Stop', color: 'bg-emerald-100 text-emerald-800' },
};

/**
 * Curated showcase destinations for the landing page and explore shortcuts.
 * Every image URL below is a free-license source verified at build time;
 * `attribution` is displayed in the footer for license compliance.
 */
export const SHOWCASE_DESTINATIONS = [
  { name: 'Kyoto', country: 'Japan', query: 'Kyoto', tag: 'Temples & tradition', imageKey: 'kyoto' },
  { name: 'Santorini', country: 'Greece', query: 'Santorini', tag: 'Island sunsets', imageKey: 'santorini' },
  { name: 'Paris', country: 'France', query: 'Paris', tag: 'Art & cafés', imageKey: 'paris' },
  { name: 'Bali', country: 'Indonesia', query: 'Bali', tag: 'Beaches & rice fields', imageKey: 'bali' },
  { name: 'New York', country: 'United States', query: 'New York', tag: 'The city skyline', imageKey: 'new-york' },
  { name: 'Rome', country: 'Italy', query: 'Rome', tag: 'Ancient wonders', imageKey: 'rome' },
  { name: 'Dubai', country: 'United Arab Emirates', query: 'Dubai', tag: 'Desert futurism', imageKey: 'dubai' },
  { name: 'Machu Picchu', country: 'Peru', query: 'Machu Picchu', tag: 'Lost citadel', imageKey: 'machu-picchu' },
  { name: 'Maldives', country: 'Maldives', query: 'Maldives', tag: 'Overwater escapes', imageKey: 'maldives' },
  { name: 'Tokyo', country: 'Japan', query: 'Tokyo', tag: 'Food & neon', imageKey: 'tokyo' },
  { name: 'Barcelona', country: 'Spain', query: 'Barcelona', tag: 'Gaudí & the sea', imageKey: 'barcelona' },
  { name: 'Cape Town', country: 'South Africa', query: 'Cape Town', tag: 'Mountain & ocean', imageKey: 'cape-town' },
  { name: 'Marrakesh', country: 'Morocco', query: 'Marrakesh', tag: 'Souks & riads', imageKey: 'marrakesh' },
  { name: 'Reykjavík', country: 'Iceland', query: 'Reykjavik', tag: 'Glaciers & aurora', imageKey: 'reykjavik' },
  { name: 'Jaipur', country: 'India', query: 'Jaipur', tag: 'Pink City forts', imageKey: 'jaipur' },
  { name: 'Hội An', country: 'Vietnam', query: 'Hoi An', tag: 'Lantern-lit lanes', imageKey: 'hoi-an' },
];

/** Quick discovery chips shown on Explore when no search is active. */
export const TRAVEL_STYLES = [
  { label: 'Beaches', query: 'beaches' },
  { label: 'Honeymoon', query: 'honeymoon' },
  { label: 'History', query: 'history' },
  { label: 'Food', query: 'food' },
  { label: 'Mountains', query: 'mountains' },
  { label: 'Wildlife', query: 'wildlife' },
  { label: 'Adventure', query: 'adventure' },
  { label: 'Wellness', query: 'wellness' },
];

export const MAX_TRIP_DAYS = 30;
export const MAX_TRAVELLERS = 20;
