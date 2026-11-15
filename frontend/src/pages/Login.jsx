import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { LogIn, Mail, Sparkles, ArrowRight } from 'lucide-react';
import Button from '../components/ui/Button';
import { Input, PasswordInput } from '../components/ui/Form';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError } from '../lib/api';
import AuthAside from '../components/AuthAside';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || '/dashboard';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!EMAIL_RE.test(email)) errs.email = 'Enter a valid email address.';
    if (!password) errs.password = 'Enter your password.';
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setBusy(true);
    try {
      await login(email.trim(), password);
      toast.success('Welcome back!', 'Your trips are ready.');
      navigate(from, { replace: true });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Could not sign in. Please try again.';
      toast.error('Sign in failed', msg);
      if (err instanceof ApiError && err.status === 429) {
        setErrors({ password: 'Too many attempts — wait a minute and retry.' });
      }
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
          <h1 className="font-display text-3xl font-extrabold">Welcome back, traveler</h1>
          <p className="mt-2 text-sm text-slate-600">
            Sign in to open your itineraries and keep planning.
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              icon={Mail}
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={errors.email}
              required
            />
            <PasswordInput
              id="login-password"
              label="Password"
              autoComplete="current-password"
              placeholder="Your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={errors.password}
              required
            />
            <Button type="submit" loading={busy} className="w-full justify-center py-3 text-base">
              <LogIn className="h-5 w-5" aria-hidden="true" />
              Sign in
            </Button>
          </form>

          <p className="mt-6 text-sm text-slate-600">
            New here?{' '}
            <Link to="/register" className="font-semibold text-ocean-700 underline-offset-4 hover:underline">
              Create an account <ArrowRight className="inline h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </p>
        </div>
      </div>
      <AuthAside />
    </div>
  );
}
