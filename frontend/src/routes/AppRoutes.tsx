import { useState, useEffect } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Footer } from '../components/Footer';
import { AramarkRouteLoader } from '../components/AramarkRouteLoader';
import { HomePage } from '../pages/HomePage';
import { MenuAnalysisPage } from '../pages/MenuAnalysisPage';
import { CategoryAnalysisPage } from '../pages/CategoryAnalysisPage';
import { CombinedReportPage } from '../pages/CombinedReportPage';

const ROUTE_LOADER_DURATION_MS = 2000;

export function AppRoutes() {
  const location = useLocation();
  const [showLoader, setShowLoader] = useState(true);
  const [displayLocation, setDisplayLocation] = useState(location);

  useEffect(() => {
    setShowLoader(true);
    const t = setTimeout(() => {
      setDisplayLocation(location);
      setShowLoader(false);
    }, ROUTE_LOADER_DURATION_MS);
    return () => clearTimeout(t);
  }, [location]);

  return (
    <>
      <div className="min-h-screen flex flex-col">
        <div className="flex-1 flex flex-col min-h-0">
        <Routes location={displayLocation}>
          <Route path="/" element={<HomePage />} />
          <Route path="/stations/:stationSlug/meal-period" element={<MenuAnalysisPage />} />
          <Route path="/stations/:stationSlug/report" element={<CombinedReportPage />} />
          <Route path="/stations/:stationSlug/:category" element={<CategoryAnalysisPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </div>
        <Footer />
      </div>
      {showLoader && <AramarkRouteLoader />}
    </>
  );
}
