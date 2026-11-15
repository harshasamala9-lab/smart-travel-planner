import { Wallet, Users, Scale, CircleAlert, Info } from 'lucide-react';
import { formatMoney } from '../../lib/format';

const LINE_META = [
  ['transportation', 'Transportation', 'bg-ocean-500'],
  ['accommodation', 'Accommodation', 'bg-navy-700'],
  ['food', 'Food', 'bg-sand-400'],
  ['activities', 'Activities', 'bg-emerald-500'],
  ['other', 'Other', 'bg-slate-400'],
];

/** Budget panel — every value shown is the backend's planning estimate. */
export default function BudgetBreakdown({ budget, totalBudget, currency = 'USD' }) {
  if (!budget) return null;
  const cur = budget.currency || currency;
  const max = Math.max(...LINE_META.map(([k]) => budget.line_items?.[k] || 0), 1);

  return (
    <div className="card print-full p-5 sm:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 font-display text-lg font-bold">
          <Wallet className="h-5 w-5 text-ocean-600" aria-hidden="true" />
          Budget estimate
        </h3>
        <span className="badge bg-slate-100 text-slate-600" title="No provider returns a verified live price">
          {budget.cost_type === 'estimated' ? 'Planning estimate' : budget.cost_type}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: Wallet, label: 'Estimated total', value: formatMoney(budget.total, cur) },
          { icon: Users, label: 'Per person', value: formatMoney(budget.per_person, cur) },
          {
            icon: budget.over_budget ? CircleAlert : Scale,
            label: budget.over_budget ? 'Over your budget' : 'Remaining',
            value: formatMoney(Math.abs(budget.remaining), cur),
            danger: budget.over_budget,
          },
        ].map(({ icon: Icon, label, value, danger }) => (
          <div key={label} className={`rounded-xl border p-4 ${danger ? 'border-rose-200 bg-rose-50' : 'border-slate-100 bg-slate-50'}`}>
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <Icon className={`h-3.5 w-3.5 ${danger ? 'text-rose-500' : 'text-ocean-600'}`} aria-hidden="true" />
              {label}
            </p>
            <p className={`mt-1 font-display text-xl font-bold ${danger ? 'text-rose-600' : 'text-navy-950'}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Line items */}
      <div className="mt-5 space-y-3">
        {LINE_META.map(([key, label, color]) => {
          const v = budget.line_items?.[key] || 0;
          const pct = Math.round((v / max) * 100);
          return (
            <div key={key}>
              <div className="mb-1 flex items-baseline justify-between text-sm">
                <span className="font-medium text-navy-950">{label}</span>
                <span className="font-semibold text-slate-600">{formatMoney(v, cur)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full ${color} transition-[width] duration-700 ease-out`}
                  style={{ width: `${Math.max(pct, v > 0 ? 6 : 0)}%` }}
                  role="presentation"
                />
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-xs text-slate-500">
        Your stated budget: <strong className="text-navy-950">{formatMoney(budget.total_budget ?? totalBudget, cur)}</strong> ·{' '}
        {budget.utilization_percent != null ? `${budget.utilization_percent.toFixed(0)}% used` : ''}
      </p>

      {budget.warning ? (
        <div className="mt-4 flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-xs leading-relaxed text-amber-800">
          <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {budget.warning}
        </div>
      ) : null}

      {budget.assumptions?.length ? (
        <details className="mt-4 rounded-xl bg-slate-50 p-3">
          <summary className="cursor-pointer text-xs font-semibold text-navy-950">How this estimate was built</summary>
          <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-slate-600">
            {budget.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {budget.disclaimer ? (
        <p className="mt-4 flex items-start gap-1.5 border-t border-slate-100 pt-3 text-[11px] leading-relaxed text-slate-400">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {budget.disclaimer}
        </p>
      ) : null}
    </div>
  );
}
