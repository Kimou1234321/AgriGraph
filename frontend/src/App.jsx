import { useCallback, useEffect, useMemo, useState } from "react";
import ErrorState from "./components/ErrorState";
import LoadingState from "./components/LoadingState";
import AccountPanel from "./components/AccountPanel";
import BottomToast from "./components/BottomToast";
import SaveSimulationModal from "./components/SaveSimulationModal";
import AuthPage from "./components/auth/AuthPage";
import {
  fetchCounties,
  fetchForecast,
  fetchHistorical,
  fetchSavedSimulation,
  runCounterfactualGlobal,
  saveSimulation,
} from "./api";
import { useAuth } from "./auth/AuthContext";
import { buildSimulationSnapshot } from "./utils/simulationSnapshot";
import BenchmarksView from "./views/BenchmarksView";
import AtlasView from "./views/AtlasView";
import MethodologyView from "./views/MethodologyView";

const TABS = ["Atlas", "Benchmarks"];

export default function App() {
  const { user, loadingAuth, isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState(TABS[0]);
  const [appView, setAppView] = useState("main");
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
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [accountPanelOpen, setAccountPanelOpen] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [atlasViewMode, setAtlasViewMode] = useState("initial");
  const [toast, setToast] = useState(null);
  const [lastSavedSnapshot, setLastSavedSnapshot] = useState(null);

  const showToast = useCallback((message, variant) => {
    setToast({ message, variant });
  }, []);

  const dismissToast = useCallback(() => {
    setToast(null);
  }, []);

  const loadBaseData = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadBaseData();
  }, [isAuthenticated, loadBaseData]);

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
      setAtlasViewMode("simulation");
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
    setAtlasViewMode("initial");
    setLastSavedSnapshot(null);
  }, []);

  const handleSaveSimulation = useCallback(
    async ({ name, description }) => {
      if (!simulationResults) return;
      try {
        setSaveLoading(true);
        setSaveError("");
        await saveSimulation({
          name,
          description,
          scenarios,
          result: simulationResults,
          horizon: simulationResults.horizon?.length ?? 11,
        });
        const snapshot = buildSimulationSnapshot(scenarios, simulationResults);
        setLastSavedSnapshot(snapshot);
        setSaveModalOpen(false);
        showToast("Simulation saved successfully.", "success");
      } catch (err) {
        setSaveError(err.message || "Unable to save simulation.");
      } finally {
        setSaveLoading(false);
      }
    },
    [scenarios, simulationResults, showToast]
  );

  const handleOpenSaveModal = useCallback(() => {
    if (!simulationResults) return;
    const current = buildSimulationSnapshot(scenarios, simulationResults);
    if (lastSavedSnapshot && current === lastSavedSnapshot) {
      showToast("This simulation is already saved. Change scenarios or re-run to save again.", "error");
      return;
    }
    setSaveError("");
    setSaveModalOpen(true);
  }, [scenarios, simulationResults, lastSavedSnapshot, showToast]);

  const handleLoadSimulation = useCallback(async (simulationId) => {
    try {
      const detail = await fetchSavedSimulation(simulationId);
      const loadedScenarios = detail.scenarios ?? {};
      const loadedResult = detail.result ?? null;
      setScenarios(loadedScenarios);
      setSimulationResults(loadedResult);
      setLastSavedSnapshot(buildSimulationSnapshot(loadedScenarios, loadedResult));
      setSimulationError("");
      setActiveTab("Atlas");
      setAppView("main");
      setAtlasViewMode("simulation");
      setAtlasCountyConfirmed(false);
      setSelectedCounty("");
      setAccountPanelOpen(false);
    } catch (err) {
      setSimulationError(err.message || "Unable to load saved simulation.");
    }
  }, []);

  const ActiveView = useMemo(() => {
    if (appView === "methodology") {
      return <MethodologyView onBack={() => setAppView("main")} />;
    }
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
          viewMode={atlasViewMode}
          setViewMode={setAtlasViewMode}
        />
      );
    return (
      <BenchmarksView
        {...sharedProps}
        setActiveTab={setActiveTab}
        simulationResults={simulationResults}
        setAtlasCountyConfirmed={setAtlasCountyConfirmed}
        viewMode={atlasViewMode}
        setViewMode={setAtlasViewMode}
      />
    );
  }, [
    appView,
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
    atlasViewMode,
    runGlobalSimulation,
    resetSimulation,
  ]);

  const mainClass =
    activeTab === "Atlas" && appView === "main"
      ? "min-h-screen pt-16"
      : "mx-auto max-w-[1280px] p-6 pt-24";

  if (loadingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background dark:bg-dark-bg">
        <LoadingState label="Checking session…" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  const canSave = Boolean(simulationResults);

  return (
    <div className="min-h-screen bg-background text-slate-900 dark:bg-dark-bg dark:text-dark-text-primary">
      <header className="fixed left-0 right-0 top-0 z-50 h-16 border-b border-slate-200 bg-white px-6 dark:border-dark-border dark:bg-dark-surface">
        <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-wider text-emerald-900 dark:text-dark-accent">AGRIGRAPH AI</h1>
          </div>
          {appView === "main" ? (
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
          ) : (
            <p className="text-sm text-slate-500 dark:text-dark-text-secondary">Methodology</p>
          )}
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Save simulation"
              title={canSave ? "Save simulation" : "Run a simulation first to save"}
              disabled={!canSave}
              onClick={handleOpenSaveModal}
              className="material-symbols-outlined rounded-md p-1 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-35 dark:text-dark-text-secondary dark:hover:bg-dark-bg dark:hover:text-dark-accent"
            >
              save
            </button>
            <button
              type="button"
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
              title={dark ? "Switch to light mode" : "Switch to dark mode"}
              onClick={() => setDark((v) => !v)}
              className="material-symbols-outlined rounded-md p-1 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-dark-text-secondary dark:hover:bg-dark-bg dark:hover:text-dark-accent"
            >
              {dark ? "light_mode" : "dark_mode"}
            </button>
            <button
              type="button"
              aria-label="Account"
              title={user?.email ?? "Account"}
              onClick={() => setAccountPanelOpen(true)}
              className="material-symbols-outlined rounded-md p-1 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-dark-text-secondary dark:hover:bg-dark-bg dark:hover:text-dark-accent"
            >
              account_circle
            </button>
          </div>
        </div>
      </header>
      <main className={mainClass}>
        {loading ? <LoadingState label="Loading AgriGraph data..." /> : null}
        {!loading && error ? <ErrorState message={error} onRetry={loadBaseData} /> : null}
        {!loading && !error ? ActiveView : null}
      </main>
      <SaveSimulationModal
        open={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        onSave={handleSaveSimulation}
        saving={saveLoading}
        error={saveError}
      />
      <AccountPanel
        open={accountPanelOpen}
        onClose={() => setAccountPanelOpen(false)}
        onLoadSimulation={handleLoadSimulation}
        onOpenMethodology={() => {
          setAccountPanelOpen(false);
          setAppView("methodology");
        }}
      />
      <BottomToast message={toast?.message} variant={toast?.variant} onDismiss={dismissToast} />
    </div>
  );
}
