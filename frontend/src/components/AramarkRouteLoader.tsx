import { AramarkLogo } from './AramarkLogo';


export function AramarkRouteLoader() {
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-gradient-to-br from-footer-bg"
      role="status"
      aria-label="Loading"
    >
      <div className="flex flex-col items-center gap-6">
        <div className="animate-pulse">
          <AramarkLogo width={220} height={55} variant="white" />
        </div>
      </div>
    </div>
  );
}
