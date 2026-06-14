import { useState } from "react";
import { useAuth } from "../../auth/AuthContext";

export default function AuthPage() {
  const { login, signup, setAuthError, authError } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState("");

  const onSubmit = async (event) => {
    event.preventDefault();
    setLocalError("");
    setAuthError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        if (password.length < 8) {
          setLocalError("Password must be at least 8 characters.");
          return;
        }
        await signup(email.trim(), password, fullName.trim());
      }
    } catch (err) {
      setLocalError(err.message || "Authentication failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const displayError = localError || authError;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-emerald-50 via-white to-slate-100 px-4 dark:from-dark-bg dark:via-dark-surface dark:to-dark-bg">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl dark:border-dark-border dark:bg-dark-surface">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold tracking-wider text-emerald-900 dark:text-dark-accent">AGRIGRAPH AI</h1>
          <p className="mt-2 text-sm text-slate-600 dark:text-dark-text-secondary">
            County-level dairy sustainability forecasting
          </p>
        </div>

        <div className="mb-6 flex rounded-lg bg-slate-100 p-1 dark:bg-dark-bg">
          <button
            type="button"
            className={`flex-1 rounded-md py-2 text-sm font-semibold ${mode === "login" ? "bg-white text-emerald-800 shadow dark:bg-dark-surface dark:text-dark-accent" : "text-slate-500 dark:text-dark-text-secondary"}`}
            onClick={() => setMode("login")}
          >
            Sign in
          </button>
          <button
            type="button"
            className={`flex-1 rounded-md py-2 text-sm font-semibold ${mode === "signup" ? "bg-white text-emerald-800 shadow dark:bg-dark-surface dark:text-dark-accent" : "text-slate-500 dark:text-dark-text-secondary"}`}
            onClick={() => setMode("signup")}
          >
            Sign up
          </button>
        </div>

        <form className="space-y-4" onSubmit={onSubmit}>
          {mode === "signup" ? (
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700 dark:text-dark-text-primary">Full name</span>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-dark-border dark:bg-dark-bg dark:text-dark-text-primary"
                placeholder="Optional"
              />
            </label>
          ) : null}
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-dark-text-primary">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-dark-border dark:bg-dark-bg dark:text-dark-text-primary"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-dark-text-primary">Password</span>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-dark-border dark:bg-dark-bg dark:text-dark-text-primary"
            />
          </label>
          {displayError ? (
            <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {displayError}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 dark:disabled:bg-slate-600"
          >
            {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
