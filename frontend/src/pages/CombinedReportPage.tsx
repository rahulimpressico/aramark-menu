import { useCallback, useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { DEFAULT_STATION, REPORT_OVERALL_API } from "../api/reports";
import { AramarkLogo } from "../components/AramarkLogo";
import { ReportMarkdown } from "../components/ReportMarkdown";

function useOverallReport() {
  const [overallContent, setOverallContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOverall = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(REPORT_OVERALL_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ station_name: DEFAULT_STATION }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = err?.detail ?? (res.status === 404
          ? "No cached reports. Generate Breakfast, Lunch & Dinner reports first from the meal-period pages."
          : "Overall report could not be generated. Try again.");
        setError(msg);
        setOverallContent(null);
        return;
      }
      const data = await res.json();
      setOverallContent(data.content ?? "");
      setError(null);
    } catch {
      setError("Failed to load overall report. Try again.");
      setOverallContent(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return { overallContent, loading, error, fetchOverall };
}

export function CombinedReportPage() {
  const { overallContent, loading, error, fetchOverall } = useOverallReport();

  useEffect(() => {
    fetchOverall();
  }, [fetchOverall]);

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
              {!loading && (overallContent || error) && (
                <div className="flex justify-end mb-4">
                  <button
                    type="button"
                    onClick={() => fetchOverall()}
                    disabled={loading}
                    className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2"
                  >
                    Regenerate overall report
                  </button>
                </div>
              )}
              {loading ? (
                <div className="flex flex-col items-center justify-center gap-4 py-16 text-gray-500">
                  <span className="h-10 w-10 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  <p className="m-0 text-sm font-medium text-gray-600">
                    Generating overall report from Breakfast, Lunch & Dinner…
                  </p>
                </div>
              ) : error ? (
                <div className="py-10">
                  <div className="rounded-xl bg-amber-50/90 border border-amber-200/80 px-5 py-4 text-sm text-amber-900 max-w-md">
                    <p className="m-0 font-medium">Overall report not available</p>
                    <p className="m-0 mt-1.5 text-amber-800/90 text-xs leading-relaxed">
                      {error}
                    </p>
                  </div>
                </div>
              ) : overallContent ? (
                <ReportMarkdown content={overallContent} />
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
