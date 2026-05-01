export default function LoadingState({ label = "Loading..." }) {
  return (
    <div className="flex items-center justify-center rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">
      <span className="mr-2 inline-block h-3 w-3 animate-pulse rounded-full bg-emerald-700" />
      {label}
    </div>
  );
}

