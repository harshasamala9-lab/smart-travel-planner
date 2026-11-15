import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle2, Compass, Loader2, TriangleAlert } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { setSession } from '../lib/auth';

/**
 * Neon Auth completes the Google OAuth exchange on its own and redirects the
 * user back here. Depending on configuration the redirect carries the session
 * tokens in the URL fragment/query — we pick them up when present; otherwise
 * we point the user to sign in.
 */
export default function AuthCallback() {
  const { reloadProfile } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [state, setState] = useState('working'); // working | done | error
  const [message, setMessage] = useState('Completing sign-in…');

  useEffect(() => {
    let alive = true;
    const params = new URLSearchParams(location.search);
    const hash = new URLSearchParams(location.hash.startsWith('#') ? location.hash.slice(1) : location.hash);
    const accessToken = params.get('access_token') || hash.get('access_token');
    const refreshToken = params.get('refresh_token') || hash.get('refresh_token');
    const error = params.get('error') || params.get('error_description');

    if (error) {
      setState('error');
      setMessage('Google sign-in was cancelled or failed. You can try again.');
      return undefined;
    }

    if (accessToken) {
      setSession(accessToken, refreshToken || '');
      reloadProfile()
        .then(() => {
          if (!alive) return;
          setState('done');
          setMessage('Signed in with Google.');
          navigate('/dashboard', { replace: true });
        })
        .catch(() => {
          if (!alive) return;
          setState('error');
          setMessage('We could not verify the session. Please sign in again.');
        });
    } else {
      setState('error');
      setMessage('No session arrived from the sign-in provider. Please sign in again.');
    }
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 text-center">
      {state === 'working' ? (
        <Loader2 className="h-10 w-10 animate-spin text-ocean-600" aria-hidden="true" />
      ) : state === 'done' ? (
        <CheckCircle2 className="h-12 w-12 text-ocean-600" aria-hidden="true" />
      ) : (
        <TriangleAlert className="h-12 w-12 text-amber-500" aria-hidden="true" />
      )}
      <h1 className="mt-5 font-display text-2xl font-bold">{state === 'done' ? 'You\u2019re in!' : state === 'error' ? 'Sign-in issue' : 'One moment…'}</h1>
      <p className="mt-2 max-w-sm text-sm text-slate-600">{message}</p>
      <Link to="/login" className="btn btn-outline mt-7">
        <Compass className="h-4 w-4" aria-hidden="true" />
        Back to sign in
      </Link>
    </div>
  );
}
