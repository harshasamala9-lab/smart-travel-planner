import { useEffect, useRef, useState } from 'react';
import { authPhotoFetch } from '../../lib/api';

// ---------------------------------------------------------------------------
// SmartImage — lazy, aspect-ratio-stable, shimmer placeholder, graceful
// fallback. Also supports the backend's auth-protected photo proxy
// (photoName → blob → objectURL) with a small FIFO cache.
// ---------------------------------------------------------------------------

const objectUrlCache = new Map(); // "photoName|maxWidth" -> url
const inflight = new Map();
const MAX_CACHE = 60;

function cacheKey(name, w) {
  return `${name}|${w}`;
}

function evictIfNeeded() {
  while (objectUrlCache.size >= MAX_CACHE) {
    const oldest = objectUrlCache.keys().next().value;
    URL.revokeObjectURL(objectUrlCache.get(oldest));
    objectUrlCache.delete(oldest);
  }
}

/** Resolve a Google Places photo resource name to a local object URL. */
export function fetchAuthPhoto(photoName, maxWidth = 800, signal) {
  const key = cacheKey(photoName, maxWidth);
  if (objectUrlCache.has(key)) return Promise.resolve(objectUrlCache.get(key));
  if (inflight.has(key)) return inflight.get(key);

  const promise = authPhotoFetch(photoName, maxWidth, signal)
    .then((url) => {
      objectUrlCache.set(key, url);
      evictIfNeeded();
      inflight.delete(key);
      return url;
    })
    .catch((err) => {
      inflight.delete(key);
      throw err;
    });
  inflight.set(key, promise);
  return promise;
}

/**
 * Render an image with loading placeholder and fallback.
 * @param {{src?:string, photoName?:string, alt:string, ratio?:string,
 *          className?:string, imgClassName?:string, eager?:boolean}} props
 */
export default function SmartImage({
  src,
  photoName,
  alt,
  ratio = 'aspect-[4/3]',
  className = '',
  imgClassName = '',
  eager = false,
  maxWidth = 800,
}) {
  const [authUrl, setAuthUrl] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    setLoaded(false);
    setFailed(false);
    setAuthUrl(null);
    if (!photoName) return undefined;
    fetchAuthPhoto(photoName, maxWidth)
      .then((url) => {
        if (alive.current) setAuthUrl(url);
      })
      .catch(() => {
        if (alive.current) setFailed(true);
      });
    return () => {
      alive.current = false;
    };
  }, [photoName, maxWidth]);

  const finalSrc = authUrl || src || null;
  const showImage = Boolean(finalSrc) && !failed;
  const showPlaceholder = !showImage || !loaded;

  return (
    <div className={`relative overflow-hidden bg-gradient-to-br from-navy-900 via-navy-800 to-ocean-900 ${ratio} ${className}`}>
      {showImage ? (
        <img
          src={finalSrc}
          alt={alt}
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          draggable="false"
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
          className={`h-full w-full object-cover transition-opacity duration-500 ${loaded ? 'opacity-100' : 'opacity-0'} ${imgClassName}`}
        />
      ) : (
        <span className="absolute inset-0 flex items-center justify-center text-3xl" role="img" aria-label={alt}>
          🗺️
        </span>
      )}
      {showPlaceholder && showImage ? <div className="skeleton absolute inset-0" aria-hidden="true" /> : null}
    </div>
  );
}
