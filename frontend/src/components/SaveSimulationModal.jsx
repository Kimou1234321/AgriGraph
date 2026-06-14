import { useState } from "react";

export default function SaveSimulationModal({ open, onClose, onSave, saving, error }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  if (!open) return null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    await onSave({ name: name.trim(), description: description.trim() || null });
    setName("");
    setDescription("");
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 px-4 dark:bg-black/50">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-dark-border dark:bg-dark-surface">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-dark-text-primary">Save simulation</h2>
          <button
            type="button"
            onClick={onClose}
            className="material-symbols-outlined rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-dark-bg"
            aria-label="Close"
          >
            close
          </button>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-dark-text-primary">Name *</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-dark-border dark:bg-dark-bg dark:text-dark-text-primary"
              placeholder="e.g. Monaghan intervention Q2"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-dark-text-primary">Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-dark-border dark:bg-dark-bg dark:text-dark-text-primary"
              placeholder="Optional notes about this scenario"
            />
          </label>
          {error ? (
            <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </p>
          ) : null}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm dark:border-dark-border dark:text-dark-text-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
