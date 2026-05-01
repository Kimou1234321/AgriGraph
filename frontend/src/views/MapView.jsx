import { getCountyScoreForYear, toScoreTier } from "../api";
import IrelandMap from "../components/IrelandMap";
import KpiCard from "../components/KpiCard";

const YEARS = Array.from({ length: 16 }, (_, index) => 2021 + index);

export default function MapView({
  counties,
  historical,
  forecast,
  selectedCounty,
  setSelectedCounty,
  selectedYear,
  setSelectedYear,
}) {
  const scoreByCounty = Object.fromEntries(
    counties.map((county) => [county, getCountyScoreForYear(county, selectedYear, historical, forecast)])
  );
  const scores = Object.values(scoreByCounty).filter((score) => Number.isFinite(score));
  const average = scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null;
  const ranked = counties
    .map((county) => ({ county, score: scoreByCounty[county] }))
    .filter((item) => Number.isFinite(item.score))
    .sort((a, b) => b.score - a.score);
  const highest = ranked[0];
  const lowest = ranked[ranked.length - 1];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">National Sustainability Map</h2>
          <p className="text-sm text-slate-600">Overview of county scores for {selectedYear}</p>
        </div>
        <div className="w-full max-w-sm space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-600">
            <span>2021</span>
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700">{selectedYear}</span>
            <span>2036</span>
          </div>
          <input type="range" min={2021} max={2036} step={1} value={selectedYear} onChange={(event) => setSelectedYear(Number(event.target.value))} className="w-full" />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <IrelandMap
            counties={counties}
            selectedCounty={selectedCounty}
            scoreByCounty={scoreByCounty}
            onSelectCounty={setSelectedCounty}
          />
        </div>
        <div className="space-y-3 lg:col-span-4">
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
            sublabel={selectedCounty ? `Tier: ${toScoreTier(scoreByCounty[selectedCounty] ?? 0)}` : "Select county on map"}
          />
        </div>
      </div>
    </section>
  );
}

