import { useEffect, useState } from 'react';

/**
 * "AI planning" indicator — a slow orbiting SVG (not a blink) plus cycling
 * progress copy. Pauses instantly under prefers-reduced-motion and shows
 * static copy instead.
 */
const STEPS = [
  'Reading real Google Places data…',
  'Matching places to your interests…',
  'Ordering days around opening hours…',
  'Estimating an honest budget…',
  'Checking routes between stops…',
  'Polishing your itinerary…',
];

export default function AIThinking({ destination = 'your trip' }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) return undefined;
    const t = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 3400);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex flex-col items-center text-center">
      <svg viewBox="0 0 120 120" className="h-28 w-28" role="img" aria-label="AI is planning your itinerary">
        <circle cx="60" cy="60" r="52" fill="none" stroke="#e2ecf9" strokeWidth="3" />
        <circle cx="60" cy="60" r="34" fill="none" stroke="#0a1c39" strokeWidth="1.5" strokeDasharray="3 6" opacity="0.35" />
        <g className="origin-center" style={{ transformBox: 'fill-box', transformOrigin: 'center' }}>
          <animateTransform attributeName="transform" type="rotate" from="0 60 60" to="360 60 60" dur="7s" repeatCount="indefinite" />
          <circle cx="60" cy="8" r="6" fill="#06c19b" />
          <circle cx="112" cy="60" r="4" fill="#e7ab35" />
          <circle cx="60" cy="112" r="3" fill="#3778cd" />
        </g>
        <g>
          <circle cx="60" cy="60" r="16" fill="#effef9" />
          <path d="M54 66 L58 62 L64 68 L66 50 L70 66" fill="none" stroke="#06c19b" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </svg>
      <p className="mt-5 font-display text-lg font-bold text-navy-950">Crafting {destination}…</p>
      <p className="mt-1.5 h-5 text-sm text-slate-500" aria-live="polite">
        {STEPS[step]}
      </p>
    </div>
  );
}
