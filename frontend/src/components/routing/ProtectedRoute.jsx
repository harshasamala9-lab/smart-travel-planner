import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { hasSession } from '../../lib/auth';

/** Blocks the route for guests and remembers where they wanted to go. */
export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'authed') return <Outlet />;
  if (status === 'loading') {
    return (
      <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-label="Checking your session">
        <Spinner size="lg" />
      </div>
    );
  }
  return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
}

function Spinner() {
  return (
    <svg className="h-9 w-9 animate-spin text-ocean-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/** Login/register pages are pointless once signed in. */
export function PublicOnlyRoute() {
  const { status } = useAuth();
  if (status === 'authed') return <Navigate to="/dashboard" replace />;
  if (status === 'loading') {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }
  return <Outlet />;
}
