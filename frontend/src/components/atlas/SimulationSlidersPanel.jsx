import InterventionSlider from "../InterventionSlider";
import PillarRadar from "../PillarRadar";

export default function SimulationSlidersPanel({
  selectedCounty,
  sliders,
  draft,
  onSliderChange,
  presets,
  onApplyPreset,
  onClear,
  onSave,
  canSave,
  preview,
  loadingPreview,
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-dark-border dark:bg-dark-bg">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={!canSave}
          className="rounded bg-[#2D6A4F] px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 dark:disabled:bg-slate-600"
        >
          Save scenario for {selectedCounty}
        </button>
        <button
          type="button"
          onClick={onClear}
          className="rounded bg-slate-100 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-200 dark:bg-dark-border dark:text-dark-text-primary dark:hover:bg-dark-surface"
        >
          Clear sliders
        </button>
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        {Object.keys(presets).map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => onApplyPreset(name)}
            className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200 dark:bg-dark-border dark:text-dark-text-primary dark:hover:bg-dark-surface"
          >
            {name}
          </button>
        ))}
      </div>
      <div className="max-h-[24rem] space-y-3 overflow-y-auto pr-1">
        {sliders.map((slider) => (
          <InterventionSlider
            key={slider.key}
            label={slider.label}
            value={draft[slider.key] ?? 0}
            onChange={(value) => onSliderChange(slider.key, value)}
          />
        ))}
      </div>
      <div className="mt-3 h-64 rounded-lg border border-slate-200 p-2 dark:border-dark-border dark:bg-dark-surface/60">
        {loadingPreview ? (
          <p className="text-sm text-slate-600 dark:text-dark-text-secondary">Updating preview...</p>
        ) : null}
        {preview ? (
          <PillarRadar labels={Object.keys(preview.before)} before={preview.before} after={preview.after} />
        ) : (
          <p className="text-sm text-slate-600 dark:text-dark-text-secondary">Adjust sliders to preview pillar impact.</p>
        )}
      </div>
    </div>
  );
}
