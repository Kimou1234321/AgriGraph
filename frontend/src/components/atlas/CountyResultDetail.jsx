import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartPanel from "../ChartPanel";
import PillarRadar from "../PillarRadar";
import SustainabilityChart from "../SustainabilityChart";
import { useIsDark } from "../../hooks/useIsDark";

export default function CountyResultDetail({ block, glass = false }) {
  const isDark = useIsDark();
  const chartVariant = glass ? "glass" : "solid";
  const gridStroke = isDark ? "#223047" : "#e2e8f0";
  const axisStroke = isDark ? "#64748b" : "#94a3b8";
  const tickFill = isDark ? "#9FB0C3" : "#475569";

  const lineData = (block?.baseline ?? []).map((row, index) => {
    const baseline = Number(row.score);
    const counterfactual = Number(block?.counterfactual?.[index]?.score ?? row.score);
    return {
      year: row.year,
      baseline,
      counterfactual,
      uplift: Number((counterfactual - baseline).toFixed(2)),
    };
  });
  const upliftData = (block?.uplift ?? []).map((row) => ({ year: row.year, delta: Number(row.delta) }));
  const shifts = block?.pillar_shifts ?? { P1: 0, P2: 0, P3: 0, P4: 0 };
  const radarBefore = { P1: 0, P2: 0, P3: 0, P4: 0 };
  const radarAfter = Object.fromEntries(Object.entries(shifts).map(([key, value]) => [key, Number(value)]));

  const pillarShell = glass
    ? "h-80 rounded-xl border border-white/40 bg-white/75 p-4 backdrop-blur-md dark:border-dark-border/60 dark:bg-dark-surface/80"
    : "h-80 rounded-xl border border-slate-200 bg-white p-4 dark:border-dark-border dark:bg-dark-surface";

  return (
    <section className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartPanel variant={chartVariant} title="Baseline vs counterfactual" subtitle="2026-2036 score trajectory">
          <SustainabilityChart data={lineData} mode="counterfactual" />
        </ChartPanel>
        <ChartPanel variant={chartVariant} title="Year-by-year uplift" subtitle="Counterfactual - baseline">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={upliftData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="year" stroke={axisStroke} tick={{ fill: tickFill }} />
              <YAxis stroke={axisStroke} tick={{ fill: tickFill }} />
              <Tooltip
                formatter={(value) => `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(1)}`}
                contentStyle={
                  isDark
                    ? { backgroundColor: "#111B2E", borderColor: "#223047", color: "#E5EEF7" }
                    : undefined
                }
              />
              <Bar dataKey="delta" fill="#2d6a4f" />
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
      </div>
      <div className={pillarShell}>
        <h3 className="mb-2 text-sm font-semibold text-slate-900 dark:text-dark-text-primary">Pillar shift geometry</h3>
        <PillarRadar labels={Object.keys(shifts)} before={radarBefore} after={radarAfter} />
      </div>
    </section>
  );
}
