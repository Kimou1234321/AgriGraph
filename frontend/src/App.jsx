import { useCallback, useEffect, useMemo, useState } from "react";
import ErrorState from "./components/ErrorState";
import LoadingState from "./components/LoadingState";
import { fetchCounties, fetchForecast, fetchHistorical, runCounterfactualGlobal } from "./api";
import BenchmarksView from "./views/BenchmarksView";
import AtlasView from "./views/AtlasView";
import MethodologyView from "./views/MethodologyView";

const TABS = ["Atlas", "Benchmarks", "Methodology"];

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
  const [scenarios, setScenarios] = useState({});
  const [simulationResults, setSimulationResults] = useState(null);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError, setSimulationError] = useState("");
  const [atlasCountyConfirmed, setAtlasCountyConfirmed] = useState(false);

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

  const runGlobalSimulation = useCallback(async () => {
    if (Object.keys(scenarios).length === 0) return;
    try {
      setSimulationLoading(true);
      setSimulationError("");
      const response = await runCounterfactualGlobal({ scenarios, horizon: 11 });
      setSimulationResults(response);
    } catch (err) {
      setSimulationError(err.message || "Global simulation failed.");
    } finally {
      setSimulationLoading(false);
    }
  }, [scenarios]);

  const resetSimulation = useCallback(() => {
    setScenarios({});
    setSimulationResults(null);
    setSimulationError("");
  }, []);

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
    if (activeTab === "Atlas")
      return (
        <AtlasView
          {...sharedProps}
          scenarios={scenarios}
          setScenarios={setScenarios}
          simulationResults={simulationResults}
          runGlobalSimulation={runGlobalSimulation}
          resetSimulation={resetSimulation}
          simulationLoading={simulationLoading}
          simulationError={simulationError}
          atlasCountyConfirmed={atlasCountyConfirmed}
          setAtlasCountyConfirmed={setAtlasCountyConfirmed}
        />
      );
    if (activeTab === "Benchmarks")
      return (
        <BenchmarksView
          {...sharedProps}
          setActiveTab={setActiveTab}
          simulationResults={simulationResults}
          setAtlasCountyConfirmed={setAtlasCountyConfirmed}
        />
      );
    return <MethodologyView />;
  }, [
    activeTab,
    counties,
    historical,
    forecast,
    selectedCounty,
    selectedYear,
    scenarios,
    simulationResults,
    simulationLoading,
    simulationError,
    atlasCountyConfirmed,
    runGlobalSimulation,
    resetSimulation,
  ]);

  const mainClass =
    activeTab === "Atlas"
      ? "min-h-screen pt-16"
      : "mx-auto max-w-[1280px] p-6 pt-24";

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
      <main className={mainClass}>
        {loading ? <LoadingState label="Loading AgriGraph data..." /> : null}
        {!loading && error ? <ErrorState message={error} onRetry={loadBaseData} /> : null}
        {!loading && !error ? ActiveView : null}
      </main>
    </div>
  );
}
