import { CloudSun, CloudRain, Thermometer, CloudOff, Info } from 'lucide-react';

/** Weather panel with the backend's honest forecast-coverage disclosure. */
export default function WeatherCard({ weather }) {
  if (!weather) return null;
  const current = weather.current || {};
  const coverage = weather.forecast_covers_requested_dates;
  const daily = weather.daily_forecast || weather.forecast || [];

  return (
    <div className="card print-full p-5 sm:p-6">
      <h3 className="mb-4 flex items-center gap-2 font-display text-lg font-bold">
        <CloudSun className="h-5 w-5 text-ocean-600" aria-hidden="true" />
        Weather
      </h3>
      {current.temp_c != null || current.temp != null ? (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <p className="font-display text-3xl font-bold text-navy-950">
            {current.temp_c ?? current.temp}°{weather.units === 'imperial' ? 'F' : 'C'}
          </p>
          <div className="text-sm text-slate-600">
            <p className="font-semibold text-navy-950">{current.description || current.condition || 'Current conditions'}</p>
            {current.feels_like_c != null || current.feels_like != null ? (
              <p className="flex items-center gap-1 text-xs">
                <Thermometer className="h-3.5 w-3.5" aria-hidden="true" />
                Feels like {current.feels_like_c ?? current.feels_like}°
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {Array.isArray(daily) && daily.length ? (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {daily.slice(0, 8).map((d, i) => (
            <div key={i} className="rounded-xl bg-slate-50 p-3 text-center">
              <p className="text-[11px] font-bold uppercase text-slate-500">{String(d.date || '').slice(5)}</p>
              <p className="mt-1 font-display text-base font-bold text-navy-950">
                {d.max_temp_c ?? d.max_temp ?? '—'}° / {d.min_temp_c ?? d.min_temp ?? '—'}°
              </p>
              <p className="mt-0.5 flex items-center justify-center gap-1 text-[11px] text-slate-500">
                <CloudRain className="h-3 w-3" aria-hidden="true" />
                {d.precipitation_chance_mm ?? d.pop ?? 0}
                {typeof d.precipitation_chance_mm === 'number' ? '%' : 'mm'}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <p className={`mt-4 flex items-start gap-1.5 rounded-xl p-3 text-[11px] leading-relaxed ${coverage === true ? 'bg-ocean-50 text-ocean-800' : 'bg-amber-50 text-amber-800'}`}>
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        {coverage === true
          ? 'Forecast covers your full travel dates.'
          : coverage === false
            ? 'Heads-up: dates extend beyond the weather provider\'s forecast horizon — treat these values as indicative only.'
            : 'No reliable forecast data was available for these dates.'}
        {weather.source ? <span className="ml-auto opacity-60">{weather.source}</span> : null}
      </p>
    </div>
  );
}
