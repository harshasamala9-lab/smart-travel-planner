import { useId, useMemo } from 'react';
import { Compass, ExternalLink, MapPin, Navigation } from 'lucide-react';

/**
 * A lightweight animated travel map.
 *
 * It deliberately does not embed Google Maps: no third-party JavaScript, no
 * layout shift, no client-side API key. The supplied Google key stays on the
 * server where it powers Places/Routes. This component projects coordinates
 * into a branded SVG and animates the route, markers and compass with native
 * SVG/CSS so it stays smooth on low-end phones.
 */
export default function AnimatedMap({
  title = 'Trip map',
  latitude,
  longitude,
  points = [],
  className = '',
  height = 'min-h-[260px]',
}) {
  const gradientId = useId().replace(/:/g, '');
  const gridId = `grid-${gradientId}`;

  const validPoints = useMemo(() => {
    const items = [];
    if (Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude))) {
      items.push({ name: title, latitude: Number(latitude), longitude: Number(longitude) });
    }
    for (const point of points) {
      if (
        Number.isFinite(Number(point?.latitude)) &&
        Number.isFinite(Number(point?.longitude))
      ) {
        items.push({
          name: point.name || 'Stop',
          latitude: Number(point.latitude),
          longitude: Number(point.longitude),
        });
      }
    }
    return items;
  }, [latitude, longitude, points, title]);

  const geometry = useMemo(() => {
    const width = 600;
    const frameHeight = 320;
    const pad = 54;
    if (!validPoints.length) return null;
    const lats = validPoints.map((point) => point.latitude);
    const lngs = validPoints.map((point) => point.longitude);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const latSpan = Math.max(maxLat - minLat, 0.02);
    const lngSpan = Math.max(maxLng - minLng, 0.02);
    const projected = validPoints.map((point) => ({
      ...point,
      x: pad + ((point.longitude - minLng) / lngSpan) * (width - pad * 2),
      y: pad + ((maxLat - point.latitude) / latSpan) * (frameHeight - pad * 2),
    }));
    if (projected.length === 1) {
      projected[0] = { ...projected[0], x: width / 2, y: frameHeight / 2 };
    }
    const path = projected
      .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
      .join(' ');
    return { width, height: frameHeight, points: projected, path };
  }, [validPoints]);

  const mapsUrl =
    validPoints.length > 0
      ? validPoints.length === 1
        ? `https://www.google.com/maps/search/?api=1&query=${validPoints[0].latitude},${validPoints[0].longitude}`
        : `https://www.google.com/maps/dir/?api=1&origin=${validPoints[0].latitude},${validPoints[0].longitude}&destination=${
            validPoints[validPoints.length - 1].latitude
          },${validPoints[validPoints.length - 1].longitude}`
      : null;

  if (!geometry) {
    return (
      <div className={`card flex ${height} flex-col items-center justify-center gap-2 p-6 text-center ${className}`}>
        <Compass className="h-9 w-9 text-ocean-300" aria-hidden="true" />
        <p className="text-sm font-semibold text-navy-950">Map preview unavailable</p>
        <p className="max-w-xs text-xs leading-relaxed text-slate-500">
          This place has no verified coordinates yet. The guide and itinerary still work.
        </p>
      </div>
    );
  }

  const { width, height: frameHeight, points: mapped, path } = geometry;

  return (
    <div className={`card group relative overflow-hidden ${height} ${className}`}>
      <svg
        viewBox={`0 0 ${width} ${frameHeight}`}
        className="absolute inset-0 h-full w-full"
        role="img"
        aria-label={`Animated map for ${title}`}
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#071a33" />
            <stop offset="55%" stopColor="#0b2c50" />
            <stop offset="100%" stopColor="#0e4d66" />
          </linearGradient>
          <pattern id={gridId} width="46" height="46" patternUnits="userSpaceOnUse">
            <path d="M 46 0 L 0 0 0 46" fill="none" stroke="rgba(125,211,252,0.13)" strokeWidth="1" />
          </pattern>
          <filter id={`glow-${gradientId}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect width={width} height={frameHeight} fill={`url(#${gradientId})`} />
        <rect width={width} height={frameHeight} fill={`url(#${gridId})`} />
        <g opacity="0.5">
          <path d="M -20 230 C 90 190 130 250 220 220 S 360 150 470 205 S 580 180 640 210 L 640 340 L -20 340 Z" fill="#134e63" />
          <path d="M -20 90 C 70 60 120 110 200 80 S 330 30 410 70 S 530 50 640 85 L 640 -20 L -20 -20 Z" fill="#0a3d5c" />
        </g>

        {/* Decorative contour rings around the primary marker. */}
        {mapped[0] ? (
          <g opacity="0.45">
            {[28, 48, 70].map((radius) => (
              <circle
                key={radius}
                cx={mapped[0].x}
                cy={mapped[0].y}
                r={radius}
                fill="none"
                stroke="#5eead4"
                strokeWidth="1"
                strokeDasharray="4 7"
                className="map-ring"
                style={{ animationDelay: `${radius * 18}ms` }}
              />
            ))}
          </g>
        ) : null}

        {mapped.length > 1 ? (
          <>
            <path
              d={path}
              fill="none"
              stroke="#5eead4"
              strokeWidth="7"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.22"
            />
            <path
              d={path}
              fill="none"
              stroke="#99f6e4"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="map-route"
              style={{ strokeDasharray: '10 8' }}
            />
            <circle r="5" fill="#fef3c7" filter={`url(#glow-${gradientId})`}>
              <animateMotion dur="7s" repeatCount="indefinite" path={path} rotate="auto" />
            </circle>
          </>
        ) : null}

        {mapped.map((point, index) => (
          <g key={`${point.name}-${index}`} transform={`translate(${point.x} ${point.y})`}>
            <circle r="16" fill="#0f766e" opacity="0.25" className="map-pulse" />
            <circle r="8" fill="#fbbf24" stroke="#fff7ed" strokeWidth="2.5" />
            <text
              y={index === 0 ? -20 : 26}
              textAnchor="middle"
              fill="#f8fafc"
              fontSize="12"
              fontWeight="700"
              style={{ paintOrder: 'stroke', stroke: 'rgba(2,6,23,0.75)', strokeWidth: 4 }}
            >
              {index === 0 ? 'Start' : index === mapped.length - 1 ? 'Finish' : index}
            </text>
          </g>
        ))}
      </svg>

      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between p-4">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-950/55 px-3 py-1.5 text-[11px] font-bold uppercase tracking-wide text-teal-200 backdrop-blur">
          <Navigation className="h-3 w-3" aria-hidden="true" /> Animated route
        </span>
        <span className="map-compass inline-flex h-9 w-9 items-center justify-center rounded-full bg-slate-950/45 text-teal-200 backdrop-blur">
          <Compass className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>

      <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-end justify-between gap-2 bg-gradient-to-t from-slate-950/80 to-transparent p-4 pt-10">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{title}</p>
          <p className="mt-0.5 flex items-center gap-1 text-[11px] text-slate-300">
            <MapPin className="h-3 w-3" aria-hidden="true" />
            {Number(latitude).toFixed(3)}, {Number(longitude).toFixed(3)}
            {mapped.length > 1 ? ` · ${mapped.length - 1} stop${mapped.length > 2 ? 's' : ''}` : ''}
          </p>
        </div>
        {mapsUrl ? (
          <a
            href={mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="pointer-events-auto inline-flex items-center gap-1.5 rounded-lg bg-white/95 px-2.5 py-1.5 text-[11px] font-bold text-navy-950 shadow-soft transition hover:bg-white"
          >
            Open in Google Maps <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
        ) : null}
      </div>
    </div>
  );
}
