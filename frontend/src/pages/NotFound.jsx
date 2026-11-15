import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { PageTransition } from '../components/ui/Reveal';

export default function NotFound() {
  return (
    <PageTransition>
      <div className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-4 text-center">
        <div className="relative mb-6">
          <Compass className="h-24 w-24 text-ocean-600" strokeWidth={1} aria-hidden="true" />
          <span className="absolute -right-2 -top-1 rounded-full bg-rose-500 px-2 py-0.5 font-display text-sm font-bold text-white shadow-lift">
            404
          </span>
        </div>
        <h1 className="font-display text-3xl font-extrabold">You've wandered off the map</h1>
        <p className="mt-2 text-sm text-slate-600">
          The page you're looking for doesn't exist — but plenty of destinations do.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link to="/" className="btn btn-primary">Back to home</Link>
          <Link to="/explore" className="btn btn-outline">Explore destinations</Link>
        </div>
      </div>
    </PageTransition>
  );
}
