import IrelandRealMap from "../atlas/IrelandRealMap";

/** Compact minimap with tier-colored centroid markers. */
export default function MiniMapNodes(props) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-dark-border dark:bg-dark-surface">
      <IrelandRealMap {...props} variant="mini" className="w-full" />
    </div>
  );
}
