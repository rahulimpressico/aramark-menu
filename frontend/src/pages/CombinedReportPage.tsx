import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { AramarkLogo } from "../components/AramarkLogo";
import { ReportMarkdown } from "../components/ReportMarkdown";

const REPORT_API = "/api/reports/report";
const REPORT_CACHED_API = "/api/reports/report";
const DEFAULT_STATION = "Grill";
const MEAL_PERIODS = ["Breakfast", "Lunch", "Dinner"] as const;

function reportCachedUrl(station: string, mealPeriod: string): string {
  const s = station.toLowerCase().replace(/\s+/g, "_");
  const m = mealPeriod.toLowerCase().replace(/\s+/g, "_");
  return `${REPORT_CACHED_API}/${s}/${m}`;
}

type ReportSection =
  | { meal_period: string; content: string; generated_at?: string }
  | { meal_period: string; error: true };

export function CombinedReportPage() {
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [anyError, setAnyError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const results = await Promise.all(
        MEAL_PERIODS.map(async (meal_period): Promise<ReportSection> => {
          try {
            const cachedRes = await fetch(reportCachedUrl(DEFAULT_STATION, meal_period));
            if (cachedRes.ok) {
              const data = await cachedRes.json();
              const text = (data.content ?? "").trim();
              if (text) {
                return {
                  meal_period: data.meal_period ?? meal_period,
                  content: text,
                  generated_at: data.generated_at,
                };
              }
            }
            const res = await fetch(REPORT_API, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                station_name: DEFAULT_STATION,
                meal_period,
              }),
            });
            if (!res.ok) return { meal_period, error: true };
            const data = await res.json();
            return {
              meal_period: data.meal_period ?? meal_period,
              content: data.content ?? "",
              generated_at: data.generated_at,
            };
          } catch {
            return { meal_period, error: true };
          }
        })
      );
      if (cancelled) return;
      setSections(results);
      setAnyError(results.some((r) => "error" in r && r.error));
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <main className="min-h-0 flex-1 flex flex-col bg-[#f5f5f5]">
      {/* Premium header */}
      <header className="shrink-0 border-b border-gray-200/90 bg-white shadow-sm">
        <div className="max-w-[1000px] mx-auto px-5 py-4 flex flex-wrap items-center justify-between gap-4">
          <Link
            to="/meal-period"
            className="inline-flex items-center gap-2 text-[0.9375rem] font-medium text-gray-500 no-underline transition-colors hover:text-primary focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 rounded shrink-0"
          >
            <span aria-hidden>←</span>
            Back to Menu Analysis
          </Link>
          <div className="flex items-center gap-3">
            <AramarkLogo width={120} height={30} />
          </div>
        </div>
      </header>

      {/* Hero strip */}
      <div className="shrink-0 bg-gradient-to-r from-footer-bg via-[#034078] to-[#055c9e] text-white">
        <div className="max-w-[1000px] mx-auto px-5 py-6">
          <h1 className="m-0 text-xl sm:text-2xl font-bold tracking-tight">
            Combined Menu Report
          </h1>
          <p className="m-0 mt-1.5 text-sm text-white/90 max-w-[50ch]">
            Full analysis across all meal periods — structure, playbook alignment, rotation, and recommendations.
          </p>
        </div>
      </div>

      {/* Report content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-[1000px] mx-auto px-5 py-6">
          <div className="rounded-2xl border border-gray-200/90 bg-white shadow-sm overflow-hidden">
            <div className="p-6 sm:p-8 border-l-4 border-l-primary/30 bg-[#fafbfc]">
              {loading ? (
                <div className="flex flex-col items-center justify-center gap-4 py-16 text-gray-500">
                  <span className="h-10 w-10 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  <p className="m-0 text-sm font-medium text-gray-600">
                    Generating reports for Breakfast, Lunch & Dinner…
                  </p>
                </div>
              ) : anyError && sections.every((s) => "error" in s && s.error) ? (
                <div className="py-10">
                  <div className="rounded-xl bg-amber-50/90 border border-amber-200/80 px-5 py-4 text-sm text-amber-900 max-w-md">
                    <p className="m-0 font-medium">Reports not available</p>
                    <p className="m-0 mt-1.5 text-amber-800/90 text-xs leading-relaxed">
                      Ensure the menu analyzer is available (<code className="bg-amber-100/80 px-1.5 py-0.5 rounded">uv sync --extra experiments</code>) or try again.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-10">
                  {sections.map((section) => {
                    if ("error" in section && section.error) {
                      return (
                        <div key={section.meal_period} className="rounded-xl bg-amber-50/90 border border-amber-200/80 px-5 py-4 text-sm text-amber-900">
                          <p className="m-0 font-medium">{section.meal_period} — Report could not be generated.</p>
                        </div>
                      );
                    }
                    const s = section as { meal_period: string; content: string; generated_at?: string };
                    return (
                      <section key={s.meal_period}>
                        <h2 className="text-lg font-semibold text-gray-900 mb-3 border-b border-gray-200 pb-2">
                          {s.meal_period}
                          {s.generated_at && (
                            <span className="ml-2 text-xs font-normal text-gray-500">
                              {new Date(s.generated_at).toLocaleString()}
                            </span>
                          )}
                        </h2>
                        <ReportMarkdown content={s.content} />
                      </section>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
