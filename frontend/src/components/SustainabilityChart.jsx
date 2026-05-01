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

export default function SustainabilityChart({ data, mode = "timeline" }) {
  if (mode === "counterfactual") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="year" />
          <YAxis domain={[(min) => Math.floor((min - 1) * 10) / 10, (max) => Math.ceil((max + 1) * 10) / 10]} />
          <Tooltip formatter={(value) => Number(value).toFixed(1)} />
          <Legend />
          <Line dataKey="baseline" name="Baseline" stroke="#1f2937" strokeWidth={2} dot={{ r: 3 }} />
          <Line dataKey="counterfactual" name="Counterfactual" stroke="#2d6a4f" strokeWidth={3} dot={{ r: 4 }} />
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

