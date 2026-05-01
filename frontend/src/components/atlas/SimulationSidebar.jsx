import ScenarioChips from "./ScenarioChips";
import SimulationSlidersPanel from "./SimulationSlidersPanel";
import { emptyInterventions, INTERVENTION_PRESETS, INTERVENTION_SLIDERS } from "../../constants/interventionSliders";

/** Slide-in drawer: global run/reset, scenario chips, presets, sliders, pillar preview. */
export default function SimulationSidebar({
  open,
  onClose,
  activeCounty,
  draft,
  scenarios,
  setScenarios,
  preview,
  loadingPreview,
  previewError,
  onSliderChange,
  onApplyPreset,
  onClear,
  onSaveScenario,
  onRemoveScenario,
  runGlobalSimulation,
  resetAll,
  loadingRun,
  canRun,
  onScenarioChipSelect,
}) {
  const dirty = activeCounty
    ? JSON.stringify(draft) !== JSON.stringify(scenarios[activeCounty] ?? emptyInterventions())
    : false;
  const hasAnyDraftChange = Object.values(draft).some((value) => Math.abs(value) > 0);
  const canSave = Boolean(activeCounty) && hasAnyDraftChange && dirty;

  return (
    <>
      <div
        className={`fixed inset-0 top-16 z-[35] bg-slate-900/20 transition-opacity dark:bg-black/40 ${
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden={!open}
        onClick={onClose}
      />
      <aside
        className={`fixed bottom-0 right-0 top-16 z-[40] flex w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl transition-transform duration-300 ease-out dark:border-dark-border dark:bg-dark-surface ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        aria-hidden={!open}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-dark-border">
          <div>
            <p className="text-label-caps text-slate-500 dark:text-dark-text-secondary">Simulation</p>
            <p className="text-sm font-semibold text-slate-900 dark:text-dark-text-primary">
              {activeCounty || "Select a county on the map"}
            </p>
          </div>
          <button
            type="button"
            className="rounded-md p-2 text-slate-600 hover:bg-slate-100 dark:text-dark-text-secondary dark:hover:bg-dark-bg"
            aria-label="Close simulation panel"
            onClick={onClose}
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        <div className="flex flex-wrap gap-2 border-b border-slate-200 px-4 py-3 dark:border-dark-border">
          <button
            type="button"
            onClick={runGlobalSimulation}
            disabled={!canRun || loadingRun}
            className="rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 dark:disabled:bg-slate-600"
          >
            {loadingRun ? "Running…" : "Run global simulation"}
          </button>
          <button
            type="button"
            onClick={resetAll}
            className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-medium text-slate-700 dark:border-dark-border dark:text-dark-text-primary"
          >
            Reset all
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          <ScenarioChips
            scenarios={scenarios}
            onSelect={(county) => onScenarioChipSelect?.(county)}
            onRemove={onRemoveScenario}
          />
          <p className="mb-2 mt-3 text-xs text-slate-500 dark:text-dark-text-secondary">
            Tap a chip to load that county&apos;s saved scenario onto the map selection.
          </p>
          {previewError ? (
            <p className="mb-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {previewError}
            </p>
          ) : null}
          {activeCounty ? (
            <SimulationSlidersPanel
              selectedCounty={activeCounty}
              sliders={INTERVENTION_SLIDERS}
              draft={draft}
              onSliderChange={onSliderChange}
              presets={INTERVENTION_PRESETS}
              onApplyPreset={onApplyPreset}
              onClear={onClear}
              onSave={onSaveScenario}
              canSave={canSave}
              preview={preview}
              loadingPreview={loadingPreview}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-dark-text-secondary">
              Click a county on the map to adjust interventions. Saved scenarios appear as chips above.
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
