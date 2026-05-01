import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  extractPillarNormKeys,
  fetchIndicators,
  fetchPillars,
  fetchPillarsPreview,
  mergeCountyTimeline,
} from "../api";
import IrelandRealMap from "../components/atlas/IrelandRealMap";
import CountyDetailPanel from "../components/atlas/CountyDetailPanel";
import SimulationSidebar from "../components/atlas/SimulationSidebar";
import SimToggle from "../components/atlas/SimToggle";
import { emptyInterventions, INTERVENTION_PRESETS } from "../constants/interventionSliders";

const CONSTANTS = {
  PREVIEW_DEBOUNCE_MS: 150,
};

export default function AtlasView({
  counties,
  historical,
  forecast,
  selectedCounty,
  setSelectedCounty,
  selectedYear,
  scenarios,
  setScenarios,
  simulationResults,
  runGlobalSimulation,
  resetSimulation,
  simulationLoading,
  simulationError,
  atlasCountyConfirmed,
  setAtlasCountyConfirmed,
}) {
  const [viewMode, setViewMode] = useState("initial");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [draft, setDraft] = useState(emptyInterventions());
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [pillars, setPillars] = useState([]);
  const [indicators, setIndicators] = useState(null);
  const previewDebounceRef = useRef(null);

  const activeCounty = atlasCountyConfirmed ? selectedCounty : "";

  useEffect(() => {
    if (!simulationResults) setViewMode("initial");
  }, [simulationResults]);

  useEffect(() => {
    return () => {
      if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
    };
  }, []);

  const runPreviewNow = useCallback(async (county, interventionDraft) => {
    if (!county) return;
    try {
      setLoadingPreview(true);
      setPreviewError("");
      const data = await fetchPillarsPreview({ county, interventions: interventionDraft });
      setPreview(data);
    } catch (err) {
      setPreviewError(err.message || "Unable to load pillar preview.");
    } finally {
      setLoadingPreview(false);
    }
  }, []);

  const schedulePreview = useCallback(
    (county, interventionDraft) => {
      if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
      previewDebounceRef.current = setTimeout(() => {
        runPreviewNow(county, interventionDraft);
      }, CONSTANTS.PREVIEW_DEBOUNCE_MS);
    },
    [runPreviewNow]
  );

  const timeline = useMemo(() => {
    if (!activeCounty) return [];
    const merged = mergeCountyTimeline(activeCounty, historical, forecast);
    return merged.map((row) => ({
      year: row.year,
      historical: row.score,
      forecast: row.predicted_score,
      lower_5pct: row.lower_5pct,
      upper_95pct: row.upper_95pct,
    }));
  }, [activeCounty, historical, forecast]);

  const pillarKeys = extractPillarNormKeys(pillars);
  const selectedPillarRow = pillars.find((row) => Number(row.year) === selectedYear);
  const radarSingle = pillarKeys.map((key) => ({
    pillar: key.replaceAll("_norm", "").replaceAll("_", " "),
    value: Number(selectedPillarRow?.[key] ?? 0),
  }));

  useEffect(() => {
    let cancelled = false;
    const loadCountyData = async () => {
      if (!activeCounty) return;
      try {
        const [pillarRows, indicatorData] = await Promise.all([
          fetchPillars(activeCounty),
          fetchIndicators(activeCounty, selectedYear),
        ]);
        if (!cancelled) {
          setPillars(pillarRows);
          setIndicators(indicatorData);
        }
      } catch {
        if (!cancelled) {
          setPillars([]);
          setIndicators(null);
        }
      }
    };
    loadCountyData();
    return () => {
      cancelled = true;
    };
  }, [activeCounty, selectedYear]);

  const onSelectCounty = (county) => {
    if (atlasCountyConfirmed && selectedCounty === county) {
      setAtlasCountyConfirmed(false);
      setSelectedCounty("");
      return;
    }
    setAtlasCountyConfirmed(true);
    setSelectedCounty(county);
    const nextDraft = scenarios[county] ?? emptyInterventions();
    setDraft(nextDraft);
    runPreviewNow(county, nextDraft);
    if (scenarios[county] !== undefined) setSidebarOpen(true);
  };

  const onScenarioChipSelect = (county) => {
    setAtlasCountyConfirmed(true);
    setSelectedCounty(county);
    const next = scenarios[county] ?? emptyInterventions();
    setDraft(next);
    runPreviewNow(county, next);
  };

  const onSliderChange = (key, value) => {
    if (!activeCounty) return;
    const next = { ...draft, [key]: value };
    setDraft(next);
    schedulePreview(activeCounty, next);
  };

  const onApplyPreset = (name) => {
    if (!activeCounty) return;
    const next = { ...draft, ...(INTERVENTION_PRESETS[name] ?? {}) };
    setDraft(next);
    schedulePreview(activeCounty, next);
  };

  const onClear = () => {
    if (!activeCounty) return;
    const next = emptyInterventions();
    setDraft(next);
    schedulePreview(activeCounty, next);
  };

  const onSaveScenario = () => {
    if (!activeCounty) return;
    setScenarios((prev) => ({ ...prev, [activeCounty]: { ...draft } }));
  };

  const onRemoveScenario = (county) => {
    setScenarios((prev) => {
      const next = { ...prev };
      delete next[county];
      return next;
    });
    if (activeCounty === county) {
      const cleared = emptyInterventions();
      setDraft(cleared);
      runPreviewNow(county, cleared);
    }
  };

  const handleResetAll = () => {
    resetSimulation();
    setDraft(emptyInterventions());
    setPreview(null);
    setPreviewError("");
    setSidebarOpen(false);
  };

  const canRun = Object.keys(scenarios).length > 0 && !simulationLoading;

  const simulationBlock = simulationResults?.by_county?.[activeCounty];

  return (
    <div className="relative min-h-[calc(100vh-5rem)]">
      <div className="pointer-events-none fixed inset-0 top-16 z-0">
        <div className="pointer-events-auto h-full w-full">
          <IrelandRealMap
            counties={counties}
            selectedCounty={activeCounty}
            onSelectCounty={onSelectCounty}
            variant="atlas"
            className="h-full w-full [&_svg]:h-full [&_svg]:min-h-[420px] [&_svg]:w-full"
          />
        </div>
      </div>

      <div className="pointer-events-none relative z-10 min-h-[calc(100vh-5rem)]">
        <div className="pointer-events-auto fixed right-4 top-24 z-20 flex flex-col items-end gap-2 md:right-8">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="flex h-12 w-12 items-center justify-center rounded-full border border-slate-200 bg-white text-emerald-800 shadow-lg dark:border-dark-border dark:bg-dark-surface dark:text-dark-accent"
            aria-label="Open simulation sidebar"
          >
            <span className="material-symbols-outlined">tune</span>
          </button>
          {simulationError ? (
            <p className="max-w-xs rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
              {simulationError}
            </p>
          ) : null}
        </div>

        {simulationResults ? (
          <div className="pointer-events-auto fixed bottom-6 left-1/2 z-20 -translate-x-1/2">
            <SimToggle value={viewMode} onChange={setViewMode} />
          </div>
        ) : null}

        <CountyDetailPanel
          county={activeCounty}
          viewMode={viewMode}
          selectedYear={selectedYear}
          simulationBlock={simulationBlock}
          onOpenSimulation={() => setSidebarOpen(true)}
          timeline={timeline}
          indicators={indicators}
          radarSingle={radarSingle}
          pillarKeys={pillarKeys}
          pillars={pillars}
        />
      </div>

      <SimulationSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeCounty={activeCounty}
        draft={draft}
        scenarios={scenarios}
        setScenarios={setScenarios}
        preview={preview}
        loadingPreview={loadingPreview}
        previewError={previewError}
        onSliderChange={onSliderChange}
        onApplyPreset={onApplyPreset}
        onClear={onClear}
        onSaveScenario={onSaveScenario}
        onRemoveScenario={onRemoveScenario}
        runGlobalSimulation={runGlobalSimulation}
        resetAll={handleResetAll}
        loadingRun={simulationLoading}
        canRun={canRun}
        onScenarioChipSelect={onScenarioChipSelect}
      />
    </div>
  );
}
