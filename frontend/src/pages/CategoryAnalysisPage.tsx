import { useCallback, useState, useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { reportCachedUrl, REPORT_API_BASE } from "../api/reports";
import { AramarkLogo } from "../components/AramarkLogo";
import { ReportMarkdown } from "../components/ReportMarkdown";
import { backendStationNameFromSlug, stationNameFromSlug } from "../data/stations";

const CATEGORIES: Record<string, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
};

const IMAGE_BY_CATEGORY: Record<string, string> = {
  breakfast: "Breakfast.png",
  lunch: "Lunch.png",
  dinner: "Dinner.png",
};

type SourceRow = {
  id: string;
  name: string;
  food_cost?: number;
  ing_count?: number;
};

function getImagePath(stationSlug: string, fileName: string): string {
  return `/stations/${encodeURIComponent(stationSlug)}/${encodeURIComponent(fileName)}`;
}

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

function extractSourceRows(data: any): SourceRow[] {
  const rows = data?.analysis?.all_recipes;
  if (!Array.isArray(rows)) return [];
  return rows.slice(0, 40).map((r: any) => ({
    id: String(r?.id ?? ""),
    name: String(r?.name ?? ""),
    food_cost: typeof r?.food_cost === "number" ? r.food_cost : undefined,
    ing_count: typeof r?.ing_count === "number" ? r.ing_count : undefined,
  }));
}


function normalizeReportError(message: string): string {
  if (message.toLowerCase().includes("no data found for station")) {
    return "No data available for this station and meal period yet.";
  }
  return message;
}
export function CategoryAnalysisPage() {
  const { stationSlug, category } = useParams<{ stationSlug: string; category: string }>();
  const navigate = useNavigate();
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [loaderActive, setLoaderActive] = useState(false);
  const [reportContent, setReportContent] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [sourceRows, setSourceRows] = useState<SourceRow[]>([]);
  const [imageDialogOpen, setImageDialogOpen] = useState(false);
  const [imageAvailable, setImageAvailable] = useState(true);

  const normalizedStationSlug = stationSlug?.trim().toLowerCase() || "";
  const normalizedCategory = category?.trim().toLowerCase() || "";
  const displayStationName = stationNameFromSlug(normalizedStationSlug || "grill");
  const stationName = backendStationNameFromSlug(normalizedStationSlug || "grill");
  const title =
    normalizedCategory && CATEGORIES[normalizedCategory]
      ? `${displayStationName} ${CATEGORIES[normalizedCategory]} Menu`
      : `${displayStationName} Menu`;

  const imageFileName = normalizedCategory ? IMAGE_BY_CATEGORY[normalizedCategory] : "";
  const imageSrc = imageFileName ? getImagePath(normalizedStationSlug, imageFileName) : "";

  useEffect(() => {
    if (!analysisOpen || !normalizedCategory || !CATEGORIES[normalizedCategory]) return;
    setReportContent(null);
    setReportError(null);
    setSourceRows([]);
    setLoaderActive(true);
    let cancelled = false;
    const mealPeriod = CATEGORIES[normalizedCategory];
    (async () => {
      try {
        const cachedRes = await fetch(reportCachedUrl(stationName, mealPeriod));
        if (cancelled) return;
        if (cachedRes.ok) {
          const data = await cachedRes.json();
          const text = data.content ?? "";
          if (text.trim()) {
            setReportContent(text);
            setSourceRows(extractSourceRows(data));
            setReportError(null);
            setLoaderActive(false);
            return;
          }
        }
        const res = await fetch(REPORT_API_BASE, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            station_name: stationName,
            meal_period: mealPeriod,
            use_fast: true,
          }),
        });
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          setReportContent(data.content ?? "");
          setSourceRows(extractSourceRows(data));
          setReportError(null);
        } else {
          let message: string | null = null;
          try {
            const err = await res.json();
            if (err?.detail) message = typeof err.detail === "string" ? err.detail : err.detail?.msg ?? null;
          } catch {
            message = res.status === 503 ? "Report could not be generated. Please try again." : null;
          }
          setReportError(normalizeReportError(message ?? (res.status === 503 ? "Report could not be generated. Please try again." : "Report not available.")));
        }
      } catch {
        if (!cancelled) setReportError(normalizeReportError("Report not available. Please try again."));
      } finally {
        if (!cancelled) setLoaderActive(false);
      }
    })();
    return () => { cancelled = true; };
  }, [analysisOpen, normalizedCategory, stationName]);

  useEffect(() => {
    if (normalizedCategory && CATEGORIES[normalizedCategory]) setAnalysisOpen(true);
  }, [normalizedCategory]);

  const regenerateReport = useCallback(async () => {
    if (!normalizedCategory || !CATEGORIES[normalizedCategory]) return;
    const mealPeriod = CATEGORIES[normalizedCategory];
    setLoaderActive(true);
    setReportError(null);
    try {
      const res = await fetch(REPORT_API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ station_name: stationName, meal_period: mealPeriod, use_fast: true }),
      });
      if (res.ok) {
        const data = await res.json();
        setReportContent(data.content ?? "");
        setSourceRows(extractSourceRows(data));
        setReportError(null);
      } else {
        const err = await res.json().catch(() => ({}));
        const msg = typeof err?.detail === "string" ? err.detail : "Report could not be generated. Please try again.";
        setReportError(normalizeReportError(msg));
      }
    } catch {
      setReportError(normalizeReportError("Report not available. Please try again."));
    } finally {
      setLoaderActive(false);
    }
  }, [normalizedCategory, stationName]);

  useEffect(() => {
    setImageAvailable(true);
  }, [imageSrc]);

  useEffect(() => {
    if (!imageDialogOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setImageDialogOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [imageDialogOpen]);

  if (!normalizedStationSlug || !normalizedCategory || !CATEGORIES[normalizedCategory]) {
    navigate("/", { replace: true });
    return null;
  }

  return (
    <main className="min-h-0 flex-1 flex flex-col bg-[#f5f5f5]">
      <header className="shrink-0 border-b border-gray-200/90 bg-white">
        <div className="max-w-[1400px] mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <Link
            to={`/stations/${normalizedStationSlug}/meal-period`}
            className="inline-flex items-center gap-2 text-[0.8125rem] font-medium text-gray-500 no-underline transition-colors hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 rounded shrink-0"
          >
            <span className="text-gray-400" aria-hidden>←</span>
            Back to Menu
          </Link>
          <h1 className="m-0 text-[1.0625rem] font-semibold tracking-tight text-gray-900 flex items-center gap-2 min-w-0 truncate">
            <span className="truncate">{title}</span>
            {MEAL_ICONS[normalizedCategory] ?? null}
          </h1>
        </div>
      </header>
      <div className="flex-1 relative flex flex-col lg:flex-row gap-5 m-4 min-h-0">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0" aria-hidden>
          <div className="opacity-[0.06] select-none">
            <AramarkLogo width={280} height={70} variant="default" />
          </div>
        </div>
        <div className="relative z-10 flex-1 flex flex-col lg:flex-row gap-5 min-h-0 min-w-0">
          <section className="lg:w-[45%] xl:w-[40%] flex-shrink-0 opacity-0-init animate-slide-up rounded-xl bg-white shadow-xl border border-gray-200/90 overflow-hidden flex flex-col h-[65vh] lg:h-[72vh] transition-shadow duration-300 hover:shadow-2xl">
            <div className="shrink-0 px-5 py-3.5 border-b border-gray-100 bg-white">
              <h2 className="m-0 text-[0.9375rem] font-semibold tracking-tight text-gray-900">{title}</h2>
              <p className="m-0 mt-0.5 text-xs text-gray-500">Reference source data</p>
            </div>
            <div className="flex-1 min-h-0 p-4 overflow-y-auto bg-gray-50/40">
              {imageSrc && imageAvailable ? (
                <div className="relative w-full h-[220px] flex items-center justify-center mb-4">
                  <button
                    type="button"
                    onClick={() => !loaderActive && setImageDialogOpen(true)}
                    className={`w-full h-full flex items-center justify-center focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 rounded-lg ${loaderActive ? "cursor-wait" : "cursor-zoom-in"}`}
                    disabled={loaderActive}
                    aria-label="Open image in full view"
                  >
                    <img
                      src={imageSrc}
                      alt={title}
                      className={`max-w-full max-h-full w-auto h-auto object-contain rounded-lg border border-gray-200/80 shadow-sm transition-all duration-500 `}
                      onError={() => setImageAvailable(false)}
                    />
                  </button>
                </div>
              ) : null}

              <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
                <div className="px-3 py-2 border-b border-gray-200 bg-gray-50 text-xs font-semibold text-gray-700">
                  Source menu data used (Excel/KG)
                </div>
                {sourceRows.length > 0 ? (
                  <div className="max-h-[280px] overflow-auto">
                    <table className="min-w-full text-xs text-left text-gray-700">
                      <thead className="bg-gray-50 text-gray-800 sticky top-0">
                        <tr>
                          <th className="px-3 py-2">Recipe</th>
                          <th className="px-3 py-2">Cost</th>
                          <th className="px-3 py-2">Ingredients</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {sourceRows.map((r) => (
                          <tr key={`${r.id}-${r.name}`}>
                            <td className="px-3 py-2">
                              <div className="font-medium text-gray-900">{r.name || r.id}</div>
                              {r.id ? <div className="text-[10px] text-gray-500">{r.id}</div> : null}
                            </td>
                            <td className="px-3 py-2">{typeof r.food_cost === "number" ? `$${r.food_cost.toFixed(4)}` : "-"}</td>
                            <td className="px-3 py-2">{typeof r.ing_count === "number" ? r.ing_count : "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-3 text-xs text-gray-500">
                    Source rows not available yet. Generate or regenerate the report for this station/meal.
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className="flex-1 min-h-0 min-w-0 opacity-0-init animate-slide-up delay-100 flex flex-col rounded-xl shadow-xl border border-gray-200/90 max-h-[65vh] lg:max-h-[72vh] overflow-hidden bg-white w-full">
            <div className="shrink-0 px-6 py-3.5 border-b border-gray-100 bg-white flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="m-0 text-[0.9375rem] font-semibold tracking-tight text-gray-900">Analysis Report</h2>
                <p className="m-0 mt-0.5 text-xs text-gray-500">Menu intelligence</p>
              </div>
              <button
                type="button"
                onClick={regenerateReport}
                disabled={loaderActive}
                className="shrink-0 inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2"
              >
                {loaderActive ? (
                  <>
                    <span className="h-3.5 w-3.5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    Regenerating…
                  </>
                ) : (
                  "Regenerate report"
                )}
              </button>
            </div>
            <div className="flex-1 min-h-0 min-w-0 overflow-y-auto overflow-x-auto border-l-4 border-l-primary/20 bg-[#fafbfc]">
              <div className="p-6 py-5 w-full min-w-0 max-w-none">
                {loaderActive ? (
                  <div className="flex flex-col items-center justify-center gap-4 py-12 text-gray-500 animate-fade-in">
                    <span className="h-10 w-10 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <p className="m-0 text-sm font-medium text-gray-600">Preparing your report…</p>
                  </div>
                ) : reportContent ? (
                  <ReportMarkdown content={reportContent} />
                ) : reportError ? (
                  <div className="py-10 animate-fade-in">
                    <div className="rounded-xl bg-amber-50/90 border border-amber-200/80 px-5 py-4 text-sm text-amber-900 max-w-md">
                      <p className="m-0 font-medium">Report not available</p>
                      <p className="m-0 mt-1.5 text-amber-800/90 text-xs leading-relaxed">{reportError}</p>
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

      {imageDialogOpen && imageSrc && imageAvailable && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setImageDialogOpen(false)} role="dialog" aria-modal="true" aria-label="Menu image full view">
          <div className="relative max-w-[95vw] max-h-[95vh] flex items-center justify-center" onClick={(e) => e.stopPropagation()}>
            <img src={imageSrc} alt={title} className="max-w-full max-h-[90vh] w-auto h-auto object-contain rounded-lg shadow-2xl ring-2 ring-white/20" />
          </div>
        </div>
      )}
    </main>
  );
}
