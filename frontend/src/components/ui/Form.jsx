import { forwardRef, useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export const Input = forwardRef(function Input(
  { label, error, hint, icon: Icon, type = 'text', className = '', id, ...rest },
  ref
) {
  const autoId = useId();
  const inputId = id || autoId;
  const errId = `${inputId}-err`;
  const hintId = `${inputId}-hint`;
  return (
    <div className={className}>
      {label ? (
        <label htmlFor={inputId} className="label">
          {label}
        </label>
      ) : null}
      <div className="relative">
        {Icon ? (
          <Icon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
        ) : null}
        <input
          ref={ref}
          id={inputId}
          type={type}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errId : hint ? hintId : undefined}
          className={`input ${Icon ? 'pl-10' : ''} ${error ? 'input-error' : ''}`}
          {...rest}
        />
      </div>
      {error ? (
        <p id={errId} className="field-error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="hint">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

export function PasswordInput({ label, error, hint, className = '', ...rest }) {
  const [show, setShow] = useState(false);
  return (
    <div className={className}>
      {label ? <label htmlFor={rest.id} className="label">{label}</label> : null}
      <div className="relative">
        <input
          type={show ? 'text' : 'password'}
          aria-invalid={Boolean(error)}
          className={`input pr-11 ${error ? 'input-error' : ''}`}
          {...rest}
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          aria-label={show ? 'Hide password' : 'Show password'}
          aria-pressed={show}
        >
          {show ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="hint">{hint}</p>
      ) : null}
    </div>
  );
}

export const Textarea = forwardRef(function Textarea(
  { label, error, hint, className = '', id, rows = 3, ...rest },
  ref
) {
  const autoId = useId();
  const areaId = id || autoId;
  return (
    <div className={className}>
      {label ? (
        <label htmlFor={areaId} className="label">
          {label}
        </label>
      ) : null}
      <textarea
        ref={ref}
        id={areaId}
        rows={rows}
        aria-invalid={Boolean(error)}
        className={`input resize-y ${error ? 'input-error' : ''}`}
        {...rest}
      />
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="hint">{hint}</p>
      ) : null}
    </div>
  );
});

export const Select = forwardRef(function Select(
  { label, error, hint, options = [], placeholder, className = '', id, children, ...rest },
  ref
) {
  const autoId = useId();
  const selectId = id || autoId;
  return (
    <div className={className}>
      {label ? (
        <label htmlFor={selectId} className="label">
          {label}
        </label>
      ) : null}
      <select
        ref={ref}
        id={selectId}
        aria-invalid={Boolean(error)}
        className={`input cursor-pointer appearance-none bg-[url("data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2216%22%20height%3D%2216%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2364748b%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E")] bg-[position:right_0.9rem_center] bg-no-repeat pr-10 ${error ? 'input-error' : ''}`}
        {...rest}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options.map((o) =>
          typeof o === 'string' ? (
            <option key={o} value={o}>
              {o}
            </option>
          ) : (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          )
        )}
        {children}
      </select>
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="hint">{hint}</p>
      ) : null}
    </div>
  );
});
