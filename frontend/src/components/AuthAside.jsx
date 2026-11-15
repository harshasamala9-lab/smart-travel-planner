import { IMAGES } from '../lib/images';
import { Plane, Brain, ShieldCheck } from 'lucide-react';

/** Visual panel beside the auth forms. */
export default function AuthAside() {
  return (
    <aside className="relative hidden overflow-hidden lg:block" aria-hidden="false">
      <img
        src={IMAGES.authPanel.src}
        alt="Mountain peaks rising above a sea of clouds"
        className="absolute inset-0 h-full w-full object-cover"
        loading="lazy"
        decoding="async"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-navy-950/90 via-navy-950/35 to-navy-950/20" />
      <div className="relative flex h-full flex-col justify-end p-10">
        <ul className="mb-8 space-y-4">
          {[
            { icon: Brain, text: 'AI itineraries from real Google Places data' },
            { icon: Plane, text: 'Share links and printable PDF trip books' },
            { icon: ShieldCheck, text: 'Sessions secured by Neon Auth (Better Auth)' },
          ].map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-3 text-sm font-medium text-slate-200">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/10 text-ocean-300 backdrop-blur">
                <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
              {text}
            </li>
          ))}
        </ul>
        <blockquote className="border-l-2 border-sand-400 pl-4">
          <p className="font-display text-xl font-bold leading-snug text-white">
            "The mountains are calling and I must go."
          </p>
          <footer className="mt-1 text-xs text-slate-400">— John Muir</footer>
        </blockquote>
      </div>
    </aside>
  );
}
