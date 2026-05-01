import { useEffect, useMemo, useState } from "react";
import { extractPillarNormKeys, fetchIndicators, fetchPillars, mergeCountyTimeline } from "../api";
import ChartPanel from "../components/ChartPanel";
import ErrorState from "../components/ErrorState";
import KpiCard from "../components/KpiCard";
import LoadingState from "../components/LoadingState";
import PillarRadar from "../components/PillarRadar";
import SustainabilityChart from "../components/SustainabilityChart";

const YEARS = Array.from({ length: 16 }, (_, index) => 2021 + index);

export default function CountyDashboard({
  counties,
  historical,
  forecast,
  selectedCounty,
  setSelectedCounty,
  selectedYear,
  setSelectedYear,
}) {
  const [pillars, setPillars] = useState([]);
  const [loadingPillars, setLoadingPillars] = useState(false);
  const [pillarError, setPillarError] = useState("");
  const [indicators, setIndicators] = useState(null);

  const loadPillars = async () => {
    if (!selectedCounty) return;
    try {
      setLoadingPillars(true);
      setPillarError("");
      const rows = await fetchPillars(selectedCounty);
      setPillars(rows);
    } catch (error) {
      setPillarError(error.message || "Unable to load pillar data.");
    } finally {
      setLoadingPillars(false);
    }
  };

  useEffect(() => {
    loadPillars();
  }, [selectedCounty]);

  useEffect(() => {
    let cancelled = false;
    const loadIndicators = async () => {
      if (!selectedCounty) return;
      const data = await fetchIndicators(selectedCounty, selectedYear);
      if (!cancelled) setIndicators(data);
    };
    loadIndicators();
    return () => {
      cancelled = true;
    };
  }, [selectedCounty, selectedYear]);

  const timeline = useMemo(() => {
    const merged = mergeCountyTimeline(selectedCounty, historical, forecast);
    return merged.map((row) => ({
      year: row.year,
      historical: row.score,
      forecast: row.predicted_score,
      lower_5pct: row.lower_5pct,
      upper_95pct: row.upper_95pct,
    }));
  }, [selectedCounty, historical, forecast]);

  const latestScore = timeline.find((row) => row.year === selectedYear);
  const pillarKeys = extractPillarNormKeys(pillars);
  const selectedPillarRow = pillars.find((row) => Number(row.year) === selectedYear);
  const radarSingle = pillarKeys.map((key) => ({
    pillar: key.replaceAll("_norm", "").replaceAll("_", " "),
    value: Number(selectedPillarRow?.[key] ?? 0),
  }));

  return (
    <section className="space-y-4">
      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">County</span>
          <select
            value={selectedCounty}
            onChange={(event) => setSelectedCounty(event.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2"
          >
            {counties.map((county) => (
              <option key={county} value={county}>
                {county}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Year</span>
          <select
            value={selectedYear}
            onChange={(event) => setSelectedYear(Number(event.target.value))}
            className="w-full rounded border border-slate-300 px-3 py-2"
          >
            {YEARS.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <KpiCard label="Score" value={latestScore ? (latestScore.forecast ?? latestScore.historical ?? 0).toFixed(1) : "—"} tone="good" />
        <KpiCard label="Calving interval" value={indicators?.calving_interval?.toFixed?.(1) ?? "—"} tone="warn" />
        <KpiCard label="6-week calving rate" value={indicators?.six_wk_calving_rate?.toFixed?.(1) ?? "—"} />
        <KpiCard label="Culling rate" value={indicators?.cows_culled_pct?.toFixed?.(1) ?? "—"} tone="risk" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartPanel
          title="Sustainability trajectory"
          subtitle="Historical 2021-2025, forecast 2026-2036 with 90% confidence band"
        >
          <SustainabilityChart data={timeline} />
        </ChartPanel>
        <ChartPanel title="Pillar radar" subtitle={`Pillars for ${selectedCounty} in ${selectedYear}`}>
          {loadingPillars ? <LoadingState label="Loading pillar profile..." /> : null}
          {!loadingPillars && pillarError ? <ErrorState message={pillarError} onRetry={loadPillars} /> : null}
          {!loadingPillars && !pillarError ? <PillarRadar single={radarSingle} /> : null}
        </ChartPanel>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        {pillarKeys.map((key) => (
          <ChartPanel key={key} title={key.replaceAll("_norm", "").replaceAll("_", " ")}>
            <SustainabilityChart
              mode="counterfactual"
              data={pillars.map((row) => ({ year: row.year, baseline: row[key], counterfactual: null }))}
            />
          </ChartPanel>
        ))}
      </div>
    </section>
  );
}

