import { toScoreTier } from "../../api";
import KpiCard from "../KpiCard";

export default function NationalKpiPanel({
  average,
  highest,
  lowest,
  selectedCounty,
  selectedScore,
  hint = "",
  stack = true,
}) {
  return (
    <div className={stack ? "space-y-3" : "contents"}>
      <KpiCard label="National average" value={average !== null ? average.toFixed(1) : "—"} />
      <KpiCard
        label="Highest county"
        value={highest ? `${highest.county} (${highest.score.toFixed(1)})` : "—"}
        tone="good"
      />
      <KpiCard
        label="Lowest county"
        value={lowest ? `${lowest.county} (${lowest.score.toFixed(1)})` : "—"}
        tone="risk"
      />
      <KpiCard
        label="Selected county"
        value={selectedCounty || "None"}
        sublabel={selectedCounty ? `Tier: ${toScoreTier(selectedScore ?? 0)}` : hint || "Select county on map"}
      />
    </div>
  );
}
