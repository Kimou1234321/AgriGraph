import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchPillarsPreview, runCounterfactual } from "../api";
import ChartPanel from "../components/ChartPanel";
import ErrorState from "../components/ErrorState";
import InterventionSlider from "../components/InterventionSlider";
import PillarRadar from "../components/PillarRadar";
import SustainabilityChart from "../components/SustainabilityChart";
import XAIExplanation from "../components/XAIExplanation";

const SLIDERS = [
  { key: "calving_interval", label: "Calving Interval" },
  { key: "recycled_cows_pct", label: "Recycled Cows" },
  { key: "cows_culled_pct", label: "Cows Culled" },
  { key: "six_wk_calving_rate", label: "6-Week Calving Rate" },
  { key: "replacements_dairy_ai_pct", label: "Replacements to Dairy AI" },
  { key: "mortality_dead_at_birth", label: "Mortality at Birth" },
];

const PRESETS = {
  "Optimize Reproduction": { calving_interval: -0.1, recycled_cows_pct: 0.1 },
  "Reduce Losses": { cows_culled_pct: -0.1, mortality_dead_at_birth: -0.15 },
  "Improve Genetics": { replacements_dairy_ai_pct: 0.15, births_known_sire_pct: 0.1 },
};

function emptyInterventions() {
  return Object.fromEntries(SLIDERS.map((slider) => [slider.key, 0]));
}

export default function CounterfactualView({ counties, selectedCounty, setSelectedCounty }) {
  const [interventions, setInterventions] = useState(emptyInterventions());
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const [error, setError] = useState("");

  const hasAnyChange = useMemo(
    () => Object.values(interventions).some((value) => Math.abs(value) > 0),
    [interventions]
  );

  const applyPreset = (presetName) => {
    const preset = PRESETS[presetName] ?? {};
    setInterventions((prev) => ({ ...prev, ...preset }));
  };

  const refreshPreview = async (nextInterventions) => {
    if (!selectedCounty) return;
    try {
      setLoadingPreview(true);
      const payload = { county: selectedCounty, interventions: nextInterventions };
      const data = await fetchPillarsPreview(payload);
      setPreview(data);
    } catch (previewError) {
      setError(previewError.message || "Unable to load pillar preview.");
    } finally {
      setLoadingPreview(false);
    }
  };

  const updateSlider = (key, value) => {
    setInterventions((prev) => {
      const next = { ...prev, [key]: value };
      refreshPreview(next);
      return next;
    });
  };

  const runScenario = async () => {
    try {
      setLoadingRun(true);
      setError("");
      const payload = { county: selectedCounty, interventions, horizon: 11 };
      const response = await runCounterfactual(payload);
      setResult(response);
    } catch (runError) {
      setError(runError.message || "Simulation failed.");
    } finally {
      setLoadingRun(false);
    }
  };

  const counterfactualChartData = (result?.baseline ?? []).map((row, index) => ({
    year: row.year,
    baseline: Number(row.score),
    counterfactual: Number(result.counterfactual?.[index]?.score ?? row.score),
  }));
  const upliftChartData = (result?.uplift ?? []).map((row) => ({
    year: row.year,
    delta: Number(row.delta),
  }));
  const finalYear = upliftChartData.length ? upliftChartData[upliftChartData.length - 1].year : 2036;
  const upliftFinalYear = upliftChartData.find((row) => row.year === finalYear)?.delta ?? 0;

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Counterfactual Simulation</h2>
          <select
            value={selectedCounty}
            onChange={(event) => setSelectedCounty(event.target.value)}
            className="rounded border border-slate-300 px-3 py-2 text-sm"
          >
            {counties.map((county) => (
              <option key={county} value={county}>
                {county}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.keys(PRESETS).map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => {
                applyPreset(name);
                refreshPreview({ ...interventions, ...(PRESETS[name] ?? {}) });
              }}
              className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700"
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          {SLIDERS.map((slider) => (
            <InterventionSlider
              key={slider.key}
              label={slider.label}
              value={interventions[slider.key] ?? 0}
              onChange={(value) => updateSlider(slider.key, value)}
            />
          ))}
          <button
            type="button"
            onClick={runScenario}
            disabled={!hasAnyChange || loadingRun}
            className="w-full rounded bg-[#2D6A4F] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined text-base">play_arrow</span>
            {loadingRun ? "Running simulation..." : "Run Simulation"}
          </button>
        </div>

        <ChartPanel title="Pillar impact preview" subtitle="Before STGNN propagation">
          {loadingPreview ? <p className="text-sm text-slate-600">Updating preview...</p> : null}
          {preview ? (
            <PillarRadar labels={Object.keys(preview.before)} before={preview.before} after={preview.after} />
          ) : (
            <p className="text-sm text-slate-600">Adjust sliders to preview pillar impact.</p>
          )}
        </ChartPanel>
      </div>

      {error ? <ErrorState message={error} /> : null}

      {result ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <ChartPanel title="Baseline vs counterfactual" subtitle="2026-2036 score trajectory (with explicit uplift)">
            <div className="mb-3 flex items-center gap-2">
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
                {finalYear} uplift: {upliftFinalYear > 0 ? "+" : ""}
                {upliftFinalYear.toFixed(1)} points
              </span>
            </div>
            <SustainabilityChart data={counterfactualChartData} mode="counterfactual" />
          </ChartPanel>
          <ChartPanel title="Year-by-year uplift" subtitle="Counterfactual - baseline">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={upliftChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" />
                <YAxis />
                <Tooltip formatter={(value) => `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(1)}`} />
                <Bar dataKey="delta" fill="#2d6a4f" />
              </BarChart>
            </ResponsiveContainer>
          </ChartPanel>
          <div className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-1">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><span className="material-symbols-outlined">psychology</span>AI Analysis</h3>
            <XAIExplanation text={result.explanation} />
          </div>
        </div>
      ) : null}
    </section>
  );
}

