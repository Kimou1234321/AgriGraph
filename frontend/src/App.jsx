import { useEffect, useMemo, useState } from "react";
import ErrorState from "./components/ErrorState";
import LoadingState from "./components/LoadingState";
import { fetchCounties, fetchForecast, fetchHistorical } from "./api";
import BenchmarkTable from "./views/BenchmarkTable";
import CounterfactualView from "./views/CounterfactualView";
import CountyDashboard from "./views/CountyDashboard";
import MapView from "./views/MapView";
import MethodologyView from "./views/MethodologyView";

const TABS = [
  "National Map",
  "County Dashboard",
  "Simulation",
  "Benchmarks",
  "Methodology",
];

export default function App() {
  const [activeTab, setActiveTab] = useState(TABS[0]);
  const [counties, setCounties] = useState([]);
  const [historical, setHistorical] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [selectedCounty, setSelectedCounty] = useState("");
  const [selectedYear, setSelectedYear] = useState(2036);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dark, setDark] = useState(false);

  const loadBaseData = async () => {
    try {
      setLoading(true);
      setError("");
      const [countyPayload, historicalRows, forecastRows] = await Promise.all([
        fetchCounties(),
        fetchHistorical(),
        fetchForecast(),
      ]);
      const countyList = countyPayload.counties ?? [];
      setCounties(countyList);
      setHistorical(historicalRows);
      setForecast(forecastRows);
      setSelectedCounty((prev) => prev || countyList[0] || "");
    } catch (err) {
      setError(err.message || "Unable to load startup data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBaseData();
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const ActiveView = useMemo(() => {
    const sharedProps = {
      counties,
      historical,
      forecast,
      selectedCounty,
      setSelectedCounty,
      selectedYear,
      setSelectedYear,
    };
    if (activeTab === "National Map") return <MapView {...sharedProps} />;
    if (activeTab === "County Dashboard") return <CountyDashboard {...sharedProps} />;
    if (activeTab === "Simulation") return <CounterfactualView {...sharedProps} />;
    if (activeTab === "Benchmarks") return <BenchmarkTable {...sharedProps} setActiveTab={setActiveTab} />;
    return <MethodologyView />;
  }, [activeTab, counties, historical, forecast, selectedCounty, selectedYear]);

  return (
    <div className="min-h-screen bg-background text-slate-900 dark:bg-dark-bg dark:text-dark-text-primary">
      <header className="fixed left-0 right-0 top-0 z-50 h-16 border-b border-slate-200 bg-white px-6 dark:border-dark-border dark:bg-dark-surface">
        <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-wider text-emerald-900 dark:text-dark-accent">AGRIGRAPH AI</h1>
          </div>
          <nav className="hidden h-full items-end gap-6 md:flex">
            {TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                className={`pb-5 text-sm ${activeTab === tab ? "border-b-2 border-emerald-700 text-emerald-700 dark:border-dark-accent dark:text-dark-accent" : "text-slate-500 dark:text-dark-text-secondary"}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
              title={dark ? "Switch to light mode" : "Switch to dark mode"}
              onClick={() => setDark((v) => !v)}
              className="material-symbols-outlined rounded-md p-1 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-dark-text-secondary dark:hover:bg-dark-bg dark:hover:text-dark-accent"
            >
              {dark ? "light_mode" : "dark_mode"}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1280px] p-6 pt-24">
        {loading ? <LoadingState label="Loading AgriGraph data..." /> : null}
        {!loading && error ? <ErrorState message={error} onRetry={loadBaseData} /> : null}
        {!loading && !error ? ActiveView : null}
      </main>
    </div>
  );
}

