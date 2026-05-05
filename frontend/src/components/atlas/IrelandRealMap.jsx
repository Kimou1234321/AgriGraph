import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import { feature } from "topojson-client";
import irelandTopology from "../../data/irish-counties-topology.json";
import { COUNTY_CENTROIDS, IRISH_COUNTIES_26 } from "../../constants/counties";
import { toScoreTier } from "../../api";

const CONSTANTS = {
  MAP_CENTER_LON: -8,
  MAP_CENTER_LAT: 53.35,
  MAP_SCALE_ATLAS: 7200,
  MAP_SCALE_MINI: 6000,
};

const countiesTopoObject = {
  ...irelandTopology.objects.counties,
  geometries: irelandTopology.objects.counties.geometries.filter((g) => IRISH_COUNTIES_26.includes(g.id)),
};

const irelandGeoJson = feature(irelandTopology, countiesTopoObject);

function countyFromGeography(geo) {
  return geo.id || geo.properties?.id || geo.properties?.name || "";
}

function tierMarkerClass(score) {
  const tier = toScoreTier(score ?? 0);
  if (tier === "Top") return "fill-green-600 stroke-green-800 dark:fill-green-500 dark:stroke-green-300";
  if (tier === "Mid") return "fill-amber-400 stroke-amber-700 dark:fill-amber-500 dark:stroke-amber-200";
  return "fill-red-500 stroke-red-800 dark:fill-red-400 dark:stroke-red-200";
}

/** Real Ireland county boundaries + centroid markers; atlas = neutral markers, mini = tier-colored. */
export default function IrelandRealMap({
  counties,
  selectedCounty,
  onSelectCounty,
  scoreByCounty = {},
  variant = "atlas",
  className = "",
}) {
  const scale = variant === "mini" ? CONSTANTS.MAP_SCALE_MINI : CONSTANTS.MAP_SCALE_ATLAS;
  const height = variant === "mini" ? 340 : "100%";

  return (
    <ComposableMap
      projection="geoMercator"
      projectionConfig={{
        center: [CONSTANTS.MAP_CENTER_LON, CONSTANTS.MAP_CENTER_LAT],
        scale,
      }}
      className={className}
      style={{ width: "100%", height }}
    >
      <Geographies geography={irelandGeoJson}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const name = countyFromGeography(geo);
            if (!counties.includes(name)) return null;
            const selected = selectedCounty === name;
            return (
              <Geography
                key={geo.rsmKey || name}
                geography={geo}
                onClick={() => onSelectCounty?.(name)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectCounty?.(name);
                  }
                }}
                tabIndex={0}
                className={`cursor-pointer outline-none transition-colors fill-slate-100 stroke-slate-400 hover:fill-emerald-50 hover:stroke-emerald-600 dark:fill-slate-800/95 dark:stroke-slate-500 dark:hover:fill-emerald-950/40 dark:hover:stroke-emerald-400 ${
                  selected ? "stroke-emerald-700 dark:stroke-emerald-400" : ""
                }`}
                style={{
                  default: { strokeWidth: selected ? 1.35 : variant === "mini" ? 0.85 : 0.65, outline: "none" },
                  hover: { strokeWidth: 1.1, outline: "none" },
                  pressed: { outline: "none" },
                }}
              />
            );
          })
        }
      </Geographies>
      {counties
        .filter((c) => IRISH_COUNTIES_26.includes(c) && COUNTY_CENTROIDS[c])
        .map((county) => {
          const [lat, lon] = COUNTY_CENTROIDS[county];
          const selected = selectedCounty === county;
          const score = scoreByCounty[county];
          const colorClasses =
            variant === "mini" && Number.isFinite(score)
              ? tierMarkerClass(score)
              : "fill-white stroke-slate-600 dark:fill-slate-700 dark:stroke-slate-300";
          const r = variant === "mini" ? (selected ? 8.5 : 6.5) : selected ? 7 : 5;
          return (
            <Marker key={county} coordinates={[lon, lat]}>
              <g
                role="button"
                tabIndex={0}
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectCounty?.(county);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectCounty?.(county);
                  }
                }}
              >
                <circle
                  r={r}
                  className={`${colorClasses}`}
                  strokeWidth={selected ? (variant === "mini" ? 2.5 : 2.2) : variant === "mini" ? 1.65 : 1.2}
                />
              </g>
            </Marker>
          );
        })}
    </ComposableMap>
  );
}
