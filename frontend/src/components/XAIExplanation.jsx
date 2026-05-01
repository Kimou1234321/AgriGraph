export default function XAIExplanation({ text }) {
  const [stage1 = "", stage2 = ""] = String(text || "").split("\n\n");
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">Two-stage explanation</h3>
      <div className="mt-3 space-y-3 text-sm text-slate-700">
        <p><span className="material-symbols-outlined mr-1 align-middle text-base">build</span>{stage1}</p>
        <p><span className="material-symbols-outlined mr-1 align-middle text-base">smart_toy</span>{stage2}</p>
      </div>
    </section>
  );
}

