export default function ChartPanel({ title, subtitle, children, variant = "solid" }) {
  const shell =
    variant === "glass"
      ? "rounded-xl border border-white/40 bg-white/75 p-4 shadow-sm backdrop-blur-md dark:border-dark-border/60 dark:bg-dark-surface/80"
      : "rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-dark-border dark:bg-dark-surface";
  const titleCls =
    variant === "glass"
      ? "text-sm font-semibold text-slate-900 dark:text-dark-text-primary"
      : "text-sm font-semibold text-slate-900 dark:text-dark-text-primary";
  const subtitleCls =
    variant === "glass"
      ? "text-xs text-slate-600 dark:text-dark-text-secondary"
      : "text-xs text-slate-600 dark:text-dark-text-secondary";

  return (
    <section className={shell}>
      <div className="mb-3">
        <h3 className={titleCls}>{title}</h3>
        {subtitle ? <p className={subtitleCls}>{subtitle}</p> : null}
      </div>
      <div className="h-72">{children}</div>
    </section>
  );
}
