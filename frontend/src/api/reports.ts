/** Shared report API base path and helpers for cached + generate flows. */

export const REPORT_API_BASE = "/api/reports/report";
export const REPORT_OVERALL_API = "/api/reports/overall";
export const DEFAULT_STATION = "Grill";
export const MEAL_PERIODS = ["Breakfast", "Lunch", "Dinner"] as const;

export function reportCachedUrl(station: string, mealPeriod: string): string {
  const s = station.toLowerCase().replace(/\s+/g, "_");
  const m = mealPeriod.toLowerCase().replace(/\s+/g, "_");
  return `${REPORT_API_BASE}/${s}/${m}`;
}

export interface ReportResponse {
  content: string;
  station_name?: string;
  meal_period?: string;
  generated_at?: string;
}
