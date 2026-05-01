export default function ScenarioChips({ scenarios, onSelect, onRemove }) {
  const counties = Object.keys(scenarios);
  if (counties.length === 0) {
    return <p className="text-xs text-slate-500 dark:text-dark-text-secondary">No saved county scenarios yet.</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {counties.map((county) => (
        <div
          key={county}
          className="flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200"
        >
          <button type="button" onClick={() => onSelect(county)}>
            {county}
          </button>
          <button
            type="button"
            onClick={() => onRemove(county)}
            className="rounded-full px-1 text-emerald-700 hover:bg-emerald-100 dark:text-emerald-300 dark:hover:bg-emerald-900/50"
          >
            x
          </button>
        </div>
      ))}
    </div>
  );
}
