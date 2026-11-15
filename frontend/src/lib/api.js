// ---------------------------------------------------------------------------
// Central API client for the Smart Travel Planner backend.
//
// - Reads VITE_API_BASE_URL (empty = same-origin; the Vite dev server proxies
//   /api to http://127.0.0.1:8000).
// - Attaches the bearer access token to protected routes.
// - Transparently refreshes the session on 401 once, then retries.
// - Parses the backend's stable error envelope:
//     { "error": { "code", "message", "details", "request_id" } }
// ---------------------------------------------------------------------------

import {
  getAccessToken,
  getRefreshToken,
  setSession,
  clearSession,
  accessNeedsRefresh,
} from './auth';

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

/** Human-readable copy for backend error codes. */
const CODE_COPY = {
  authentication_required: 'Your session has expired. Please sign in again.',
  permission_denied: "You don't have access to this resource.",
  not_found: 'We could not find that item. It may have been deleted.',
  conflict: 'That already exists for your account.',
  validation_error: 'Some details need a quick fix before we can continue.',
  rate_limit_exceeded: 'Too many attempts. Please wait a moment and try again.',
  payload_too_large: 'That request is too large.',
  service_unavailable: 'This feature is not configured on the server yet.',
  request_timeout: 'The server took too long. Please try again.',
  ai_invalid_output: 'The AI planner could not produce a valid route this time. Try adjusting your trip.',
  internal_error: 'Something went wrong on our side. Please try again.',
};

export class ApiError extends Error {
  constructor(status, code, message, details, requestId) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || 'unknown';
    this.details = details;
    this.requestId = requestId;
  }

  /** First safe field message from a validation_error envelope, if any. */
  firstFieldMessage() {
    const errs = this.details?.errors || this.details?.errors?.errors;
    if (Array.isArray(errs) && errs.length) {
      const e = errs[0];
      return e.msg || e.message || this.message;
    }
    return null;
  }
}

/** Normalize any thrown value into an ApiError with friendly copy. */
export function toApiError(err) {
  if (err instanceof ApiError) return err;
  if (err?.name === 'AbortError') return err;
  const network = new ApiError(0, 'network_error', 'No connection to the travel server. Check that the backend is running.');
  return network;
}

let refreshInFlight = null;

/** Exchange the stored session token for a fresh access JWT. */
export async function refreshSession() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = await res.json();
        if (!data?.session?.access_token) return false;
        setSession(data.session.access_token, data.session.refresh_token || refreshToken);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

/** Force a logout everywhere: revoke the session server-side, then wipe local. */
export async function destroySession() {
  const refreshToken = getRefreshToken();
  try {
    if (refreshToken) {
      await fetch(`${BASE}/api/v1/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    }
  } catch {
    /* best effort — the local session is cleared regardless */
  }
  clearSession();
}

/**
 * Core request helper.
 * @param {string} path  e.g. "/api/v1/users/me"
 */
async function request(path, { method = 'GET', body, auth = true, signal, blob = false, retry = true } = {}) {
  // Proactively refresh an access token that is about to expire.
  if (auth && accessNeedsRefresh()) {
    await refreshSession();
  }

  const headers = { Accept: blob ? 'application/pdf, image/*, text/csv' : 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = getAccessToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
      credentials: 'omit',
    });
  } catch (err) {
    if (err?.name === 'AbortError') throw err;
    throw new ApiError(0, 'network_error', 'No connection to the travel server. Check that the backend is running.');
  }

  if (res.ok) return blob ? res : res.json().catch(() => ({}));

  // 401 → refresh once and retry the original request.
  if (res.status === 401 && auth && retry) {
    const refreshed = await refreshSession();
    if (refreshed) return request(path, { method, body, auth, signal, blob, retry: false });
    clearSession();
  }

  let code = 'unknown';
  let message = res.statusText || 'Request failed.';
  let details;
  let requestId = res.headers.get('X-Request-ID') || undefined;

  if (res.status !== 204) {
    try {
      const data = await res.json();
      if (data?.error) {
        code = data.error.code || code;
        message = data.error.message || message;
        details = data.error.details;
        requestId = data.error.request_id || requestId;
      } else {
        message = data?.detail || data?.message || message;
      }
    } catch {
      /* non-JSON error body */
    }
  }

  if (CODE_COPY[code]) {
    const raw = message;
    message = CODE_COPY[code];
    if (code === 'validation_error' && details?.errors?.length) {
      const fe = details.errors[0];
      const loc = Array.isArray(fe.loc) ? fe.loc.slice(-1)[0] : undefined;
      message = loc ? `${String(loc)}: ${fe.msg || 'invalid value'}` : message;
    } else if (code === 'validation_error' && typeof raw === 'string' && raw.length && raw.length < 200) {
      message = raw;
    }
  }

  throw new ApiError(res.status, code, message, details, requestId);
}

// ---------------------------------------------------------------------------
// Domain services
// ---------------------------------------------------------------------------

const v1 = '/api/v1';

export const authAPI = {
  register: (payload, signal) => request(`${v1}/auth/register`, { method: 'POST', body: payload, auth: false, signal }),
  login: (payload, signal) => request(`${v1}/auth/login`, { method: 'POST', body: payload, auth: false, signal }),
  googleUrl: (redirectTo, signal) =>
    request(`${v1}/auth/google/url?redirect_to=${encodeURIComponent(redirectTo)}`, { auth: false, signal }),
};

export const usersAPI = {
  me: (signal) => request(`${v1}/users/me`, { signal }),
  updateMe: (payload, signal) => request(`${v1}/users/me`, { method: 'PATCH', body: payload, signal }),
  preferences: (signal) => request(`${v1}/users/me/preferences`, { signal }),
  savePreferences: (payload, signal) => request(`${v1}/users/me/preferences`, { method: 'PUT', body: payload, signal }),
  history: (limit = 20, offset = 0, signal) => request(`${v1}/users/me/history?limit=${limit}&offset=${offset}`, { signal }),
  savedDestinations: (signal) => request(`${v1}/users/me/saved-destinations`, { signal }),
  saveDestination: (payload, signal) => request(`${v1}/users/me/saved-destinations`, { method: 'POST', body: payload, signal }),
  removeSavedDestination: (placeId, signal) =>
    request(`${v1}/users/me/saved-destinations/${encodeURIComponent(placeId)}`, { method: 'DELETE', signal }),
};

export const destinationsAPI = {
  search: (query, limit = 10, signal, category = 'all') => {
    const params = new URLSearchParams({ query, limit: String(limit) });
    if (category && category !== 'all') params.set('category', category);
    return request(`${v1}/destinations/search?${params.toString()}`, { signal });
  },
  featured: (limit = 12, category = 'all', signal) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (category && category !== 'all') params.set('category', category);
    return request(`${v1}/destinations/featured?${params.toString()}`, { auth: false, signal });
  },
  details: (placeId, signal) => request(`${v1}/destinations/${encodeURIComponent(placeId)}`, { signal }),
  /** URL for the photo proxy — requires a bearer header, so fetch as blob. */
  photoUrl: (photoName, maxWidth = 1200) =>
    `${v1}/destinations/photo?photo_name=${encodeURIComponent(photoName)}&max_width=${maxWidth}`,
  nearby: (placeId, kind = 'attractions', params = {}, signal) => {
    const qs = new URLSearchParams(params).toString();
    return request(`${v1}/destinations/${encodeURIComponent(placeId)}/${kind}${qs ? `?${qs}` : ''}`, { signal });
  },
  route: (payload, signal) => request(`${v1}/destinations/route`, { method: 'POST', body: payload, signal }),
};

export const itinerariesAPI = {
  generate: (payload, signal) => request(`${v1}/itineraries/generate`, { method: 'POST', body: payload, signal, timeoutHint: 'long' }),
  list: (limit = 50, offset = 0, signal) => request(`${v1}/itineraries?limit=${limit}&offset=${offset}`, { signal }),
  get: (id, signal) => request(`${v1}/itineraries/${id}`, { signal }),
  update: (id, payload, signal) => request(`${v1}/itineraries/${id}`, { method: 'PATCH', body: payload, signal }),
  remove: (id, signal) => request(`${v1}/itineraries/${id}`, { method: 'DELETE', signal }),
  createShare: (id, expiresInDays = 7, signal) =>
    request(`${v1}/itineraries/${id}/share`, { method: 'POST', body: { expires_in_days: expiresInDays }, signal }),
  listShares: (id, signal) => request(`${v1}/itineraries/${id}/shares`, { signal }),
  revokeShares: (id, signal) => request(`${v1}/itineraries/${id}/shares`, { method: 'DELETE', signal }),
  /** Raw response for PDF download (blob). */
  pdf: (id, signal) => request(`${v1}/itineraries/${id}/export/pdf`, { blob: true, signal }),
};

export const recommendationsAPI = {
  create: (payload, signal) => request(`${v1}/recommendations/`, { method: 'POST', body: payload, signal }),
};

export const weatherAPI = {
  get: (destination, params = {}, signal) => {
    const qs = new URLSearchParams(params).toString();
    return request(`${v1}/weather/${encodeURIComponent(destination)}${qs ? `?${qs}` : ''}`, { signal });
  },
};

export const notificationsAPI = {
  list: (params = {}, signal) => {
    const qs = new URLSearchParams({ unread_only: 'false', limit: '20', offset: '0', ...params }).toString();
    return request(`${v1}/notifications?${qs}`, { signal });
  },
  markAllRead: (signal) => request(`${v1}/notifications/read-all`, { method: 'POST', signal }),
  markRead: (id, signal) => request(`${v1}/notifications/${id}/read`, { method: 'PATCH', signal }),
  remove: (id, signal) => request(`${v1}/notifications/${id}`, { method: 'DELETE', signal }),
};

export const analyticsAPI = {
  me: (signal) => request(`${v1}/analytics/me`, { signal }),
  exportCsv: (signal) => request(`${v1}/analytics/me/export.csv`, { blob: true, signal }),
};

export const sharedAPI = {
  get: (token, signal) => request(`${v1}/shared/itineraries/${encodeURIComponent(token)}`, { auth: false, signal }),
};

/**
 * Fetch a Google Places photo through the backend proxy as an object URL.
 * The photo route requires the bearer header, so plain <img src> cannot be
 * used directly. Returns a blob object URL ready for <img>.
 */
export async function authPhotoFetch(photoName, maxWidth = 800, signal) {
  const res = await request(`${v1}/destinations/photo?photo_name=${encodeURIComponent(photoName)}&max_width=${maxWidth}`, {
    blob: true,
    signal,
  });
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export { BASE };
