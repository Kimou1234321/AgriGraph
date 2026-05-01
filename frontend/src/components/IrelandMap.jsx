export default function IrelandMap({ counties, selectedCounty, scoreByCounty, onSelectCounty }) {
  const tierColor = (score) => {
    if (!Number.isFinite(score)) return "#e2e8f0";
    if (score > 75) return "#95d5b2";
    if (score >= 50) return "#ffdfa0";
    return "#ffb3b3";
  };

  const countyPoints = [
    ["Donegal", 90, 55], ["Sligo", 110, 85], ["Leitrim", 135, 90], ["Mayo", 90, 115], ["Roscommon", 145, 120],
    ["Cavan", 165, 95], ["Monaghan", 185, 110], ["Louth", 205, 135], ["Meath", 185, 150], ["Dublin", 210, 160],
    ["Longford", 150, 145], ["Westmeath", 165, 165], ["Galway", 105, 155], ["Offaly", 175, 185], ["Kildare", 195, 185],
    ["Laois", 185, 210], ["Wicklow", 220, 205], ["Clare", 115, 205], ["Tipperary", 160, 235], ["Kilkenny", 200, 235],
    ["Wexford", 225, 255], ["Limerick", 130, 245], ["Waterford", 205, 260], ["Kerry", 90, 270], ["Cork", 130, 285], ["Carlow", 205, 225],
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="mb-3 text-xs text-slate-600">Click a county shape to inspect details for the selected year.</p>
      <svg viewBox="40 30 220 285" className="h-[460px] w-full rounded-lg bg-slate-50">
        <path d="M70,50 L170,45 L225,120 L240,205 L210,295 L95,305 L55,220 L60,110 Z" fill="#f8fafc" stroke="#94a3b8" strokeWidth="1.5" />
        {countyPoints
          .filter(([county]) => counties.includes(county))
          .map(([county, x, y]) => {
            const score = scoreByCounty[county];
            const selected = selectedCounty === county;
            return (
              <g key={county} onClick={() => onSelectCounty(county)} className="cursor-pointer">
                <circle cx={x} cy={y} r={selected ? 11 : 9} fill={tierColor(score)} stroke={selected ? "#166534" : "#334155"} strokeWidth={selected ? 2.5 : 1.2} />
                <text x={x} y={y - 14} textAnchor="middle" fontSize="8" fill="#0f172a">
                  {county}
                </text>
              </g>
            );
          })}
      </svg>
    </div>
  );
}

