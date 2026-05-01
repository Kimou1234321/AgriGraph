import { useEffect, useMemo, useState } from "react";
import { countyTrendFromScores, fetchPillars, getCountyScoreForYear, toScoreTier } from "../api";

function toCsv(rows) {
  const headers = ["county", "score_2025", "score_2036", "trend", "tier"];
  const lines = rows.map((row) =>
    [row.county, row.score_2025.toFixed(1), row.score_2036.toFixed(1), row.trend, row.tier].join(",")
  );
  return [headers.join(","), ...lines].join("\n");
}

export default function BenchmarkTable({
  counties,
  historical,
  forecast,
  setSelectedCounty,
  setActiveTab,
}) {
  const [query, setQuery] = useState("");
  const [pillarWeakness, setPillarWeakness] = useState({});
  const [sortBy, setSortBy] = useState("score_2036");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);
  const pageSize = 10;

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

  const rows = useMemo(() => {
    const base = counties
      .map((county) => {
        const score2025 = getCountyScoreForYear(county, 2025, historical, forecast);
        const score2036 = getCountyScoreForYear(county, 2036, historical, forecast);
        return {
          county,
          score_2025: Number(score2025 ?? 0),
          score_2036: Number(score2036 ?? 0),
          trend: countyTrendFromScores(score2025, score2036),
          tier: toScoreTier(score2036 ?? 0),
          top_weakness: pillarWeakness[county] ?? "Loading...",
        };
      })
      .filter((row) => row.county.toLowerCase().includes(query.toLowerCase()));
    const sorted = [...base].sort((a, b) => {
      const av = a[sortBy];
      const bv = b[sortBy];
      if (typeof av === "number" && typeof bv === "number") return sortDir === "asc" ? av - bv : bv - av;
      return sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return sorted;
  }, [counties, historical, forecast, query, pillarWeakness, sortBy, sortDir]);

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
    const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "agrigraph_benchmarks.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Regional Benchmarks</h2>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search county..."
            className="rounded border border-slate-300 px-3 py-2 text-sm"
          />
          <button type="button" onClick={exportCsv} className="rounded bg-slate-100 px-3 py-2 text-sm font-medium">
            Export CSV
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-600">
              <th className="py-2 cursor-pointer" onClick={() => toggleSort("county")}>County ↕</th>
              <th className="py-2 cursor-pointer" onClick={() => toggleSort("score_2025")}>2025 Score ↕</th>
              <th className="py-2 cursor-pointer" onClick={() => toggleSort("score_2036")}>2036 Forecast ↕</th>
              <th className="py-2 cursor-pointer" onClick={() => toggleSort("trend")}>Trend ↕</th>
              <th className="py-2">Top Weakness</th>
              <th className="py-2 cursor-pointer" onClick={() => toggleSort("tier")}>Tier ↕</th>
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((row) => (
              <tr key={row.county} className="border-b border-slate-100">
                <td className="py-2">
                  <button
                    type="button"
                    className="font-medium text-[#2D6A4F]"
                    onClick={() => {
                      setSelectedCounty(row.county);
                      setActiveTab("County Dashboard");
                    }}
                  >
                    {row.county}
                  </button>
                </td>
                <td className="py-2">{row.score_2025.toFixed(1)}</td>
                <td className="py-2">{row.score_2036.toFixed(1)}</td>
                <td className="py-2">{row.trend}</td>
                <td className="py-2">{row.top_weakness}</td>
                <td className="py-2">
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${
                    row.tier === "Top" ? "bg-emerald-100 text-emerald-800" : row.tier === "Mid" ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800"
                  }`}>
                    {row.tier}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-xs text-slate-600">
        <span>
          Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, rows.length)} of {rows.length} counties
        </span>
        <div className="flex gap-2">
          <button type="button" className="rounded border px-2 py-1 disabled:opacity-40" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ◀
          </button>
          <button type="button" className="rounded border px-2 py-1 disabled:opacity-40" disabled={page >= maxPage} onClick={() => setPage((p) => p + 1)}>
            ▶
          </button>
        </div>
      </div>
    </section>
  );
}

