import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchCvaeValidation, fetchLearningCurves, fetchMetrics } from "../api";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";

export default function MethodologyView() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [learning, setLearning] = useState({ cvae: [], stgnn: [] });
  const [validation, setValidation] = useState(null);
  const [selectedValidationYear, setSelectedValidationYear] = useState(null);
  const selectedYearIndex =
    validation && selectedValidationYear !== null
      ? Math.max(0, validation.years.indexOf(selectedValidationYear))
      : 0;

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

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-xl font-semibold text-slate-900">Methodology</h2>
        <p className="mt-2 text-sm text-slate-700">
          ICBF Data → CVAE Augmentation → PCA Pillars → Sustainability Score → STGNN Forecast → Counterfactual Simulation
        </p>
      </div>

      {loading ? <LoadingState label="Loading A7 evaluation metrics..." /> : null}
      {!loading && error ? <ErrorState message={error} onRetry={loadMetrics} /> : null}

      {!loading && !error && metrics ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
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
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
            Metrics are shown as-is (no retraining). Paper comparisons should use normalized MAE/MSE, while dashboard accuracy uses 0-100 score-space MAE/MSE.
          </p>
        </div>
      ) : null}

      {!loading && !error ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900">CVAE Learning Curve</h3>
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={learning.cvae}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="epoch" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line dataKey="loss" stroke="#2d6a4f" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900">STGNN Fold R²</h3>
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={learning.stgnn}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="fold" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="train_r2" fill="#1b4332" />
                  <Bar dataKey="val_r2" fill="#95d4b3" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && !error && validation ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-slate-900">CVAE Validation (Year-wise means)</h3>
          <div className="mt-3 flex items-center gap-3 text-xs">
            <label htmlFor="validation-year" className="font-semibold text-slate-700">
              Year
            </label>
            <select
              id="validation-year"
              className="rounded border border-slate-300 px-2 py-1"
              value={selectedValidationYear ?? ""}
              onChange={(event) => setSelectedValidationYear(Number(event.target.value))}
            >
              {validation.years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
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
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="feature" hide />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="real" fill="#1b4332" />
                <Bar dataKey="synth" fill="#95d4b3" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p
            className={`mt-3 rounded border p-2 text-xs ${
              validation.quality_gate?.passed
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-amber-200 bg-amber-50 text-amber-700"
            }`}
          >
            {validation.quality_gate?.passed
              ? "CVAE quality gate passed."
              : `CVAE quality gate failed; fallback used=${String(validation.quality_gate?.fallback_used)}.`}
          </p>
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700 space-y-2">
        <h3 className="text-sm font-semibold text-slate-900">Two-model transparency</h3>
        <p>Evaluation metrics are from `stgnn_eval_weights.pt` (held-out 2025).</p>
        <p>Forecasting and simulation use `stgnn_forecast_weights.pt` (full-data retrain).</p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
        <h3 className="text-sm font-semibold text-slate-900">Prototype transparency</h3>
        <p className="mt-2">
          This prototype uses county-level operational indicators as sustainability proxies. It does not include direct emissions, farm-level onboarding, climate APIs, milk-production prediction, or full SHAP explanations.
        </p>
      </div>
    </section>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">{label}</p>
      <p className="mt-2 text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}

