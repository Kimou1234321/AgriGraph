export default function InterventionSlider({ label, value, min = -0.2, max = 0.2, step = 0.01, onChange }) {
  const pct = ((value - min) / (max - min)) * 100;
  const center = ((0 - min) / (max - min)) * 100;
  return (
    <label className="block rounded-lg border border-slate-200 bg-white p-3 dark:border-dark-border dark:bg-dark-surface">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-800 dark:text-dark-text-primary">{label}</span>
        <span className="text-xs font-semibold text-slate-600 dark:text-dark-text-secondary">{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="relative h-5">
        <div className="absolute left-0 right-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-slate-200 dark:bg-dark-border" />
        <div
          className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-amber-400 dark:bg-amber-500/80"
          style={{ left: `${Math.min(pct, center)}%`, width: `${Math.abs(pct - center)}%` }}
        />
        <div
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 bg-slate-500 dark:bg-dark-text-secondary"
          style={{ left: `${center}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          className="absolute left-0 top-1/2 w-full -translate-y-1/2"
        />
      </div>
    </label>
  );
}
