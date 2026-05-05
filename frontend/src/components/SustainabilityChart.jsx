import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function CounterfactualTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  const b = row?.baseline;
  const c = row?.counterfactual;
  const u = row?.uplift;
  const showDelta = typeof b === "number" && typeof c === "number";
  const deltaNum = typeof u === "number" ? u : showDelta ? Number(c) - Number(b) : NaN;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md dark:border-dark-border dark:bg-dark-surface">
      <p className="font-semibold text-slate-900 dark:text-dark-text-primary">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }} className="mt-0.5">
          {entry.name}: {Number(entry.value).toFixed(1)}
        </p>
      ))}
      {showDelta && Number.isFinite(deltaNum) ? (
        <p className="mt-1 border-t border-slate-100 pt-1 font-medium text-slate-700 dark:border-dark-border dark:text-dark-text-secondary">
          Uplift (CF − baseline): {deltaNum >= 0 ? "+" : ""}
          {deltaNum.toFixed(2)}
        </p>
      ) : null}
    </div>
  );
}

export default function SustainabilityChart({ data, mode = "timeline" }) {
  if (mode === "pillarTrend") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="year" />
          <YAxis domain={["auto", "auto"]} />
          <Tooltip formatter={(value) => Number(value).toFixed(2)} />
          <Legend />
          <Line type="monotone" dataKey="value" name="Pillar" stroke="#2d6a4f" strokeWidth={2} dot={{ r: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (mode === "counterfactual") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-dark-border" />
          <XAxis dataKey="year" />
          <YAxis domain={[(min) => Math.floor((min - 2) * 10) / 10, (max) => Math.ceil((max + 2) * 10) / 10]} />
          <Tooltip content={<CounterfactualTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="baseline"
            name="Baseline"
            stroke="#64748b"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={{ r: 2 }}
          />
          <Line
            type="monotone"
            dataKey="counterfactual"
            name="Counterfactual"
            stroke="#2d6a4f"
            strokeWidth={3}
            dot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="year" />
        <YAxis domain={[0, 100]} />
        <Tooltip />
        <Legend />
        <Area
          type="monotone"
          dataKey="upper_95pct"
          name="90% confidence band"
          fill="#d8f3dc"
          stroke="none"
          fillOpacity={0.5}
        />
        <Area type="monotone" dataKey="lower_5pct" fill="#ffffff" stroke="none" fillOpacity={1} />
        <Line type="monotone" dataKey="historical" name="Historical" stroke="#1b4332" strokeWidth={2} />
        <Line
          type="monotone"
          dataKey="forecast"
          name="Forecast"
          stroke="#2d6a4f"
          strokeDasharray="6 4"
          strokeWidth={2}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
