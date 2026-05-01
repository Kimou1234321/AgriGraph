/** Two-segment pill: Initial stats vs Simulation stats (only meaningful when a run exists). */
export default function SimToggle({ value, onChange, className = "" }) {
  return (
    <div
      className={`inline-flex rounded-full border border-slate-200 bg-slate-100 p-0.5 text-xs font-semibold dark:border-dark-border dark:bg-dark-bg ${className}`}
      role="group"
      aria-label="Data source"
    >
      <button
        type="button"
        className={`rounded-full px-4 py-2 transition-colors ${
          value === "initial"
            ? "bg-white text-emerald-800 shadow-sm dark:bg-dark-surface dark:text-dark-accent"
            : "text-slate-600 dark:text-dark-text-secondary"
        }`}
        onClick={() => onChange("initial")}
      >
        Initial
      </button>
      <button
        type="button"
        className={`rounded-full px-4 py-2 transition-colors ${
          value === "simulation"
            ? "bg-white text-emerald-800 shadow-sm dark:bg-dark-surface dark:text-dark-accent"
            : "text-slate-600 dark:text-dark-text-secondary"
        }`}
        onClick={() => onChange("simulation")}
      >
        Simulation
      </button>
    </div>
  );
}
