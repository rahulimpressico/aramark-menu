import { useState, useEffect } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Footer } from '../components/Footer';
import { AramarkRouteLoader } from '../components/AramarkRouteLoader';
import { HomePage } from '../pages/HomePage';
import { MenuAnalysisPage } from '../pages/MenuAnalysisPage';
import { CategoryAnalysisPage } from '../pages/CategoryAnalysisPage';

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
        <Routes location={displayLocation}>
          <Route path="/" element={<HomePage />} />
          <Route path="/meal-period" element={<MenuAnalysisPage />} />
          <Route path="/breakfast" element={<CategoryAnalysisPage />} />
          <Route path="/lunch" element={<CategoryAnalysisPage />} />
          <Route path="/dinner" element={<CategoryAnalysisPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Footer />
      </div>
      {showLoader && <AramarkRouteLoader />}
    </>
  );
}
