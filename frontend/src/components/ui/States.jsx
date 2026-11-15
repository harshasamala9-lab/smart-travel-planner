import { Compass, CloudOff, Loader2 } from 'lucide-react';
import Button from './Button';

/** Friendly empty state with an optional action. */
export function EmptyState({ icon: Icon = Compass, title, message, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-14 text-center ${className}`}>
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-ocean-50 text-ocean-600">
        <Icon className="h-7 w-7" aria-hidden="true" />
      </div>
      <h3 className="text-base font-bold text-navy-950">{title}</h3>
      {message ? <p className="mt-1.5 max-w-sm text-sm text-slate-500">{message}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/** Error state with retry. Raw backend details are never shown. */
export function ErrorState({ message = 'Something went wrong while loading this view.', onRetry, busy = false, compact = false }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-2xl bg-rose-50/70 px-6 text-center ${compact ? 'py-8' : 'py-14'}`}>
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-100 text-rose-600">
        <CloudOff className="h-7 w-7" aria-hidden="true" />
      </div>
      <p className={`font-semibold text-navy-950 ${compact ? 'text-sm' : 'text-base'}`}>{message}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
          Try again
        </Button>
      ) : null}
    </div>
  );
}

/** Inline skeleton building blocks. */
export function SkeletonBox({ className = '' }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function CardSkeleton({ lines = 3, className = '' }) {
  return (
    <div className={`card p-5 ${className}`}>
      <div className="flex items-center gap-3">
        <SkeletonBox className="h-11 w-11 rounded-xl" />
        <div className="flex-1 space-y-2">
          <SkeletonBox className="h-3.5 w-2/3" />
          <SkeletonBox className="h-3 w-1/3" />
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonBox key={i} className="h-3" style={undefined} />
        ))}
      </div>
    </div>
  );
}
