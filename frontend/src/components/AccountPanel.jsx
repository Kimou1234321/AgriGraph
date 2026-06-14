import { useEffect, useState } from "react";
import { deleteSavedSimulation, fetchSavedSimulations } from "../api";
import { useAuth } from "../auth/AuthContext";

export default function AccountPanel({ open, onClose, onLoadSimulation, onOpenMethodology }) {
  const { user, logout } = useAuth();
  const [simulations, setSimulations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const rows = await fetchSavedSimulations();
        if (!cancelled) setSimulations(rows);
      } catch (err) {
        if (!cancelled) setError(err.message || "Unable to load saved simulations.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const handleDelete = async (id) => {
    try {
      await deleteSavedSimulation(id);
      setSimulations((prev) => prev.filter((row) => row.id !== id));
    } catch (err) {
      setError(err.message || "Unable to delete simulation.");
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 px-4 dark:bg-black/50">
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-dark-border dark:bg-dark-surface">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-dark-border">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-dark-text-primary">Account</h2>
          <button
            type="button"
            onClick={onClose}
            className="material-symbols-outlined rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-dark-bg"
            aria-label="Close"
          >
            close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-dark-border dark:bg-dark-bg">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-dark-text-secondary">
              Signed in as
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-dark-text-primary">{user?.email}</p>
            {user?.full_name ? (
              <p className="text-sm text-slate-600 dark:text-dark-text-secondary">{user.full_name}</p>
            ) : null}
          </div>

          <h3 className="mb-2 mt-6 text-sm font-semibold text-slate-900 dark:text-dark-text-primary">Saved simulations</h3>
          {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
          {error ? (
            <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </p>
          ) : null}
          {!loading && simulations.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-dark-text-secondary">No saved simulations yet.</p>
          ) : null}
          <ul className="space-y-2">
            {simulations.map((row) => (
              <li
                key={row.id}
                className="flex items-start justify-between gap-2 rounded-lg border border-slate-200 p-3 dark:border-dark-border"
              >
                <button
                  type="button"
                  className="flex-1 text-left"
                  onClick={() => onLoadSimulation(row.id)}
                >
                  <p className="text-sm font-semibold text-emerald-800 dark:text-dark-accent">{row.name}</p>
                  {row.description ? (
                    <p className="mt-1 text-xs text-slate-600 dark:text-dark-text-secondary">{row.description}</p>
                  ) : null}
                  <p className="mt-1 text-xs text-slate-500 dark:text-dark-text-secondary">
                    {row.county_count} counties · horizon {row.horizon}
                    {row.uplift_final_year != null ? ` · uplift ${row.uplift_final_year > 0 ? "+" : ""}${Number(row.uplift_final_year).toFixed(1)}` : ""}
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(row.id)}
                  className="material-symbols-outlined text-sm text-slate-400 hover:text-red-600"
                  aria-label="Delete simulation"
                >
                  delete
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-center justify-between border-t border-slate-200 px-6 py-3 dark:border-dark-border">
          <button
            type="button"
            onClick={onOpenMethodology}
            className="flex items-center gap-1 rounded-full border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 dark:border-dark-border dark:text-dark-text-primary"
            title="Methodology"
          >
            <span className="material-symbols-outlined text-base">help</span>
            Methodology
          </button>
          <button
            type="button"
            onClick={async () => {
              await logout();
              onClose();
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 dark:border-dark-border dark:text-dark-text-primary"
          >
            Log out
          </button>
        </div>
      </div>
    </div>
  );
}
