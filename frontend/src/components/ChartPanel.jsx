export default function ChartPanel({ title, subtitle, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        {subtitle ? <p className="text-xs text-slate-600">{subtitle}</p> : null}
      </div>
      <div className="h-72">{children}</div>
    </section>
  );
}

