import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import {
  Search, Sparkles, MapPin, Route as RouteIcon, Wallet, CloudSun,
  CalendarRange, Compass, ChevronDown, Plane, Brain, ListChecks, Download, Share2,
} from 'lucide-react';
import Reveal, { SectionHeading } from '../components/ui/Reveal';
import Typewriter from '../components/ui/Typewriter';
import SmartImage from '../components/ui/SmartImage';
import { IMAGES } from '../lib/images';
import { SHOWCASE_DESTINATIONS } from '../lib/constants';

const PHRASES = ['Kyoto in autumn.', 'the Amalfi Coast.', 'Iceland\u2019s ring road.', 'a Bali sunset.', 'Machu Picchu at dawn.'];

const FEATURES = [
  {
    icon: Brain,
    title: 'AI plans the days',
    text: 'Gemini shapes a day-by-day route — then every stop is validated against real Google Places candidates, never invented.',
  },
  {
    icon: MapPin,
    title: 'Real places only',
    text: 'Attractions, restaurants and hotels come straight from Google Places with ratings, addresses and opening hours.',
  },
  {
    icon: Wallet,
    title: 'Honest budgets',
    text: 'Every cost is a clearly-labelled planning estimate with its assumptions shown — no fake live prices.',
  },
  {
    icon: CloudSun,
    title: 'Weather aware',
    text: 'Forecasts from OpenWeather, with a straight answer on whether your dates are actually covered.',
  },
];

const STEPS = [
  {
    icon: ListChecks,
    title: 'Tell us the trip',
    text: 'Destination, dates, travellers, budget and what you love doing. Two minutes, no spreadsheets.',
  },
  {
    icon: Sparkles,
    title: 'AI crafts the journey',
    text: 'A full day-by-day itinerary with real places, timings, routes and an estimate that respects your budget.',
  },
  {
    icon: Download,
    title: 'Save, share, print',
    text: 'Keep it in My Trips, create a private share link, or export a clean PDF for the road.',
  },
];

function HeroVideo() {
  const videoRef = useRef(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    const v = videoRef.current;
    if (!v || reduced) return undefined;
    // Only autoplay on capable, non-metered connections — graceful otherwise.
    let played = false;
    const tryPlay = () => {
      if (played) return;
      v.play().then(() => { played = true; }).catch(() => {});
    };
    tryPlay();
    v.addEventListener('canplay', tryPlay);
    return () => v.removeEventListener('canplay', tryPlay);
  }, [reduced]);

  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
      {!reduced ? (
        <video
          ref={videoRef}
          className="h-full w-full object-cover"
          muted
          loop
          playsInline
          preload="none"
          poster={IMAGES.hero.src}
        >
          <source src="/media/hero-travel.mp4" type="video/mp4" />
        </video>
      ) : (
        <img src={IMAGES.hero.src} alt="" className="h-full w-full object-cover" />
      )}
      <div className="absolute inset-0 bg-gradient-to-b from-navy-950/80 via-navy-950/45 to-navy-950/90" />
      <div className="absolute inset-0 bg-gradient-to-r from-navy-950/70 via-transparent to-transparent" />
    </div>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const search = (e) => {
    e.preventDefault();
    const q = query.trim();
    navigate(q ? `/explore?q=${encodeURIComponent(q)}` : '/explore');
  };

  return (
    <div>
      {/* ----------------------------------------------------------- HERO */}
      <section className="relative flex min-h-[92svh] items-center justify-center overflow-hidden rounded-b-[2.5rem]">
        <HeroVideo />
        <div className="relative z-10 mx-auto max-w-3xl px-4 pb-16 pt-28 text-center sm:px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          >
            <span className="glass mx-auto mb-6 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold text-ocean-200">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              Day-by-day itineraries · real places · honest budgets
            </span>
            <h1 className="font-display text-4xl font-extrabold leading-tight text-white sm:text-5xl md:text-6xl">
              Your next journey,
              <br />
              planned around{' '}
              <Typewriter phrases={PHRASES} className="bg-gradient-to-r from-ocean-300 to-sand-300 bg-clip-text text-transparent" />
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-slate-300 sm:text-lg">
              Tell Smart Travel Planner where and when — the AI builds a complete day-by-day
              itinerary from real Google Places data, with routes, weather and budget estimates.
            </p>

            {/* Destination search */}
            <form onSubmit={search} className="mx-auto mt-8 flex max-w-xl flex-col gap-2.5 sm:flex-row" role="search">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Where do you dream of going?"
                  aria-label="Search destinations"
                  className="w-full rounded-xl border-0 bg-white/95 py-3.5 pl-12 pr-4 text-[15px] text-navy-950 shadow-lift placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-ocean-400/40"
                />
              </div>
              <button type="submit" className="btn btn-sand justify-center px-6 py-3.5 text-[15px] shadow-lift">
                <Compass className="h-5 w-5" aria-hidden="true" />
                Explore
              </button>
            </form>

            <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link to="/planner" className="btn btn-primary px-6 py-3 text-base shadow-glow">
                <Sparkles className="h-5 w-5" aria-hidden="true" />
                Plan my trip with AI
              </Link>
              <Link to="/register" className="text-sm font-semibold text-slate-300 underline-offset-4 transition-colors hover:text-white hover:underline">
                Create a free account →
              </Link>
            </div>
          </motion.div>
        </div>
        <motion.div
          className="absolute bottom-5 left-1/2 z-10 -translate-x-1/2 text-white/70"
          animate={{ y: [0, 8, 0] }}
          transition={{ repeat: Infinity, duration: 2.2, ease: 'easeInOut' }}
          aria-hidden="true"
        >
          <ChevronDown className="h-6 w-6" />
        </motion.div>
      </section>

      {/* --------------------------------------------------- POPULAR TRIPS */}
      <section id="popular" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 sm:px-6 lg:px-8">
        <Reveal>
          <SectionHeading
            eyebrow="Explore destinations"
            title="Where will you go next?"
            subtitle="Sixteen editor-picked guides — or search any city, island, beach, landmark or travel style."
            center
          />
        </Reveal>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {SHOWCASE_DESTINATIONS.map((d, i) => {
            const img = IMAGES[d.imageKey];
            return (
              <Reveal key={d.name} delay={Math.min(i * 0.05, 0.3)}>
                <Link
                  to={`/explore?q=${encodeURIComponent(d.query)}`}
                  className="card card-hover group relative block overflow-hidden"
                >
                  <SmartImage
                    src={img.src}
                    alt={img.alt}
                    ratio="aspect-[3/4] sm:aspect-[4/3] lg:aspect-[3/4]"
                    imgClassName="transition-transform duration-500 group-hover:scale-[1.05]"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-navy-950/85 via-navy-950/10 to-transparent" />
                  <div className="absolute inset-x-0 bottom-0 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-ocean-300">{d.country}</p>
                    <h3 className="font-display text-lg font-bold text-white">{d.name}</h3>
                    <p className="mt-0.5 text-xs text-slate-300">{d.tag}</p>
                  </div>
                </Link>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* ------------------------------------------------------- FEATURES */}
      <section id="features" className="scroll-mt-20 bg-navy-950 py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Reveal>
            <SectionHeading
              eyebrow="Why it's different"
              title="An itinerary you can actually trust"
              subtitle="Every recommendation is validated against real places before it reaches your screen."
              center
              light
            />
          </Reveal>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ icon: Icon, title, text }, i) => (
              <Reveal key={title} delay={Math.min(i * 0.07, 0.28)}>
                <div className="h-full rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm transition-colors duration-300 hover:border-ocean-400/40 hover:bg-white/10">
                  <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-ocean-400 to-ocean-700 text-navy-950">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <h3 className="font-display text-lg font-bold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* --------------------------------------------------- HOW IT WORKS */}
      <section id="how-it-works" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 sm:px-6 lg:px-8">
        <Reveal>
          <SectionHeading eyebrow="How it works" title="Three steps to a complete plan" center />
        </Reveal>
        <div className="relative grid gap-8 md:grid-cols-3">
          <div className="absolute left-1/2 top-10 hidden h-px w-2/3 -translate-x-1/2 bg-gradient-to-r from-ocean-200 via-sand-200 to-ocean-200 md:block" aria-hidden="true" />
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <Reveal key={title} delay={Math.min(i * 0.1, 0.3)} className="relative text-center">
              <div className="relative mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-full border-4 border-white bg-gradient-to-br from-ocean-500 to-navy-900 text-white shadow-lift">
                <Icon className="h-8 w-8" aria-hidden="true" />
                <span className="absolute -right-1 -top-1 flex h-7 w-7 items-center justify-center rounded-full bg-sand-400 text-xs font-extrabold text-navy-950">
                  {i + 1}
                </span>
              </div>
              <h3 className="font-display text-lg font-bold">{title}</h3>
              <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-slate-600">{text}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* -------------------------------------------------------- AI BAND */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <Reveal>
          <div className="relative overflow-hidden rounded-4xl bg-gradient-to-br from-ocean-700 via-navy-900 to-navy-950 p-8 sm:p-12 lg:p-16">
            <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-ocean-500/20 blur-3xl" aria-hidden="true" />
            <div className="absolute -bottom-24 -left-16 h-64 w-64 rounded-full bg-sand-400/10 blur-3xl" aria-hidden="true" />
            <div className="relative grid items-center gap-10 lg:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-sand-300">Powered by Gemini + Google</p>
                <h2 className="font-display text-3xl font-extrabold text-white sm:text-4xl">
                  From "somewhere warm" to a finished plan in one form
                </h2>
                <p className="mt-4 max-w-lg text-base leading-relaxed text-slate-300">
                  Pick your dates, budget and travel style. The planner resolves your destination with Google Places,
                  orders each day around real opening hours and travel times, and never shows you a place that doesn't exist.
                </p>
                <div className="mt-7 flex flex-wrap gap-3">
                  <Link to="/planner" className="btn btn-sand px-6 py-3 text-base shadow-lift">
                    <Sparkles className="h-5 w-5" aria-hidden="true" />
                    Start planning
                  </Link>
                  <Link to="/register" className="btn glass px-6 py-3 text-base text-white hover:bg-white/20">
                    <Plane className="h-5 w-5" aria-hidden="true" />
                    Create account
                  </Link>
                </div>
              </div>
              <ul className="grid gap-3 sm:grid-cols-2">
                {[
                  { icon: CalendarRange, label: 'Day-by-day schedule with times' },
                  { icon: RouteIcon, label: 'Walking & transit legs between stops' },
                  { icon: Wallet, label: 'Per-category budget estimate' },
                  { icon: Share2, label: 'Private share links & PDF export' },
                ].map(({ icon: Icon, label }) => (
                  <li key={label} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3.5 text-sm font-medium text-slate-200">
                    <Icon className="h-5 w-5 shrink-0 text-sand-300" aria-hidden="true" />
                    {label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Reveal>
      </section>
    </div>
  );
}
