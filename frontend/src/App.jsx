import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import Navbar from './components/layout/Navbar';
import Footer from './components/layout/Footer';
import ScrollToTop from './components/routing/ScrollToTop';
import { ProtectedRoute, PublicOnlyRoute } from './components/routing/ProtectedRoute';

// Route-based code splitting keeps the initial bundle small — important on
// low-end hardware and slow connections.
const Landing = lazy(() => import('./pages/Landing'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const AuthCallback = lazy(() => import('./pages/AuthCallback'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Explore = lazy(() => import('./pages/Explore'));
const DestinationDetail = lazy(() => import('./pages/DestinationDetail'));
const Planner = lazy(() => import('./pages/Planner'));
const MyTrips = lazy(() => import('./pages/MyTrips'));
const ItineraryDetail = lazy(() => import('./pages/ItineraryDetail'));
const Profile = lazy(() => import('./pages/Profile'));
const SharedItinerary = lazy(() => import('./pages/SharedItinerary'));
const NotFound = lazy(() => import('./pages/NotFound'));

function RouteFallback() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center" role="status" aria-label="Loading page">
      <svg className="h-10 w-10 animate-spin text-ocean-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
        <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
    </div>
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Landing />} />

        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>
        <Route path="/auth/callback" element={<AuthCallback />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/explore" element={<Explore />} />
          <Route path="/destinations/:placeId" element={<DestinationDetail />} />
          <Route path="/planner" element={<Planner />} />
          <Route path="/itineraries" element={<MyTrips />} />
          <Route path="/itineraries/:id" element={<ItineraryDetail />} />
          <Route path="/profile" element={<Profile />} />
        </Route>

        <Route path="/shared/:token" element={<SharedItinerary />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AnimatePresence>
  );
}

function Shell() {
  const { pathname } = useLocation();
  // Public shared links get the same shell (nav is harmless for guests).
  const hideChrome = pathname.startsWith('/auth/callback');
  return (
    <div className="flex min-h-screen flex-col">
      <ScrollToTop />
      {!hideChrome ? <Navbar /> : null}
      <main className="flex-1">
        <Suspense fallback={<RouteFallback />}>
          <AnimatedRoutes />
        </Suspense>
      </main>
      {!hideChrome ? <Footer /> : null}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Shell />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
