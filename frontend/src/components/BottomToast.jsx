import { useEffect } from "react";

const CONSTANTS = {
  AUTO_DISMISS_MS: 3500,
};

export default function BottomToast({ message, variant, onDismiss }) {
  useEffect(() => {
    if (!message) return undefined;
    const timer = window.setTimeout(() => onDismiss?.(), CONSTANTS.AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;

  const isSuccess = variant === "success";
  const shellClass = isSuccess
    ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/90 dark:text-emerald-100"
    : "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/90 dark:text-red-100";
  const icon = isSuccess ? "check_circle" : "error";

  return (
    <div
      role="status"
      className={`fixed bottom-6 left-1/2 z-[110] flex max-w-md -translate-x-1/2 items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium shadow-lg transition-all ${shellClass}`}
    >
      <span className="material-symbols-outlined text-base">{icon}</span>
      <span className="flex-1">{message}</span>
      <button
        type="button"
        onClick={onDismiss}
        className="material-symbols-outlined rounded p-0.5 text-base opacity-70 hover:opacity-100"
        aria-label="Dismiss"
      >
        close
      </button>
    </div>
  );
}
