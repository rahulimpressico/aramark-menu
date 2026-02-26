import { Link } from 'react-router-dom';
import { AramarkLogo } from '../components/AramarkLogo';

const backToStations = { to: '/', label: '← Back to stations' };

const combinedReportIcon = (
  <svg className="w-[72px] h-[72px] mb-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M16 13H8" />
    <path d="M16 17H8" />
    <path d="M10 9H8" />
  </svg>
);

const meals = [
  {
    id: 'breakfast',
    title: 'Breakfast',
    description: 'View and analyze morning menu offerings and nutrition.',
    icon: (
      <svg className="w-[72px] h-[72px] mb-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M4 11h16M4 11a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-5Z" />
        <path d="M8 11V7a4 4 0 1 1 8 0v4" />
      </svg>
    ),
    path: '/breakfast',
  },
  {
    id: 'lunch',
    title: 'Lunch',
    description: 'Review midday menu items and dietary compliance.',
    icon: (
      <svg className="w-[72px] h-[72px] mb-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
      </svg>
    ),
    path: '/lunch',
  },
  {
    id: 'dinner',
    title: 'Dinner',
    description: 'Explore evening menu options and full-day balance.',
    icon: (
      <svg className="w-[72px] h-[72px] mb-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
    ),
    path: '/dinner',
  },
] as const;

export function MenuAnalysisPage() {
  return (
    <main className="h-full flex flex-col overflow-hidden bg-gray-100">
      <div className="w-full shrink-0 grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 py-3 bg-footer-bg text-white">
        <Link
          to={backToStations.to}
          className="inline-flex items-center gap-2 px-3 py-2 text-[0.9375rem] font-medium text-white bg-transparent border border-white/40 rounded-md no-underline hover:bg-white/10 hover:border-white/60 transition-colors justify-self-start"
        >
          {backToStations.label}
        </Link>
        <div className="flex justify-center">
          <AramarkLogo width={140} height={35} variant="white" />
        </div>
        <div aria-hidden />
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto w-full flex flex-col items-center">
      <div className="w-full max-w-[1200px] px-4 flex flex-col items-center">
        <div className="w-full h-[200px] mb-6 rounded-b-xl overflow-hidden bg-gradient-to-br from-footer-bg via-[#034078] to-[#055c9e]" role="img" aria-label="Professional food service">
          <img
            src="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200&q=80"
            alt=""
            className="w-full h-full object-cover opacity-90"
          />
        </div>
        <header className="flex flex-col items-center gap-4 mb-6 text-center">
          <h1 className="m-0 text-2xl sm:text-3xl font-bold tracking-tight text-gray-900 leading-tight">
            Menu Analysis
          </h1>
          <p className="m-0 text-base text-gray-500 max-w-[40ch]">
            Select a meal period to view and analyze menu offerings, nutrition, and compliance.
          </p>
        </header>

        {/* Combined report CTA */}
        <Link
          to="/report"
          className="flex flex-col sm:flex-row items-center gap-4 w-full max-w-[1100px] p-5 sm:p-6 mb-6 rounded-2xl border-2 border-primary/20 bg-white shadow-md hover:shadow-lg hover:border-primary/40 transition-all duration-200 no-underline text-inherit focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 group"
        >
          <div className="shrink-0 text-primary group-hover:scale-105 transition-transform">
            {combinedReportIcon}
          </div>
          <div className="flex-1 text-center sm:text-left min-w-0">
            <h2 className="m-0 text-lg sm:text-xl font-bold text-gray-900 tracking-tight">
              Want a combined report for all meal periods?
            </h2>
            <p className="m-0 mt-1.5 text-[0.9375rem] text-gray-500 leading-snug">
              View one full report covering Breakfast, Lunch & Dinner — structure, playbook alignment, rotation, and recommendations.
            </p>
          </div>
          <span className="shrink-0 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold group-hover:bg-primary-hover transition-colors">
            View full report
            <span aria-hidden>→</span>
          </span>
        </Link>

        <p className="text-[0.8125rem] text-gray-500 mb-3 w-full max-w-[1100px]">
          Or select a meal period:
        </p>

        <ul className="grid grid-cols-1 min-[400px]:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-[1100px] list-none m-0 p-0 pb-8" role="list">
        {meals.map(({ id, title, description, icon, path }) => (
          <li key={id}>
            <Link
              to={path}
              className="relative flex flex-col items-center justify-center min-h-[260px] p-8 bg-white rounded-xl border border-gray-200 shadow-md transition duration-200 hover:scale-[1.03] hover:shadow-xl focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 no-underline text-inherit"
            >
              {icon}
              <h2 className="m-0 text-2xl font-bold text-gray-900 tracking-tight">{title}</h2>
              <p className="mt-3 text-[0.9375rem] text-gray-500 text-center leading-snug">
                {description}
              </p>
            </Link>
          </li>
        ))}
        </ul>
      </div>
      </div>
    </main>
  );
}
