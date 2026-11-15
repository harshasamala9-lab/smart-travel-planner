import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Menu, X, Compass, Map as MapIcon, LayoutDashboard, Sparkles, Briefcase,
  BellRing, LogOut, Settings, ChevronDown, Check,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { initials } from '../../lib/format';
import { notificationsAPI } from '../../lib/api';

function Logo({ light = false }) {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="Smart Travel Planner home">
      <svg viewBox="0 0 64 64" className="h-9 w-9" aria-hidden="true">
        <defs>
          <linearGradient id="lg-nav" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#06c19b" />
            <stop offset="1" stopColor="#0a1c39" />
          </linearGradient>
        </defs>
        <rect width="64" height="64" rx="16" fill="url(#lg-nav)" />
        <path d="M14 40 L28 36 L44 20 L46 22 L34 40 L38 52 L33 53 L29 42 L18 44 Z" fill="#fff" opacity="0.95" />
        <circle cx="47" cy="17" r="3.2" fill="#e7ab35" />
      </svg>
      <span className={`font-display text-lg font-extrabold tracking-tight ${light ? 'text-white' : 'text-navy-950'}`}>
        Smart<span className="text-ocean-500">Travel</span>
      </span>
    </Link>
  );
}

const NAV_LINKS = [
  { to: '/explore', label: 'Explore', icon: Compass },
  { to: '/planner', label: 'AI Planner', icon: Sparkles },
  { to: '/itineraries', label: 'My Trips', icon: Briefcase },
];

function NotificationsBell() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const toast = useToast();
  const boxRef = useRef(null);

  useEffect(() => {
    let alive = true;
    notificationsAPI
      .list({ unread_only: 'false', limit: '5' })
      .then((data) => {
        if (!alive) return;
        setItems(data.items || []);
        setUnread(data.unread_count || 0);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const markAll = async () => {
    try {
      await notificationsAPI.markAllRead();
      setUnread(0);
      setItems((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch (err) {
      toast.error('Could not update notifications', err.message);
    }
  };

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-xl p-2 text-navy-900 transition-colors hover:bg-navy-950/5"
        aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        aria-expanded={open}
      >
        <BellRing className="h-5 w-5" aria-hidden="true" />
        {unread > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        ) : null}
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lift"
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <p className="text-sm font-bold text-navy-950">Notifications</p>
              {unread > 0 ? (
                <button type="button" onClick={markAll} className="text-xs font-semibold text-ocean-700 hover:underline">
                  Mark all read
                </button>
              ) : null}
            </div>
            <div className="max-h-80 overflow-y-auto">
              {items.length ? (
                items.map((n) => (
                  <div key={n.id} className="flex items-start gap-2.5 border-b border-slate-50 px-4 py-3 last:border-0">
                    <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${n.read ? 'bg-slate-200' : 'bg-ocean-500'}`} aria-hidden="true" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-navy-950">{n.title}</p>
                      <p className="line-clamp-2 text-xs text-slate-500">{n.message}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="px-4 py-6 text-center text-sm text-slate-500">You're all caught up.</p>
              )}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function UserMenu({ profile, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-slate-200 bg-white p-1 pr-2.5 transition-colors hover:border-ocean-300"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-ocean-500 to-navy-900 text-xs font-bold text-white">
          {initials(profile?.full_name || profile?.email)}
        </span>
        <span className="hidden max-w-[7.5rem] truncate text-sm font-semibold text-navy-950 sm:block">
          {(profile?.full_name || 'Traveler').split(' ')[0]}
        </span>
        <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.16 }}
            className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white py-1.5 shadow-lift"
            role="menu"
          >
            <Link to="/dashboard" className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-navy-950 hover:bg-slate-50" role="menuitem">
              <LayoutDashboard className="h-4 w-4 text-slate-400" aria-hidden="true" /> Dashboard
            </Link>
            <Link to="/profile" className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-navy-950 hover:bg-slate-50" role="menuitem">
              <Settings className="h-4 w-4 text-slate-400" aria-hidden="true" /> Profile & settings
            </Link>
            <div className="my-1 border-t border-slate-100" />
            <button
              type="button"
              onClick={onLogout}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-rose-600 hover:bg-rose-50"
              role="menuitem"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" /> Sign out
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export default function Navbar() {
  const { isAuthed, profile, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = async () => {
    setMobileOpen(false);
    await logout();
    toast.info('Signed out', 'See you on your next adventure.');
    navigate('/');
  };

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled ? 'border-b border-slate-200/80 bg-white/85 shadow-soft backdrop-blur-lg' : 'bg-transparent'
      }`}
    >
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8" aria-label="Main navigation">
        <Logo />

        {/* Desktop links */}
        {isAuthed ? (
          <div className="hidden items-center gap-1 lg:flex">
            {NAV_LINKS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold transition-colors ${
                    isActive ? 'bg-ocean-50 text-ocean-700' : 'text-navy-900 hover:bg-navy-950/5'
                  }`
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </NavLink>
            ))}
          </div>
        ) : (
          <div className="hidden items-center gap-1 lg:flex">
            <a href="/#popular" className="rounded-xl px-3.5 py-2 text-sm font-semibold text-navy-900 transition-colors hover:bg-navy-950/5">
              Destinations
            </a>
            <a href="/#features" className="rounded-xl px-3.5 py-2 text-sm font-semibold text-navy-900 transition-colors hover:bg-navy-950/5">
              Features
            </a>
            <a href="/#how-it-works" className="rounded-xl px-3.5 py-2 text-sm font-semibold text-navy-900 transition-colors hover:bg-navy-950/5">
              How it works
            </a>
          </div>
        )}

        <div className="flex items-center gap-2">
          {isAuthed ? (
            <>
              <NotificationsBell />
              <UserMenu profile={profile} onLogout={handleLogout} />
              <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="rounded-xl p-2 text-navy-900 transition-colors hover:bg-navy-950/5 lg:hidden"
                aria-label="Open menu"
                aria-expanded={mobileOpen}
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost hidden sm:inline-flex">
                Sign in
              </Link>
              <Link to="/register" className="btn btn-primary hidden sm:inline-flex">
                Get started
              </Link>
              <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="rounded-xl p-2 text-navy-950 transition-colors hover:bg-navy-950/5 sm:hidden"
                aria-label="Open menu"
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </button>
            </>
          )}
        </div>
      </nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-[70] lg:hidden"
          >
            <div className="absolute inset-0 bg-navy-950/50 backdrop-blur-sm" onClick={() => setMobileOpen(false)} aria-hidden="true" />
            <motion.aside
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'tween', duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
              className="absolute right-0 top-0 flex h-full w-[85%] max-w-sm flex-col bg-white shadow-lift"
              role="dialog"
              aria-modal="true"
              aria-label="Menu"
            >
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-4">
                <Logo />
                <button
                  type="button"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-xl p-2 text-slate-500 hover:bg-slate-100"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
              <nav className="flex-1 overflow-y-auto px-3 py-4">
                {isAuthed ? (
                  <>
                    {NAV_LINKS.map(({ to, label, icon: Icon }) => (
                      <NavLink
                        key={to}
                        to={to}
                        onClick={() => setMobileOpen(false)}
                        className={({ isActive }) =>
                          `mb-1 flex items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-semibold ${
                            isActive ? 'bg-ocean-50 text-ocean-700' : 'text-navy-950 hover:bg-slate-50'
                          }`
                        }
                      >
                        <Icon className="h-5 w-5 text-slate-400" aria-hidden="true" />
                        {label}
                      </NavLink>
                    ))}
                    <NavLink
                      to="/dashboard"
                      onClick={() => setMobileOpen(false)}
                      className="mb-1 flex items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-semibold text-navy-950 hover:bg-slate-50"
                    >
                      <LayoutDashboard className="h-5 w-5 text-slate-400" aria-hidden="true" />
                      Dashboard
                    </NavLink>
                    <NavLink
                      to="/profile"
                      onClick={() => setMobileOpen(false)}
                      className="mb-1 flex items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-semibold text-navy-950 hover:bg-slate-50"
                    >
                      <Settings className="h-5 w-5 text-slate-400" aria-hidden="true" />
                      Profile & settings
                    </NavLink>
                  </>
                ) : (
                  <>
                    <a href="/#popular" onClick={() => setMobileOpen(false)} className="mb-1 flex items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-semibold text-navy-950 hover:bg-slate-50">
                      <MapIcon className="h-5 w-5 text-slate-400" aria-hidden="true" /> Destinations
                    </a>
                    <a href="/#features" onClick={() => setMobileOpen(false)} className="mb-1 flex items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-semibold text-navy-950 hover:bg-slate-50">
                      <Sparkles className="h-5 w-5 text-slate-400" aria-hidden="true" /> Features
                    </a>
                    <a href="/#how-it-works" onClick={() => setMobileOpen(false)} className="mb-1 flex items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-semibold text-navy-950 hover:bg-slate-50">
                      <Compass className="h-5 w-5 text-slate-400" aria-hidden="true" /> How it works
                    </a>
                    <div className="mt-4 grid gap-2">
                      <Link to="/login" onClick={() => setMobileOpen(false)} className="btn btn-outline w-full justify-center">
                        Sign in
                      </Link>
                      <Link to="/register" onClick={() => setMobileOpen(false)} className="btn btn-primary w-full justify-center">
                        Get started
                      </Link>
                    </div>
                  </>
                )}
              </nav>
              {isAuthed ? (
                <div className="safe-bottom border-t border-slate-100 p-4">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex w-full items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-semibold text-rose-600 hover:bg-rose-50"
                  >
                    <LogOut className="h-5 w-5" aria-hidden="true" />
                    Sign out
                    <Check className="ml-auto h-4 w-4 text-slate-200" aria-hidden="true" />
                  </button>
                </div>
              ) : null}
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
