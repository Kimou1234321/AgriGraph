import { API_BASE_URL } from "./config";

const CONSTANTS = {
  HISTORICAL_END_YEAR: 2025,
  FORECAST_END_YEAR: 2036,
  FORECAST_START_YEAR: 2026,
  SCORE_TOP_THRESHOLD: 75,
  SCORE_MID_THRESHOLD: 50,
};

async function parseError(response) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg).join(", ");
    if (payload.error) return payload.error;
  } catch {
    // ignore parse failure
  }
  return `API failed with status ${response.status}.`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    credentials: "include",
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function signup(payload) {
  return requestJson("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function login(payload) {
  return requestJson("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function logout() {
  return requestJson("/auth/logout", { method: "POST" });
}

export async function fetchMe() {
  return requestJson("/auth/me");
}

export async function saveSimulation(payload) {
  return requestJson("/simulations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchSavedSimulations() {
  return requestJson("/simulations");
}

export async function fetchSavedSimulation(id) {
  return requestJson(`/simulations/${encodeURIComponent(id)}`);
}

export async function deleteSavedSimulation(id) {
  return requestJson(`/simulations/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function fetchCounties() {
  return requestJson("/counties");
}

export async function fetchHistorical() {
  return requestJson("/historical");
}

export async function fetchForecast() {
  return requestJson("/forecast");
}

export async function fetchPillars(county) {
  return requestJson(`/pillars/${encodeURIComponent(county)}`);
}

export async function fetchPillarsPreview(payload) {
  return requestJson("/pillars/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function runCounterfactual(payload) {
  return requestJson("/counterfactual", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function runCounterfactualGlobal(payload) {
  return requestJson("/counterfactual/global", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchComparison() {
  return requestJson("/comparison");
}

export async function fetchMetrics() {
  return requestJson("/metrics");
}

export async function fetchIndicators(county, year) {
  return requestJson(`/county/${encodeURIComponent(county)}/indicators?year=${encodeURIComponent(year)}`);
}

export async function fetchLearningCurves() {
  return requestJson("/methodology/learning_curves");
}

export async function fetchCvaeValidation() {
  return requestJson("/methodology/cvae_validation");
}

export function toScoreTier(score) {
  if (score > CONSTANTS.SCORE_TOP_THRESHOLD) return "Top";
  if (score >= CONSTANTS.SCORE_MID_THRESHOLD) return "Mid";
  return "Low";
}

export function mergeCountyTimeline(county, historicalRows, forecastRows) {
  const historical = historicalRows
    .filter((row) => row.county === county)
    .map((row) => ({
      county: row.county,
      year: Number(row.year),
      score: Number(row.score),
      predicted_score: null,
      lower_5pct: null,
      upper_95pct: null,
      phase: "historical",
    }));

  const forecast = forecastRows
    .filter((row) => row.county === county)
    .map((row) => ({
      county: row.county,
      year: Number(row.year),
      score: null,
      predicted_score: Number(row.predicted_score),
      lower_5pct: Number(row.lower_5pct),
      upper_95pct: Number(row.upper_95pct),
      phase: "forecast",
    }));

  return [...historical, ...forecast].sort((a, b) => a.year - b.year);
}

export function extractPillarKeys(rows) {
  if (!rows || rows.length === 0) return [];
  return Object.keys(rows[0]).filter((key) => key !== "year" && !key.endsWith("_norm"));
}

export function extractPillarNormKeys(rows) {
  if (!rows || rows.length === 0) return [];
  return Object.keys(rows[0]).filter((key) => key.endsWith("_norm"));
}

export function getCountyScoreForYear(county, year, historicalRows, forecastRows) {
  if (year <= CONSTANTS.HISTORICAL_END_YEAR) {
    const row = historicalRows.find((item) => item.county === county && Number(item.year) === year);
    return row ? Number(row.score) : null;
  }
  const forecast = forecastRows.find((item) => item.county === county && Number(item.year) === year);
  return forecast ? Number(forecast.predicted_score) : null;
}

/** Score for UI when toggling Initial vs Simulation (counterfactual exists only for forecast years). */
export function getCountyScoreForYearWithSimulation(
  county,
  year,
  historicalRows,
  forecastRows,
  simulationResults,
  viewMode
) {
  if (
    viewMode === "simulation" &&
    simulationResults?.by_county?.[county] &&
    year >= CONSTANTS.FORECAST_START_YEAR
  ) {
    const rows = simulationResults.by_county[county].counterfactual ?? [];
    const row = rows.find((item) => Number(item.year) === year);
    if (row && Number.isFinite(Number(row.score))) return Number(row.score);
  }
  return getCountyScoreForYear(county, year, historicalRows, forecastRows);
}

export function countyTrendFromScores(score2025, score2030) {
  if (score2025 === null || score2030 === null) return "—";
  if (score2030 > score2025) return "↑";
  if (score2030 < score2025) return "↓";
  return "→";
}

export function forecastYears() {
  return Array.from(
    { length: CONSTANTS.FORECAST_END_YEAR - CONSTANTS.FORECAST_START_YEAR + 1 },
    (_, index) => CONSTANTS.FORECAST_START_YEAR + index
  );
}
