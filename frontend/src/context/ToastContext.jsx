import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, Info, TriangleAlert, X } from 'lucide-react';

// ---------------------------------------------------------------------------
// Toast notifications — animated, accessible, auto-dismissing.
// ---------------------------------------------------------------------------

const ToastContext = createContext(null);
let nextId = 1;

const STYLES = {
  success: { icon: CheckCircle2, ring: 'border-ocean-500/30', bar: 'bg-ocean-500', iconColor: 'text-ocean-600' },
  error: { icon: TriangleAlert, ring: 'border-rose-500/30', bar: 'bg-rose-500', iconColor: 'text-rose-600' },
  info: { icon: Info, ring: 'border-navy-500/30', bar: 'bg-navy-700', iconColor: 'text-navy-700' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    const t = timers.current.get(id);
    if (t) {
      clearTimeout(t);
      timers.current.delete(id);
    }
    setToasts((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (type, title, message = '') => {
      const id = nextId++;
      setToasts((prev) => [...prev.slice(-3), { id, type, title, message }]);
      const timer = setTimeout(() => dismiss(id), 5200);
      timers.current.set(id, timer);
      return id;
    },
    [dismiss]
  );

  const api = useMemo(
    () => ({
      success: (title, message) => push('success', title, message),
      error: (title, message) => push('error', title, message),
      info: (title, message) => push('info', title, message),
      dismiss,
    }),
    [push, dismiss]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 top-4 z-[100] flex flex-col items-center gap-2 px-4 sm:top-6"
      >
        <AnimatePresence>
          {toasts.map((t) => {
            const s = STYLES[t.type] || STYLES.info;
            const Icon = s.icon;
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, y: -14, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.97 }}
                transition={{ duration: 0.22, ease: 'easeOut' }}
                className={`pointer-events-auto relative flex w-full max-w-md items-start gap-3 overflow-hidden rounded-xl border bg-white p-3.5 pr-10 shadow-lift ${s.ring}`}
                role="status"
              >
                <span className={`absolute inset-y-0 left-0 w-1 ${s.bar}`} aria-hidden="true" />
                <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${s.iconColor}`} aria-hidden="true" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-navy-950">{t.title}</p>
                  {t.message ? <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{t.message}</p> : null}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(t.id)}
                  className="absolute right-2.5 top-2.5 rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                  aria-label="Dismiss notification"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
