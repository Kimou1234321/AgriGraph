import XAIExplanation from "../XAIExplanation";

export default function CountyResultSummary({ county, block, onEditScenarios, glass = false }) {
  const finalYear = block?.uplift?.length ? block.uplift[block.uplift.length - 1].year : 2036;
  const finalDelta = block?.uplift_final_year ?? 0;
  const shifts = block?.pillar_shifts ?? { P1: 0, P2: 0, P3: 0, P4: 0 };
  const shell = glass
    ? "space-y-3 rounded-xl border border-white/40 bg-white/75 p-4 backdrop-blur-md dark:border-dark-border/60 dark:bg-dark-surface/80"
    : "space-y-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-dark-border dark:bg-dark-surface";
  return (
    <div className={shell}>
      <h3 className="text-sm font-semibold text-slate-900 dark:text-dark-text-primary">{county} simulation output</h3>
      <div className="rounded-lg bg-emerald-50 p-3 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">
        <p className="text-xs font-medium">Final uplift</p>
        <p className="text-lg font-bold">
          {finalDelta > 0 ? "+" : ""}
          {Number(finalDelta).toFixed(1)} points by {finalYear}
        </p>
      </div>
      <div className="space-y-2">
        {Object.entries(shifts).map(([key, value]) => {
          const pct = Math.min(100, Math.abs(Number(value)) * 30);
          return (
            <div key={key}>
              <div className="mb-1 flex justify-between text-xs text-slate-600 dark:text-dark-text-secondary">
                <span>{key}</span>
                <span>{Number(value).toFixed(2)}</span>
              </div>
              <div className="h-2 rounded bg-slate-200 dark:bg-dark-border">
                <div className="h-2 rounded bg-emerald-600" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <XAIExplanation text={block?.explanation || "No explanation generated for this county."} />
      <button
        type="button"
        onClick={onEditScenarios}
        className="w-full rounded bg-slate-100 px-3 py-2 text-xs font-medium text-slate-700 dark:bg-dark-border dark:text-dark-text-primary"
      >
        Edit scenarios
      </button>
    </div>
  );
}
