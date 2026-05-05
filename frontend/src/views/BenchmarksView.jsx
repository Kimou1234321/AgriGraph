import { useEffect, useMemo, useState } from "react";
import {
  countyTrendFromScores,
  fetchPillars,
  getCountyScoreForYear,
  getCountyScoreForYearWithSimulation,
  toScoreTier,
} from "../api";
import MiniMapNodes from "../components/benchmarks/MiniMapNodes";
import NationalKpiPanel from "../components/atlas/NationalKpiPanel";
import SimToggle from "../components/atlas/SimToggle";

function toCsv(rows, viewMode, selectedYear) {
  if (viewMode === "simulation") {
    const headers = ["county", "score_2025", `score_${selectedYear}`, "uplift_final", "tier"];
    const lines = rows.map((row) =>
      [
        row.county,
        row.score_2025.toFixed(1),
        row.score_selected.toFixed(1),
        row.uplift_final.toFixed(1),
        row.tier,
      ].join(",")
    );
    return [headers.join(","), ...lines].join("\n");
  }
  const headers = ["county", "score_2025", "score_2036", "trend", "tier"];
  const lines = rows.map((row) =>
    [row.county, row.score_2025.toFixed(1), row.score_2036.toFixed(1), row.trend, row.tier].join(",")
  );
  return [headers.join(","), ...lines].join("\n");
}

export default function BenchmarksView({
  counties,
  historical,
  forecast,
  selectedCounty,
  setSelectedCounty,
  selectedYear,
  setSelectedYear,
  setActiveTab,
  simulationResults,
  setAtlasCountyConfirmed,
}) {
  const [query, setQuery] = useState("");
  const [pillarWeakness, setPillarWeakness] = useState({});
  const [sortBy, setSortBy] = useState("score_2036");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState("initial");
  const pageSize = 10;

  useEffect(() => {
    if (!simulationResults) setViewMode("initial");
  }, [simulationResults]);

  useEffect(() => {
    setSortBy(viewMode === "simulation" ? "score_selected" : "score_2036");
    setPage(1);
  }, [viewMode]);

  useEffect(() => {
    let cancelled = false;
    const loadWeaknesses = async () => {
      const pairs = await Promise.all(
        counties.map(async (county) => {
          try {
            const rows = await fetchPillars(county);
            const y2036 = rows.find((row) => Number(row.year) === 2036) ?? rows[rows.length - 1];
            if (!y2036) return [county, "N/A"];
            const pillarEntries = Object.entries(y2036).filter(([key]) => key !== "year" && !key.endsWith("_norm"));
            const weakest = pillarEntries.sort((a, b) => Number(a[1]) - Number(b[1]))[0]?.[0] ?? "N/A";
            return [county, weakest.replaceAll("_", " ")];
          } catch {
            return [county, "N/A"];
          }
        })
      );
      if (!cancelled) setPillarWeakness(Object.fromEntries(pairs));
    };
    if (counties.length > 0) loadWeaknesses();
    return () => {
      cancelled = true;
    };
  }, [counties]);

  const scoreByCountyForMap = useMemo(() => {
    return Object.fromEntries(
      counties.map((county) => [
        county,
        getCountyScoreForYearWithSimulation(county, selectedYear, historical, forecast, simulationResults, viewMode),
      ])
    );
  }, [counties, historical, forecast, selectedYear, simulationResults, viewMode]);

  const rankedStats = useMemo(() => {
    const scores = counties
      .map((c) => scoreByCountyForMap[c])
      .filter((s) => Number.isFinite(s));
    const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
    const ranked = counties
      .map((county) => ({ county, score: scoreByCountyForMap[county] }))
      .filter((item) => Number.isFinite(item.score))
      .sort((a, b) => b.score - a.score);
    return { average, highest: ranked[0], lowest: ranked[ranked.length - 1] };
  }, [counties, scoreByCountyForMap]);

  const rows = useMemo(() => {
    const base = counties
      .map((county) => {
        const score2025 = getCountyScoreForYear(county, 2025, historical, forecast);
        const score2036 = getCountyScoreForYear(county, 2036, historical, forecast);
        const scoreSelected = getCountyScoreForYearWithSimulation(
          county,
          selectedYear,
          historical,
          forecast,
          simulationResults,
          viewMode
        );
        const block = simulationResults?.by_county?.[county];
        const upliftFinal = block?.uplift_final_year ?? 0;
        const tierScore = viewMode === "simulation" ? scoreSelected : score2036;
        return {
          county,
          score_2025: Number(score2025 ?? 0),
          score_2036: Number(score2036 ?? 0),
          score_selected: Number(scoreSelected ?? 0),
          uplift_final: Number(upliftFinal),
          trend: countyTrendFromScores(score2025, score2036),
          tier: toScoreTier(Number(tierScore ?? 0)),
          top_weakness: pillarWeakness[county] ?? "Loading...",
        };
      })
      .filter((row) => row.county.toLowerCase().includes(query.toLowerCase()));

    const simSortKey = viewMode === "simulation" ? (sortBy === "score_2036" ? "score_selected" : sortBy) : sortBy;
    const sorted = [...base].sort((a, b) => {
      const av = a[simSortKey];
      const bv = b[simSortKey];
      if (typeof av === "number" && typeof bv === "number") return sortDir === "asc" ? av - bv : bv - av;
      return sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return sorted;
  }, [counties, historical, forecast, query, pillarWeakness, sortBy, sortDir, selectedYear, simulationResults, viewMode]);

  const maxPage = Math.max(1, Math.ceil(rows.length / pageSize));
  const pagedRows = rows.slice((page - 1) * pageSize, page * pageSize);

  const toggleSort = (field) => {
    setPage(1);
    if (sortBy === field) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(field);
    setSortDir("desc");
  };

  const exportCsv = () => {
    const blob = new Blob([toCsv(rows, viewMode, selectedYear)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "agrigraph_benchmarks.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-dark-border dark:bg-dark-surface">
        <h2 className="mb-4 text-xl font-semibold text-slate-900 dark:text-dark-text-primary">Benchmarks</h2>

        <div className="mb-5">
          <MiniMapNodes
            counties={counties}
            selectedCounty={selectedCounty}
            scoreByCounty={scoreByCountyForMap}
            onSelectCounty={(county) => {
              setSelectedCounty(county);
              setAtlasCountyConfirmed(true);
              setActiveTab("Atlas");
            }}
          />
        </div>

        <div className="mb-6 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <NationalKpiPanel
            stack={false}
            average={rankedStats.average}
            highest={rankedStats.highest}
            lowest={rankedStats.lowest}
            selectedCounty={selectedCounty || "None"}
            selectedScore={
              selectedCounty ? scoreByCountyForMap[selectedCounty] ?? null : null
            }
            hint={viewMode === "simulation" ? "Simulation trajectory for forecast years" : "Baseline & forecast scores"}
          />
        </div>

        <div className="rounded-lg border border-slate-100 bg-slate-50/80 p-4 dark:border-dark-border dark:bg-dark-bg/40">
          {simulationResults ? (
            <div className="mb-4 flex justify-center">
              <SimToggle value={viewMode} onChange={setViewMode} />
            </div>
          ) : null}

          <div
            className="mx-auto w-full max-w-xl space-y-1.5"
            aria-label="Year selector for map and regional table"
          >
            <div className="flex items-center justify-between text-xs text-slate-600 dark:text-dark-text-secondary">
              <span>2021</span>
              <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 font-semibold text-emerald-700 dark:bg-emerald-950/50 dark:text-dark-accent">
                {selectedYear}
              </span>
              <span>2036</span>
            </div>
            <input
              type="range"
              min={2021}
              max={2036}
              step={1}
              value={selectedYear}
              onChange={(event) => setSelectedYear(Number(event.target.value))}
              className="h-2 w-full cursor-pointer accent-emerald-700 dark:accent-dark-accent"
            />
            <p className="text-center text-xs text-slate-500 dark:text-dark-text-secondary">
              Use Initial / Simulation (when available) and the year control to refresh the map and KPIs above and the regional
              table below.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-dark-border dark:bg-dark-surface">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-section-heading text-slate-900 dark:text-dark-text-primary">Regional table</h3>
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search county..."
              className="rounded border border-slate-300 px-3 py-2 text-sm dark:border-dark-border dark:bg-dark-bg dark:text-dark-text-primary"
            />
            <button
              type="button"
              onClick={exportCsv}
              className="rounded bg-slate-100 px-3 py-2 text-sm font-medium dark:bg-dark-bg dark:text-dark-text-primary"
            >
              Export CSV
            </button>
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-600 dark:border-dark-border dark:text-dark-text-secondary">
                <th className="cursor-pointer py-2" onClick={() => toggleSort("county")}>
                  County ↕
                </th>
                <th className="cursor-pointer py-2" onClick={() => toggleSort("score_2025")}>
                  2025 Score ↕
                </th>
                {viewMode === "simulation" ? (
                  <th className="cursor-pointer py-2" onClick={() => toggleSort("score_selected")}>
                    {selectedYear} (sim) ↕
                  </th>
                ) : (
                  <th className="cursor-pointer py-2" onClick={() => toggleSort("score_2036")}>
                    2036 Forecast ↕
                  </th>
                )}
                {viewMode === "simulation" ? (
                  <th className="cursor-pointer py-2" onClick={() => toggleSort("uplift_final")}>
                    Uplift (final) ↕
                  </th>
                ) : (
                  <th className="cursor-pointer py-2" onClick={() => toggleSort("trend")}>
                    Trend ↕
                  </th>
                )}
                <th className="py-2">Top Weakness</th>
                <th className="cursor-pointer py-2" onClick={() => toggleSort("tier")}>
                  Tier ↕
                </th>
              </tr>
            </thead>
            <tbody>
              {pagedRows.map((row) => (
                <tr key={row.county} className="border-b border-slate-100 dark:border-dark-border">
                  <td className="py-2">
                    <button
                      type="button"
                      className="font-medium text-emerald-700 dark:text-dark-accent"
                      onClick={() => {
                        setSelectedCounty(row.county);
                        setAtlasCountyConfirmed(true);
                        setActiveTab("Atlas");
                      }}
                    >
                      {row.county}
                    </button>
                  </td>
                  <td className="py-2">{row.score_2025.toFixed(1)}</td>
                  <td className="py-2">
                    {viewMode === "simulation" ? row.score_selected.toFixed(1) : row.score_2036.toFixed(1)}
                  </td>
                  <td className="py-2">
                    {viewMode === "simulation"
                      ? `${row.uplift_final > 0 ? "+" : ""}${row.uplift_final.toFixed(1)}`
                      : row.trend}
                  </td>
                  <td className="py-2">{row.top_weakness}</td>
                  <td className="py-2">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold ${
                        row.tier === "Top"
                          ? "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300"
                          : row.tier === "Mid"
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
                            : "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300"
                      }`}
                    >
                      {row.tier}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-slate-600 dark:text-dark-text-secondary">
          <span>
            Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, rows.length)} of {rows.length}{" "}
            counties
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded border px-2 py-1 disabled:opacity-40 dark:border-dark-border"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ◀
            </button>
            <button
              type="button"
              className="rounded border px-2 py-1 disabled:opacity-40 dark:border-dark-border"
              disabled={page >= maxPage}
              onClick={() => setPage((p) => p + 1)}
            >
              ▶
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
