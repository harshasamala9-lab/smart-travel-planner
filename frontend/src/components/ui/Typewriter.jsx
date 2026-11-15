import { useEffect, useRef, useState } from 'react';

/**
 * Types through a list of phrases, holds, erases, and continues.
 * Pure JS timing driven by refs (no stale closures), cleaned up on unmount,
 * and fully disabled under prefers-reduced-motion.
 */
export default function Typewriter({ phrases, typeMs = 55, eraseMs = 28, holdMs = 2200, className = '' }) {
  const [text, setText] = useState('');
  const state = useRef({ phrase: 0, char: 0, phase: 'type', timer: 0 });

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setText(phrases[0] || '');
      return undefined;
    }
    let cancelled = false;
    state.current = { phrase: 0, char: 0, phase: 'type', timer: 0 };

    const step = () => {
      if (cancelled) return;
      const s = state.current;
      const current = phrases[s.phrase] || '';

      if (s.phase === 'type') {
        if (s.char < current.length) {
          s.char += 1;
          setText(current.slice(0, s.char));
          s.timer = setTimeout(step, typeMs);
          return;
        }
        s.phase = 'hold';
        s.timer = setTimeout(step, holdMs);
        return;
      }
      if (s.phase === 'hold') {
        s.phase = 'erase';
        step();
        return;
      }
      // erase
      if (s.char > 0) {
        s.char -= 1;
        setText(current.slice(0, s.char));
        s.timer = setTimeout(step, eraseMs);
        return;
      }
      s.phrase = (s.phrase + 1) % phrases.length;
      s.phase = 'type';
      s.timer = setTimeout(step, 350);
    };

    state.current.timer = setTimeout(step, 400);
    return () => {
      cancelled = true;
      clearTimeout(state.current.timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phrases.join('|')]);

  const holding = state.current.phase === 'hold';

  return (
    <span className={className}>
      {text}
      <span
        aria-hidden="true"
        className="ml-1 inline-block h-[0.9em] w-[3px] translate-y-[0.08em] rounded-full bg-sand-400 transition-opacity duration-300"
        style={{ opacity: holding ? 1 : 0.75 }}
      />
      <span className="sr-only">{phrases[0]}</span>
    </span>
  );
}
