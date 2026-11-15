import { motion, useReducedMotion } from 'framer-motion';

/** Scroll-triggered reveal — plays once, cheap for long pages. */
export default function Reveal({ children, delay = 0, y = 18, className = '', once = true }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, margin: '-48px' }}
      transition={{ duration: 0.5, delay, ease: [0.22, 0.61, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** Wraps page content with a soft enter transition (route-level). */
export function PageTransition({ children, className = '' }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.28, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  );
}

/** Section heading with eyebrow label. */
export function SectionHeading({ eyebrow, title, subtitle, center = false, light = false }) {
  return (
    <div className={`${center ? 'mx-auto max-w-2xl text-center' : 'max-w-2xl'} mb-10`}>
      {eyebrow ? (
        <p className={`mb-2 text-xs font-bold uppercase tracking-[0.18em] ${light ? 'text-ocean-300' : 'text-ocean-600'}`}>
          {eyebrow}
        </p>
      ) : null}
      <h2 className={`text-3xl font-bold sm:text-4xl ${light ? 'text-white' : ''}`}>{title}</h2>
      {subtitle ? <p className={`mt-3 text-base leading-relaxed ${light ? 'text-slate-300' : 'text-slate-600'}`}>{subtitle}</p> : null}
    </div>
  );
}
