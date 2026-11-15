import { Link } from 'react-router-dom';
import { Compass, Sparkles, Briefcase, Info, Image as ImageIcon } from 'lucide-react';
import { imageCredits } from '../../lib/images';

export default function Footer() {
  const credits = imageCredits();
  return (
    <footer className="mt-20 border-t border-slate-200 bg-navy-950 text-slate-300">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2.5">
              <svg viewBox="0 0 64 64" className="h-9 w-9" aria-hidden="true">
                <defs>
                  <linearGradient id="lg-ft" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#06c19b" />
                    <stop offset="1" stopColor="#134e63" />
                  </linearGradient>
                </defs>
                <rect width="64" height="64" rx="16" fill="url(#lg-ft)" />
                <path d="M14 40 L28 36 L44 20 L46 22 L34 40 L38 52 L33 53 L29 42 L18 44 Z" fill="#fff" opacity="0.95" />
                <circle cx="47" cy="17" r="3.2" fill="#e7ab35" />
              </svg>
              <span className="font-display text-lg font-extrabold text-white">
                Smart<span className="text-ocean-400">Travel</span>
              </span>
            </div>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-slate-400">
              Day-by-day AI itineraries built on real Google Places data, Google Routes, live weather and honest,
              clearly-labelled budget estimates.
            </p>
          </div>
          <nav aria-label="Footer">
            <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Explore</h3>
            <ul className="mt-3 space-y-2.5 text-sm">
              <li><Link className="flex items-center gap-2 transition-colors hover:text-ocean-300" to="/explore"><Compass className="h-4 w-4" aria-hidden="true" /> Explore destinations</Link></li>
              <li><Link className="flex items-center gap-2 transition-colors hover:text-ocean-300" to="/planner"><Sparkles className="h-4 w-4" aria-hidden="true" /> AI trip planner</Link></li>
              <li><Link className="flex items-center gap-2 transition-colors hover:text-ocean-300" to="/itineraries"><Briefcase className="h-4 w-4" aria-hidden="true" /> My trips</Link></li>
            </ul>
          </nav>
          <div>
            <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
              <ImageIcon className="h-3.5 w-3.5" aria-hidden="true" /> Photography credits
            </h3>
            <ul className="mt-3 space-y-1.5 text-[11px] leading-relaxed text-slate-500">
              {credits.map((c) => (
                <li key={c}>{c}</li>
              ))}
              <li className="pt-1">Hero video: "Stunning Tropical Beach Aerial View" — Pexels (Pexels License).</li>
            </ul>
          </div>
        </div>
        <div className="mt-10 flex flex-col gap-3 border-t border-white/10 pt-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-1.5">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            All monetary values are planning estimates — no provider returns a verified live price.
          </p>
          <p>© {new Date().getFullYear()} Smart Travel Planner</p>
        </div>
      </div>
    </footer>
  );
}
