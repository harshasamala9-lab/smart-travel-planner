// ---------------------------------------------------------------------------
// Formatting helpers — dates, money, durations. No external dependencies.
// ---------------------------------------------------------------------------

const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function parseISODate(value) {
  if (!value) return null;
  const [y, m, d] = String(value).slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

export function toISODate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function todayISO() {
  return toISODate(new Date());
}

export function formatDate(iso) {
  const date = parseISODate(iso);
  if (!date) return String(iso || '—');
  return `${MONTH_SHORT[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

export function formatDateRange(startIso, endIso) {
  const s = parseISODate(startIso);
  const e = parseISODate(endIso);
  if (!s || !e) return '—';
  const sameMonth = s.getMonth() === e.getMonth() && s.getFullYear() === e.getFullYear();
  if (sameMonth) return `${MONTH_SHORT[s.getMonth()]} ${s.getDate()}–${e.getDate()}, ${e.getFullYear()}`;
  const sameYear = s.getFullYear() === e.getFullYear();
  return sameYear
    ? `${MONTH_SHORT[s.getMonth()]} ${s.getDate()} – ${MONTH_SHORT[e.getMonth()]} ${e.getDate()}, ${e.getFullYear()}`
    : `${formatDate(startIso)} – ${formatDate(endIso)}`;
}

export function tripNights(startIso, endIso) {
  const s = parseISODate(startIso);
  const e = parseISODate(endIso);
  if (!s || !e) return 0;
  return Math.max(0, Math.round((e - s) / 86400000));
}

export function tripDays(startIso, endIso) {
  return tripNights(startIso, endIso) + 1;
}

export function formatMoney(amount, currency = 'INR') {
  const n = Number(amount);
  if (!Number.isFinite(n)) return '—';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: n % 1 === 0 ? 0 : 2,
    }).format(n);
  } catch {
    return `${currency} ${n.toLocaleString()}`;
  }
}

export function formatMinutes(seconds) {
  const m = Math.round((seconds ?? 0) / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}

export function greeting() {
  const h = new Date().getHours();
  if (h < 5) return 'Up late planning?';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export function initials(name = '') {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('') || 'T';
}

/**
 * Trip lifecycle bucket used by My Trips filters.
 * Mirrors reality: dates + status decide the bucket.
 */
export function tripBucket(itinerary, now = new Date()) {
  const s = parseISODate(itinerary.start_date);
  const e = parseISODate(itinerary.end_date);
  const endOfDay = e ? new Date(e.getFullYear(), e.getMonth(), e.getDate(), 23, 59, 59) : null;
  if (itinerary.status === 'archived') return 'archived';
  if (itinerary.status === 'draft') return 'draft';
  if (s && s > now) return 'upcoming';
  if (endOfDay && endOfDay >= now) return 'active';
  return 'completed';
}

export function fileTimestamp() {
  return new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-');
}
