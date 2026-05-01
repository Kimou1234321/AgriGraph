import CountyDashboardPanel from "./CountyDashboardPanel";
import CountyResultDetail from "./CountyResultDetail";
import CountyResultSummary from "./CountyResultSummary";

const CONSTANTS = {
  /** Visible height of the stats stack at scroll 0 (map fills the rest). */
  STATS_PEEK_PX: 220,
};

/** Scrollable panel rising from lower viewport; switches dashboard vs simulation output. */
export default function CountyDetailPanel({
  county,
  viewMode,
  selectedYear,
  simulationBlock,
  onOpenSimulation,
  timeline,
  indicators,
  radarSingle,
  pillarKeys,
  pillars,
}) {
  if (!county) return null;

  const showSimulation = viewMode === "simulation" && simulationBlock;
  const panelTopMargin = `calc(100dvh - ${CONSTANTS.STATS_PEEK_PX}px)`;

  return (
    <div
      className="pointer-events-auto relative z-10 min-h-[85vh] rounded-t-3xl border border-white/40 border-b-0 bg-white/75 px-4 py-6 shadow-[0_-12px_40px_rgba(15,23,42,0.12)] backdrop-blur-md dark:border-dark-border/60 dark:bg-dark-surface/80 sm:px-6"
      style={{ marginTop: panelTopMargin }}
    >
      <div className="mx-auto max-w-[1280px]">
        <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-dark-text-primary">{county}</h2>
        {showSimulation ? (
          <div className="space-y-4">
            <CountyResultSummary county={county} block={simulationBlock} onEditScenarios={onOpenSimulation} glass />
            <CountyResultDetail block={simulationBlock} glass />
          </div>
        ) : (
          <CountyDashboardPanel
            selectedCounty={county}
            selectedYear={selectedYear}
            timeline={timeline}
            indicators={indicators}
            radarSingle={radarSingle}
            pillarKeys={pillarKeys}
            pillars={pillars}
            glass
          />
        )}
      </div>
    </div>
  );
}
