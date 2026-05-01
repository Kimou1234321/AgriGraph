import ChartPanel from "../ChartPanel";
import KpiCard from "../KpiCard";
import PillarRadar from "../PillarRadar";
import SustainabilityChart from "../SustainabilityChart";

export default function CountyDashboardPanel({
  selectedCounty,
  selectedYear,
  timeline,
  indicators,
  radarSingle,
  pillarKeys,
  pillars,
  glass = false,
}) {
  const latestScore = timeline.find((row) => row.year === selectedYear);
  const chartVariant = glass ? "glass" : "solid";
  return (
    <section className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <KpiCard
          label="Score"
          value={latestScore ? (latestScore.forecast ?? latestScore.historical ?? 0).toFixed(1) : "—"}
          tone="good"
          glass={glass}
        />
        <KpiCard
          label="Calving interval"
          value={indicators?.calving_interval?.toFixed?.(1) ?? "—"}
          tone="warn"
          glass={glass}
        />
        <KpiCard label="6-week calving rate" value={indicators?.six_wk_calving_rate?.toFixed?.(1) ?? "—"} glass={glass} />
        <KpiCard label="Culling rate" value={indicators?.cows_culled_pct?.toFixed?.(1) ?? "—"} tone="risk" glass={glass} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartPanel
          variant={chartVariant}
          title="Sustainability trajectory"
          subtitle="Historical 2021-2025, forecast 2026-2036 with 90% confidence band"
        >
          <SustainabilityChart data={timeline} />
        </ChartPanel>
        <ChartPanel variant={chartVariant} title="Pillar radar" subtitle={`Pillars for ${selectedCounty} in ${selectedYear}`}>
          <PillarRadar single={radarSingle} />
        </ChartPanel>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        {pillarKeys.map((key) => (
          <ChartPanel key={key} variant={chartVariant} title={key.replaceAll("_norm", "").replaceAll("_", " ")}>
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
