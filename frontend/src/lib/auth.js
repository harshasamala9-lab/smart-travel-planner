// ---------------------------------------------------------------------------
// Session token storage — the backend returns a 15-minute access JWT plus a
// 7-day session (refresh) token. Both are kept in localStorage; the API client
// transparently refreshes the access token when it expires.
// ---------------------------------------------------------------------------
const ACCESS_KEY = 'stp_access_token';
const REFRESH_KEY = 'stp_refresh_token';

export function getAccessToken() {
  try {
    return localStorage.getItem(ACCESS_KEY) || '';
  } catch {
    return '';
  }
}

export function getRefreshToken() {
  try {
    return localStorage.getItem(REFRESH_KEY) || '';
  } catch {
    return '';
  }
}

export function setSession(accessToken, refreshToken) {
  try {
    if (accessToken) localStorage.setItem(ACCESS_KEY, accessToken);
    if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
  } catch {
    /* storage unavailable (private mode) — session lives in memory only */
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* ignore */
  }
}

export function hasSession() {
  return Boolean(getAccessToken() || getRefreshToken());
}

/** Decode the JWT payload without verification (expiry hint only). */
export function decodeJwtPayload(token) {
  if (!token) return null;
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
    const bin = atob(padded);
    const json = decodeURIComponent(
      bin
        .split('')
        .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** True when the stored access token is missing or about to expire. */
export function accessNeedsRefresh(leaseSeconds = 30) {
  const token = getAccessToken();
  if (!token) return Boolean(getRefreshToken());
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return payload.exp * 1000 - Date.now() < leaseSeconds * 1000;
}
