/** Shared report API base path and helpers for cached + generate flows. */

export const REPORT_API_BASE = "/api/reports/report";
export const REPORT_OVERALL_API = "/api/reports/overall";
export const REPORT_COMBINED_BASE = "/api/reports/combined";
export const DEFAULT_STATION = "Grill";
export const MEAL_PERIODS = ["Breakfast", "Lunch", "Dinner"] as const;

export function reportCachedUrl(station: string, mealPeriod: string): string {
  const s = station.toLowerCase().replace(/\s+/g, "_");
  const m = mealPeriod.toLowerCase().replace(/\s+/g, "_");
  return `${REPORT_API_BASE}/${s}/${m}`;
}

/** URL for combined report (Breakfast + Lunch + Dinner in one response). */
export function reportCombinedUrl(station: string): string {
  const s = station.toLowerCase().replace(/\s+/g, "_");
  return `${REPORT_COMBINED_BASE}/${s}`;
}

export interface ReportUsage {
  total_input_tokens: number;
  total_output_tokens: number;
  cost_usd?: number;
}

export interface ReportResponse {
  content: string;
  station_name?: string;
  meal_period?: string;
  generated_at?: string;
  total_input_tokens?: number;
  total_output_tokens?: number;
  cost_usd?: number;
}
