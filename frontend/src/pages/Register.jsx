import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { UserRound, Mail, Sparkles, ArrowRight } from 'lucide-react';
import Button from '../components/ui/Button';
import { Input, PasswordInput } from '../components/ui/Form';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError } from '../lib/api';
import AuthAside from '../components/AuthAside';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const PASSWORD_RE = /^(?=.*[A-Za-z])(?=.*\d).{8,128}$/;

export default function Register() {
  const { register } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({ fullName: '', email: '', password: '', confirm: '' });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.fullName.trim() || form.fullName.trim().length > 120) errs.fullName = 'Enter your full name (max 120 characters).';
    if (!EMAIL_RE.test(form.email)) errs.email = 'Enter a valid email address.';
    if (!PASSWORD_RE.test(form.password)) {
      errs.password = '8–128 characters with at least one letter and one digit.';
    }
    if (form.confirm !== form.password) errs.confirm = 'Passwords do not match.';
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setBusy(true);
    try {
      await register(form.email.trim(), form.password, form.fullName.trim());
      toast.success('Account created', 'Welcome aboard — let\u2019s plan something great.');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Could not create the account. Please try again.';
      toast.error('Registration failed', msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-[calc(100svh-4rem)] lg:grid-cols-[1fr_0.9fr]">
      <div className="flex items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full max-w-md">
          <p className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-ocean-600">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            Smart Travel Planner
          </p>
          <h1 className="font-display text-3xl font-extrabold">Start your first journey</h1>
          <p className="mt-2 text-sm text-slate-600">
            Free account — your itineraries stay private and belong to you.
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
            <Input
              label="Full name"
              autoComplete="name"
              icon={UserRound}
              placeholder="Alex Morgan"
              value={form.fullName}
              onChange={set('fullName')}
              error={errors.fullName}
              required
            />
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              icon={Mail}
              placeholder="you@example.com"
              value={form.email}
              onChange={set('email')}
              error={errors.email}
              required
            />
            <PasswordInput
              id="reg-password"
              label="Password"
              autoComplete="new-password"
              placeholder="8+ characters, a letter and a digit"
              value={form.password}
              onChange={set('password')}
              error={errors.password}
              hint="Passwords are handled exclusively by Neon Auth — never stored by the app."
              required
            />
            <PasswordInput
              id="reg-confirm"
              label="Confirm password"
              autoComplete="new-password"
              placeholder="Repeat the password"
              value={form.confirm}
              onChange={set('confirm')}
              error={errors.confirm}
              required
            />
            <Button type="submit" loading={busy} className="w-full justify-center py-3 text-base">
              Create account
            </Button>
          </form>

          <p className="mt-6 text-sm text-slate-600">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-ocean-700 underline-offset-4 hover:underline">
              Sign in <ArrowRight className="inline h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </p>
        </div>
      </div>
      <AuthAside />
    </div>
  );
}
