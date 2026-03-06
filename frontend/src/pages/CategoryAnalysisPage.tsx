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
const CATEGORY_KEYS = ["breakfast", "lunch", "dinner"] as const;

type SourceRow = {
  id: string;
  name: string;
  food_cost?: number;
  ing_count?: number;
};

type DaywiseRow = {
  day: string;
  recipes: string[];
};

const DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

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

function extractDaywiseRows(data: any): DaywiseRow[] {
  const schedule = data?.analysis?.schedule;
  if (!schedule || typeof schedule !== "object") return [];
  const ordered = DAY_ORDER
    .filter((day) => Array.isArray((schedule as Record<string, unknown>)[day]))
    .map((day) => ({
      day,
      recipes: ((schedule as Record<string, unknown[]>)[day] || [])
        .map((item) => String(item ?? "").trim())
        .filter(Boolean),
    }))
    .filter((row) => row.recipes.length > 0);
  return ordered;
}


function normalizeReportError(message: string): string {
  if (message.toLowerCase().includes("no data found for station")) {
    return "No data available for this station and meal period yet.";
  }
  return message;
}

function isNoDataError(message: string): boolean {
  return message.toLowerCase().includes("no data found for station");
}

export function CategoryAnalysisPage() {
  const { stationSlug, category } = useParams<{ stationSlug: string; category: string }>();
  const navigate = useNavigate();
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [loaderActive, setLoaderActive] = useState(false);
  const [reportContent, setReportContent] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [daywiseRows, setDaywiseRows] = useState<DaywiseRow[]>([]);
  const [sourceRows, setSourceRows] = useState<SourceRow[]>([]);

  const normalizedStationSlug = stationSlug?.trim().toLowerCase() || "";
  const normalizedCategory = category?.trim().toLowerCase() || "";
  const displayStationName = stationNameFromSlug(normalizedStationSlug || "grill");
  const stationName = backendStationNameFromSlug(normalizedStationSlug || "grill");
  const title =
    normalizedCategory && CATEGORIES[normalizedCategory]
      ? `${displayStationName} ${CATEGORIES[normalizedCategory]} Menu`
      : `${displayStationName} Menu`;

  const hasExcelData = sourceRows.length > 0;
  const hasDaywiseData = daywiseRows.length > 0;
  const daywiseByDay = daywiseRows.reduce<Record<string, string[]>>((acc, row) => {
    acc[row.day] = row.recipes;
    return acc;
  }, {});

  useEffect(() => {
    if (!analysisOpen || !normalizedCategory || !CATEGORIES[normalizedCategory]) return;
    setReportContent(null);
    setReportError(null);
    setDaywiseRows([]);
    setSourceRows([]);
    setLoaderActive(true);
    let cancelled = false;
    const mealPeriod = CATEGORIES[normalizedCategory];
    (async () => {
      const loadReport = async (period: string): Promise<{ ok: true; data: any } | { ok: false; message: string; noData: boolean }> => {
        try {
          const cachedRes = await fetch(reportCachedUrl(stationName, period));
          if (cachedRes.ok) {
            const data = await cachedRes.json();
            const text = data.content ?? "";
            if (text.trim()) return { ok: true, data };
          }

          const res = await fetch(REPORT_API_BASE, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              station_name: stationName,
              meal_period: period,
              use_fast: true,
            }),
          });

          if (res.ok) {
            const data = await res.json();
            return { ok: true, data };
          }

          let message = res.status === 503 ? "Report could not be generated. Please try again." : "Report not available.";
          try {
            const err = await res.json();
            if (err?.detail) message = typeof err.detail === "string" ? err.detail : err.detail?.msg ?? message;
          } catch {
            // keep default message
          }
          return { ok: false, message, noData: isNoDataError(message) };
        } catch {
          const message = "Report not available. Please try again.";
          return { ok: false, message, noData: false };
        }
      };

      try {
        const current = await loadReport(mealPeriod);
        if (cancelled) return;

        if (current.ok) {
          setReportContent(current.data.content ?? "");
          setDaywiseRows(extractDaywiseRows(current.data));
          setSourceRows(extractSourceRows(current.data));
          setReportError(null);
          return;
        }

        if (current.noData) {
          for (const key of CATEGORY_KEYS) {
            if (key === normalizedCategory) continue;
            const fallbackPeriod = CATEGORIES[key];
            const fallback = await loadReport(fallbackPeriod);
            if (cancelled) return;
            if (fallback.ok) {
              navigate(`/stations/${normalizedStationSlug}/${key}`, { replace: true });
              return;
            }
          }
        }

        setReportError(normalizeReportError(current.message));
      } finally {
        if (!cancelled) setLoaderActive(false);
      }
    })();
    return () => { cancelled = true; };
  }, [analysisOpen, normalizedCategory, normalizedStationSlug, stationName, navigate]);

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
        setDaywiseRows(extractDaywiseRows(data));
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
      <div className="flex-1 relative flex flex-col lg:flex-row gap-4 lg:gap-5 m-3 sm:m-4 min-h-0">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0" aria-hidden>
          <div className="opacity-[0.06] select-none">
            <AramarkLogo width={280} height={70} variant="default" />
          </div>
        </div>
        <div className="relative z-10 flex-1 flex flex-col lg:flex-row gap-4 lg:gap-5 min-h-0 min-w-0">
          <section className="w-full lg:w-[45%] xl:w-[40%] flex-shrink-0 opacity-0-init animate-slide-up rounded-xl bg-white shadow-xl border border-gray-200/90 overflow-hidden flex flex-col h-[58vh] sm:h-[65vh] lg:h-[72vh] transition-shadow duration-300 hover:shadow-2xl">
            <div className="shrink-0 px-4 sm:px-5 py-3 sm:py-3.5 border-b border-gray-100 bg-white">
              <h2 className="m-0 text-[0.9375rem] font-semibold tracking-tight text-gray-900">{title}</h2>
              <p className="m-0 mt-0.5 text-xs text-gray-500">Reference source data</p>
            </div>
            <div className="flex-1 min-h-0 p-3 sm:p-4 overflow-y-auto bg-gray-50/40">
              <div className="rounded-lg border border-gray-200 bg-white overflow-hidden mb-4">
                <div className="px-3 py-2 border-b border-gray-200 bg-gray-50 text-xs font-semibold text-gray-700">
                  Day-wise menu (Excel/KG)
                </div>
                {hasDaywiseData ? (
                  <div className="max-h-[260px] overflow-x-auto overflow-y-auto">
                    <table className="min-w-[980px] w-full text-xs text-left text-gray-700">
                      <thead className="bg-gray-50 text-gray-800 sticky top-0 z-10">
                        <tr>
                          {DAY_ORDER.map((day) => (
                            <th key={day} className="px-3 py-2.5 min-w-[180px] border-b border-gray-200 font-semibold">{day}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          {DAY_ORDER.map((day) => {
                            const recipes = daywiseByDay[day] || [];
                            return (
                              <td key={day + "-count"} className="px-3 pt-2 pb-1 border-r border-gray-100 last:border-r-0 bg-white text-center">
                                {recipes.length > 0 ? (
                                  <span className="inline-flex min-w-[78px] items-center justify-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
                                    {recipes.length} item(s)
                                  </span>
                                ) : (
                                  <span className="text-gray-400 text-[10px]">0 item(s)</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                        <tr className="align-top">
                          {DAY_ORDER.map((day) => {
                            const recipes = daywiseByDay[day] || [];
                            return (
                              <td key={day + "-recipes"} className="px-3 py-1.5 border-r border-gray-100 last:border-r-0 bg-white">
                                {recipes.length > 0 ? (
                                  <div className="space-y-1.5">
                                    {recipes.map((name, idx) => (
                                      <div
                                        key={day + "-" + idx}
                                        className="rounded-md border border-gray-100 bg-gray-50 px-2 py-1 leading-snug text-gray-700 whitespace-normal break-words"
                                      >
                                        {name}
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="text-gray-400">-</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-3 text-xs text-gray-500">
                    Day-wise source rows are not available for this station/meal.
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
                <div className="px-3 py-2 border-b border-gray-200 bg-gray-50 text-xs font-semibold text-gray-700">
                  Source recipes used (Excel/KG)
                </div>
                {hasExcelData ? (
                  <div className="max-h-[280px] overflow-x-auto overflow-y-auto">
                    <table className="min-w-[980px] w-full text-xs text-left text-gray-700">
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

          <section className="w-full flex-1 min-h-0 min-w-0 opacity-0-init animate-slide-up delay-100 flex flex-col rounded-xl shadow-xl border border-gray-200/90 h-[58vh] sm:h-[65vh] lg:h-[72vh] overflow-hidden bg-white">
            <div className="shrink-0 px-4 sm:px-6 py-3 sm:py-3.5 border-b border-gray-100 bg-white flex flex-wrap items-center justify-between gap-3">
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
    </main>
  );
}
