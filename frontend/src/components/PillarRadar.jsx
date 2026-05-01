import { Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";

export default function PillarRadar({ labels, before, after, single }) {
  const normalize = (value) => Math.max(0, Math.min(100, ((Number(value) + 3) / 6) * 100));
  const baseSeries =
    single ??
    labels.map((label) => ({
      pillar: label,
      before: normalize(before?.[label] ?? 0),
      after: normalize(after?.[label] ?? 0),
    }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={baseSeries}>
        <PolarGrid />
        <PolarAngleAxis dataKey="pillar" tick={{ fontSize: 11 }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} />
        <Legend />
        {single ? <Radar name="Pillar score" dataKey="value" stroke="#2d6a4f" fill="#2d6a4f" fillOpacity={0.4} /> : null}
        {!single ? (
          <>
            <Radar name="Before" dataKey="before" stroke="#1f2937" fill="#1f2937" fillOpacity={0.25} />
            <Radar name="After" dataKey="after" stroke="#2d6a4f" fill="#2d6a4f" fillOpacity={0.35} />
          </>
        ) : null}
      </RadarChart>
    </ResponsiveContainer>
  );
}

