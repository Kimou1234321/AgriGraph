import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchCvaeValidation, fetchLearningCurves, fetchMetrics } from "../api";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import { useIsDark } from "../hooks/useIsDark";

export default function MethodologyView() {
  const isDark = useIsDark();
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [learning, setLearning] = useState({ cvae: [], stgnn: [] });
  const [validation, setValidation] = useState(null);
  const [selectedValidationYear, setSelectedValidationYear] = useState(null);
  const [gateFailuresOpen, setGateFailuresOpen] = useState(false);
  const selectedYearIndex =
    validation && selectedValidationYear !== null
      ? Math.max(0, validation.years.indexOf(selectedValidationYear))
      : 0;

  const gridStroke = isDark ? "#223047" : "#e2e8f0";
  const axisStroke = isDark ? "#64748b" : "#94a3b8";
  const tickFill = isDark ? "#9FB0C3" : "#475569";

  const loadMetrics = async () => {
    try {
      setLoading(true);
      setError("");
      const response = await fetchMetrics();
      const learningPayload = await fetchLearningCurves();
      const validationPayload = await fetchCvaeValidation();
      setMetrics(response);
      setLearning(learningPayload);
      setValidation(validationPayload);
      if (Array.isArray(validationPayload.years) && validationPayload.years.length > 0) {
        setSelectedValidationYear(validationPayload.years[0]);
      }
    } catch (metricError) {
      setError(metricError.message || "Unable to load metrics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, []);

  const cardShell =
    "rounded-xl border border-slate-200 bg-white p-4 dark:border-dark-border dark:bg-dark-surface";
  const headingPrimary = "text-slate-900 dark:text-dark-text-primary";
  const headingMuted = "text-slate-600 dark:text-dark-text-secondary";
  const bodyText = "text-slate-700 dark:text-dark-text-secondary";

  return (
    <section className="space-y-4">
      <div className={cardShell}>
        <h2 className={`text-xl font-semibold ${headingPrimary}`}>Methodology</h2>
        <p className={`mt-2 text-sm ${bodyText}`}>
          ICBF Data → CVAE Augmentation → PCA Pillars → Sustainability Score → STGNN Forecast → Counterfactual Simulation
        </p>
      </div>

      {loading ? <LoadingState label="Loading A7 evaluation metrics..." /> : null}
      {!loading && error ? <ErrorState message={error} onRetry={loadMetrics} /> : null}

      {!loading && !error && metrics ? (
        <div className={`${cardShell} space-y-4`}>
          <h3 className={`text-sm font-semibold uppercase tracking-wide ${headingMuted}`}>
            Phase A7 held-out 2025 evaluation
          </h3>
          <div className="mt-3 grid gap-3 md:grid-cols-6">
            <MetricCard label="Train R²" value={Number(metrics.train_r2).toFixed(3)} />
            <MetricCard label="Validation R²" value={Number(metrics.val_r2).toFixed(3)} />
            <MetricCard label="Test R²" value={Number(metrics.test_r2).toFixed(3)} />
            <MetricCard label="MAE (0-100 score)" value={Number(metrics.mae_score).toFixed(3)} />
            <MetricCard label="MSE (0-100 score)" value={Number(metrics.mse_score).toFixed(3)} />
            <MetricCard label="MAE (normalized)" value={Number(metrics.mae_norm).toFixed(3)} />
          </div>
          <p className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-200">
            Metrics are shown as-is (no retraining). Paper comparisons should use normalized MAE/MSE, while dashboard accuracy
            uses 0-100 score-space MAE/MSE.
          </p>
        </div>
      ) : null}

      {!loading && !error ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className={cardShell}>
            <h3 className={`text-sm font-semibold ${headingPrimary}`}>CVAE Learning Curve</h3>
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={learning.cvae}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="epoch" stroke={axisStroke} tick={{ fill: tickFill }} />
                  <YAxis stroke={axisStroke} tick={{ fill: tickFill }} />
                  <Tooltip
                    contentStyle={
                      isDark
                        ? { backgroundColor: "#111B2E", borderColor: "#223047", color: "#E5EEF7" }
                        : undefined
                    }
                  />
                  <Legend wrapperStyle={{ color: tickFill }} />
                  <Line dataKey="loss" stroke="#2d6a4f" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className={cardShell}>
            <h3 className={`text-sm font-semibold ${headingPrimary}`}>STGNN Fold R²</h3>
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={learning.stgnn}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="fold" stroke={axisStroke} tick={{ fill: tickFill }} />
                  <YAxis stroke={axisStroke} tick={{ fill: tickFill }} />
                  <Tooltip
                    contentStyle={
                      isDark
                        ? { backgroundColor: "#111B2E", borderColor: "#223047", color: "#E5EEF7" }
                        : undefined
                    }
                  />
                  <Legend wrapperStyle={{ color: tickFill }} />
                  <Bar dataKey="train_r2" fill="#1b4332" />
                  <Bar dataKey="val_r2" fill="#95d4b3" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && !error && validation ? (
        <div className={cardShell}>
          <h3 className={`text-sm font-semibold ${headingPrimary}`}>CVAE Validation (Year-wise means)</h3>
          <div className="mt-3 flex items-center gap-3 text-xs">
            <label htmlFor="validation-year" className={`font-semibold ${headingMuted}`}>
              Year
            </label>
            <div className="relative inline-block">
              <select
                id="validation-year"
                className="appearance-none rounded-lg border border-slate-300 bg-white py-2 pl-3 pr-9 text-sm text-slate-900 dark:border-dark-border dark:bg-dark-surface dark:text-dark-text-primary"
                value={selectedValidationYear ?? ""}
                onChange={(event) => setSelectedValidationYear(Number(event.target.value))}
              >
                {validation.years.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
              <span
                className={`pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 material-symbols-outlined text-[20px] leading-none ${headingMuted}`}
                aria-hidden
              >
                expand_more
              </span>
            </div>
          </div>
          <div className="mt-3 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={validation.features.map((feature, i) => ({
                  feature,
                  real: validation.real_means[selectedYearIndex][i],
                  synth: validation.synth_means[selectedYearIndex][i],
                }))}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                <XAxis dataKey="feature" hide />
                <YAxis stroke={axisStroke} tick={{ fill: tickFill }} />
                <Tooltip
                  contentStyle={
                    isDark
                      ? { backgroundColor: "#111B2E", borderColor: "#223047", color: "#E5EEF7" }
                      : undefined
                  }
                />
                <Legend wrapperStyle={{ color: tickFill }} />
                <Bar dataKey="real" fill="#1b4332" />
                <Bar dataKey="synth" fill="#95d4b3" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div
            className={`mt-3 rounded border p-2 text-xs ${
              validation.quality_gate?.passed
                ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-200"
            }`}
          >
            {validation.quality_gate?.passed ? (
              <p>CVAE quality gate passed. Synthetic variants met configured mean and correlation-structure checks.</p>
            ) : (
              <>
                <p className="font-medium">CVAE quality gate: diagnostic (not a loading error)</p>
                <p className="mt-1 opacity-95">
                  Phase A3 compared synthetic variants to real data against fixed thresholds. This run did not pass every
                  check. The pipeline then used the documented safe fallback: replicate real county-year rows across variant
                  ids so the graph still has five variants per node-year. API and charts loaded correctly;{" "}
                  <code className="rounded bg-black/10 px-1 dark:bg-white/10">fallback_used</code> reflects that choice.
                </p>
                {Array.isArray(validation.quality_gate?.failures) && validation.quality_gate.failures.length > 0 ? (
                  <div className="mt-2">
                    <button
                      type="button"
                      className="text-left font-semibold underline decoration-dotted hover:opacity-90"
                      onClick={() => setGateFailuresOpen((open) => !open)}
                      aria-expanded={gateFailuresOpen}
                    >
                      {gateFailuresOpen ? "Hide" : "Show"} gate details ({validation.quality_gate.failures.length})
                    </button>
                    {validation.code_quality_gate_thresholds?.correlation_frobenius_norm_max != null &&
                    validation.quality_gate?.thresholds?.correlation_frobenius_norm_max != null &&
                    Number(validation.quality_gate.thresholds.correlation_frobenius_norm_max) !==
                      Number(validation.code_quality_gate_thresholds.correlation_frobenius_norm_max) ? (
                      <p className="mt-2 rounded border border-slate-200/80 bg-black/5 p-2 opacity-95 dark:border-dark-border dark:bg-white/5">
                        The lines below use the correlation Frobenius cap from the last Phase A3 run on disk (
                        {validation.quality_gate.thresholds.correlation_frobenius_norm_max}). The codebase threshold is now{" "}
                        {validation.code_quality_gate_thresholds.correlation_frobenius_norm_max}. Re-run Phase A3 to refresh{" "}
                        <code className="rounded bg-black/10 px-1 dark:bg-white/10">cvae_validation_summary.json</code> and
                        augmented outputs.
                      </p>
                    ) : null}
                    {gateFailuresOpen ? (
                      <ul className="mt-2 list-inside list-disc space-y-1 opacity-95">
                        {validation.quality_gate.failures.map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 opacity-90">
                        First checks: {validation.quality_gate.failures.slice(0, 2).join(" · ")}
                        {validation.quality_gate.failures.length > 2 ? " …" : ""}
                      </p>
                    )}
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      ) : null}

      <div className={`${cardShell} space-y-2 text-sm ${bodyText}`}>
        <h3 className={`text-sm font-semibold ${headingPrimary}`}>Two-model transparency</h3>
        <p>Evaluation metrics are from `stgnn_eval_weights.pt` (held-out 2025).</p>
        <p>Forecasting and simulation use `stgnn_forecast_weights.pt` (full-data retrain).</p>
      </div>

      <div className={`${cardShell} text-sm ${bodyText}`}>
        <h3 className={`text-sm font-semibold ${headingPrimary}`}>Prototype transparency</h3>
        <p className="mt-2">
          This prototype uses county-level operational indicators as sustainability proxies. It does not include direct emissions,
          farm-level onboarding, climate APIs, milk-production prediction, or full SHAP explanations.
        </p>
      </div>
    </section>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-dark-border dark:bg-dark-surface/80">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-dark-text-secondary">{label}</p>
      <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-dark-text-primary">{value}</p>
    </div>
  );
}
