import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AramarkLogo } from "../components/AramarkLogo";
import { ReportMarkdown } from "../components/ReportMarkdown";

const CATEGORIES: Record<string, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
};

// Images in frontend/public/stations/grill/ – Vite serves at /stations/grill/
const IMAGE_BY_CATEGORY: Record<string, string> = {
  breakfast: "Breakfast.png",
  lunch: "Lunch.png",
  dinner: "Dinner.png",
};

function getImagePath(fileName: string): string {
  return `/stations/grill/${encodeURIComponent(fileName)}`;
}

const REPORT_API = "/api/reports/report";
const REPORT_CACHED_API = "/api/reports/report"; // GET /api/reports/report/{station}/{meal}
const DEFAULT_STATION = "Grill";

function reportCachedUrl(station: string, mealPeriod: string): string {
  const s = station.toLowerCase().replace(/\s+/g, "_");
  const m = mealPeriod.toLowerCase().replace(/\s+/g, "_");
  return `${REPORT_CACHED_API}/${s}/${m}`;
}

// Same icons as Menu Analysis page cards (breakfast tray, lunch sun, dinner moon)
const MEAL_ICONS: Record<string, JSX.Element> = {
  breakfast: (
    <svg className="w-5 h-5 shrink-0 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 11h16M4 11a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-5Z" />
      <path d="M8 11V7a4 4 0 1 1 8 0v4" />
    </svg>
  ),
  lunch: (
    <svg className="w-5 h-5 shrink-0 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  ),
  dinner: (
    <svg className="w-5 h-5 shrink-0 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  ),
};

export function CategoryAnalysisPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [loaderActive, setLoaderActive] = useState(false);
  const [reportContent, setReportContent] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [imageDialogOpen, setImageDialogOpen] = useState(false);

  // Routes are /breakfast, /lunch, /dinner – no :category param, so derive from pathname
  const category = pathname.slice(1).toLowerCase() || "";
  const title =
    category && CATEGORIES[category] ? `${CATEGORIES[category]} Menu` : "Menu";

  const imageFileName = category ? IMAGE_BY_CATEGORY[category] : "";
  const imageSrc = imageFileName ? getImagePath(imageFileName) : "";

  // Try cached report (GET .txt) first; if 404, generate via POST and use response
  useEffect(() => {
    if (!analysisOpen || !category || !CATEGORIES[category]) return;
    setReportContent(null);
    setReportError(null);
    setLoaderActive(true);
    let cancelled = false;
    const mealPeriod = CATEGORIES[category];
    (async () => {
      try {
        const cachedRes = await fetch(reportCachedUrl(DEFAULT_STATION, mealPeriod));
        if (cancelled) return;
        if (cachedRes.ok) {
          const data = await cachedRes.json();
          const text = data.content ?? "";
          if (text.trim()) {
            setReportContent(text);
            setReportError(null);
            setLoaderActive(false);
            return;
          }
        }
        const res = await fetch(REPORT_API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            station_name: DEFAULT_STATION,
            meal_period: mealPeriod,
          }),
        });
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          setReportContent(data.content ?? "");
          setReportError(null);
        } else {
          let message: string | null = null;
          try {
            const err = await res.json();
            if (err?.detail) message = typeof err.detail === "string" ? err.detail : err.detail?.msg ?? null;
          } catch {
            message = res.status === 503 ? "Report could not be generated. Please try again." : null;
          }
          setReportError(message ?? (res.status === 503 ? "Report could not be generated. Please try again." : "Report not available."));
        }
      } catch {
        if (!cancelled) setReportError("Report not available. Please try again.");
      } finally {
        if (!cancelled) setLoaderActive(false);
      }
    })();
    return () => { cancelled = true; };
  }, [analysisOpen, category]);

  // Auto-start analysis once when category is valid (no buttons)
  useEffect(() => {
    if (category && CATEGORIES[category]) setAnalysisOpen(true);
  }, [category]);

  // Close image dialog on Escape
  useEffect(() => {
    if (!imageDialogOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setImageDialogOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [imageDialogOpen]);

  if (!category || !CATEGORIES[category]) {
    navigate("/", { replace: true });
    return null;
  }

  return (
    <main className="min-h-0 flex-1 flex flex-col bg-[#f5f5f5]">
      {/* Header: Back to Menu (left) + Title with icon (right) */}
      <header className="shrink-0 border-b border-gray-200/90 bg-white">
        <div className="max-w-[1400px] mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <Link
            to="/meal-period"
            className="inline-flex items-center gap-2 text-[0.8125rem] font-medium text-gray-500 no-underline transition-colors hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 rounded shrink-0"
          >
            <span className="text-gray-400" aria-hidden>←</span>
            Back to Menu
          </Link>
          <h1 className="m-0 text-[1.0625rem] font-semibold tracking-tight text-gray-900 flex items-center gap-2 min-w-0 truncate">
            <span className="truncate">{title}</span>
            {MEAL_ICONS[category] ?? null}
          </h1>
        </div>
      </header>
      {/* Two-section layout with subtle Aramark watermark (no impact on text visibility) */}
      <div className="flex-1 relative flex flex-col lg:flex-row gap-5 m-4 min-h-0">
        {/* Watermark: very low opacity, behind content, pointer-events-none */}
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none z-0"
          aria-hidden
        >
          <div className="opacity-[0.06] select-none">
            <AramarkLogo width={280} height={70} variant="default" />
          </div>
        </div>
        <div className="relative z-10 flex-1 flex flex-col lg:flex-row gap-5 min-h-0 min-w-0">
          {/* Section 1: Menu image – professional card */}
          <section className="lg:w-[45%] xl:w-[40%] flex-shrink-0 opacity-0-init animate-slide-up rounded-xl bg-white shadow-xl border border-gray-200/90 overflow-hidden flex flex-col h-[65vh] lg:h-[72vh] transition-shadow duration-300 hover:shadow-2xl">
            <div className="shrink-0 px-5 py-3.5 border-b border-gray-100 bg-white">
              <h2 className="m-0 text-[0.9375rem] font-semibold tracking-tight text-gray-900">
                {title}
              </h2>
              <p className="m-0 mt-0.5 text-xs text-gray-500">
                Reference image
              </p>
            </div>
            <div className="flex-1 min-h-0 p-4 flex items-center justify-center overflow-hidden bg-gray-50/40">
              {imageSrc ? (
                <div className="relative w-full h-full flex items-center justify-center">
                  <button
                    type="button"
                    onClick={() => !loaderActive && setImageDialogOpen(true)}
                    className={`w-full h-full flex items-center justify-center cursor-pointer focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 rounded-lg ${loaderActive ? "cursor-wait" : "cursor-zoom-in"}`}
                    disabled={loaderActive}
                    aria-label="Open image in full view"
                  >
                    <img
                      src={imageSrc}
                      alt={title}
                      className={`max-w-full max-h-full w-auto h-auto object-contain rounded-lg border border-gray-200/80 shadow-sm transition-all duration-500 ${loaderActive ? "blur-[4px]" : ""}`}
                    />
                  </button>
                  {loaderActive && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 rounded-lg bg-white/60 backdrop-blur-sm">
                      <span className="h-12 w-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
                      <p className="text-sm font-medium text-gray-600 animate-pulse">
                        Analyzing menu…
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center gap-2 text-gray-500 text-center p-4">
                  <p className="m-0 text-sm font-medium">
                    No menu image for this category.
                  </p>
                  <p className="m-0 text-xs">
                    Add{" "}
                    <strong>
                      {imageFileName || `${category || "breakfast"} grill.png`}
                    </strong>{" "}
                    to <strong>frontend/public/stations/grill/</strong>.
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* Section 2: Analysis Report – professional document-style panel */}
          <section className="flex-1 min-h-0 min-w-0 opacity-0-init animate-slide-up delay-100 flex flex-col rounded-xl shadow-xl border border-gray-200/90 max-h-[65vh] lg:max-h-[72vh] overflow-hidden bg-white">
            <div className="shrink-0 px-6 py-3.5 border-b border-gray-100 bg-white">
              <h2 className="m-0 text-[0.9375rem] font-semibold tracking-tight text-gray-900">
                Analysis Report
              </h2>
              <p className="m-0 mt-0.5 text-xs text-gray-500">
                Menu intelligence
              </p>
            </div>
            {/* Report body */}
            <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden border-l-4 border-l-primary/20 bg-[#fafbfc]">
              <div className="p-6 py-5">
                {loaderActive ? (
                  <div className="flex flex-col items-center justify-center gap-4 py-12 text-gray-500 animate-fade-in">
                    <span className="h-10 w-10 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <p className="m-0 text-sm font-medium text-gray-600">
                      Preparing your report…
                    </p>
                  </div>
                ) : reportContent ? (
                  <ReportMarkdown content={reportContent} />
                ) : reportError ? (
                  <div className="py-10 animate-fade-in">
                    <div className="rounded-xl bg-amber-50/90 border border-amber-200/80 px-5 py-4 text-sm text-amber-900 max-w-md">
                      <p className="m-0 font-medium">Report not available</p>
                      <p className="m-0 mt-1.5 text-amber-800/90 text-xs leading-relaxed">
                        {reportError}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-500 animate-fade-in">
                    <span className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <p className="m-0 text-sm font-medium">Loading report…</p>
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* Image dialog: click image to open, click outside to close */}
      {imageDialogOpen && imageSrc && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
          onClick={() => setImageDialogOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Menu image full view"
        >
          <div
            className="relative max-w-[95vw] max-h-[95vh] flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={imageSrc}
              alt={title}
              className="max-w-full max-h-[90vh] w-auto h-auto object-contain rounded-lg shadow-2xl ring-2 ring-white/20"
            />
          </div>
        </div>
      )}
    </main>
  );
}
