import { useLayoutEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";

/** Decorative node positions (% of viewport) — visually random, deterministic on reload */
const NODES = [
  { id: 0, top: 10, left: 14, size: 44 },
  { id: 1, top: 16, left: 61, size: 34 },
  { id: 2, top: 22, left: 86, size: 39 },
  { id: 3, top: 43, left: 9, size: 36 },
  { id: 4, top: 47, left: 91, size: 42 },
  { id: 5, top: 72, left: 18, size: 38 },
  { id: 6, top: 82, left: 55, size: 32 },
  { id: 7, top: 76, left: 84, size: 45 },
];

const CENTER_CIRCLE_PX = 56;

/** Line endpoints on circle perimeters (same trajectory as center-to-center). */
function lineEndpointsOnRadii(node, width, height) {
  const nodeCx = (node.left / 100) * width;
  const nodeCy = (node.top / 100) * height;
  const centerCx = width / 2;
  const centerCy = height / 2;
  const dx = centerCx - nodeCx;
  const dy = centerCy - nodeCy;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const nodeRadius = node.size / 2;
  const centerRadius = CENTER_CIRCLE_PX / 2;

  const startX = nodeCx + ux * nodeRadius;
  const startY = nodeCy + uy * nodeRadius;
  const endX = centerCx - ux * centerRadius;
  const endY = centerCy - uy * centerRadius;

  return {
    x1: (startX / width) * 100,
    y1: (startY / height) * 100,
    x2: (endX / width) * 100,
    y2: (endY / height) * 100,
  };
}
const CIRCLE_BOUNCE_MS = 580;
const CIRCLE_START_WINDOW_MS = 200;
const LINE_DURATION_MS = 260;
const CARD_REVEAL_BUFFER_MS = 50;
const CARD_REVEAL_DURATION_MS = 450;

const inputClass =
  "w-full rounded-xl border border-slate-200/80 bg-white/90 px-3.5 py-2.5 text-sm shadow-sm transition-all placeholder:text-slate-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25 dark:border-dark-border dark:bg-dark-bg/80 dark:text-dark-text-primary dark:placeholder:text-dark-text-secondary dark:focus:border-dark-accent dark:focus:ring-dark-accent/25";

export default function AuthPage() {
  const { login, signup, setAuthError, authError } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState("");
  const [viewport, setViewport] = useState({ width: 0, height: 0 });

  const circleStartMs = useMemo(
    () => Array.from({ length: 9 }, () => Math.floor(Math.random() * CIRCLE_START_WINDOW_MS)),
    []
  );
  const lineStartMs = Math.max(...circleStartMs) + CIRCLE_BOUNCE_MS;
  const cardRevealMs = lineStartMs + LINE_DURATION_MS + CARD_REVEAL_BUFFER_MS;

  useLayoutEffect(() => {
    const update = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

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
    <div className="auth-stage relative isolate min-h-screen overflow-hidden bg-gradient-to-br from-emerald-50/90 via-white to-slate-100 dark:from-dark-bg dark:via-[#0d1628] dark:to-dark-bg">
      <style>{`
        @keyframes auth-circle-bounce {
          0% { transform: translate(-50%, -50%) scale(0); opacity: 0; }
          35% { transform: translate(-50%, -50%) scale(1.28); opacity: 1; }
          55% { transform: translate(-50%, -50%) scale(0.88); opacity: 1; }
          75% { transform: translate(-50%, -50%) scale(1.06); opacity: 1; }
          100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
        }
        @keyframes auth-line-draw {
          from { stroke-dashoffset: 1; opacity: 0.35; }
          to { stroke-dashoffset: 0; opacity: 1; }
        }
        @keyframes auth-card-reveal {
          0% { transform: scale(0.35); opacity: 0; filter: blur(8px); }
          55% { transform: scale(1.04); opacity: 1; filter: blur(0); }
          100% { transform: scale(1); opacity: 1; filter: blur(0); }
        }
        @keyframes auth-glow-pulse {
          0%, 100% { opacity: 0.45; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.08); }
        }
        .auth-circle,
        .auth-center-circle {
          animation: auth-circle-bounce ${CIRCLE_BOUNCE_MS}ms cubic-bezier(0.34, 1.4, 0.64, 1) forwards;
          transform: translate(-50%, -50%) scale(0);
          opacity: 0;
        }
        .auth-line {
          stroke-dasharray: 1;
          stroke-dashoffset: 1;
          animation: auth-line-draw ${LINE_DURATION_MS}ms ease-out forwards;
          animation-delay: ${lineStartMs}ms;
        }
        .auth-card {
          animation: auth-card-reveal ${CARD_REVEAL_DURATION_MS}ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
          animation-delay: ${cardRevealMs}ms;
          opacity: 0;
          transform: scale(0.35);
        }
        .auth-center-glow {
          animation: auth-glow-pulse 3s ease-in-out infinite;
          animation-delay: ${cardRevealMs}ms;
        }
        @media (prefers-reduced-motion: reduce) {
          .auth-circle, .auth-center-circle, .auth-line, .auth-card, .auth-center-glow {
            animation: none !important;
            opacity: 1 !important;
            transform: none !important;
            stroke-dashoffset: 0 !important;
          }
          .auth-circle, .auth-center-circle { transform: translate(-50%, -50%) scale(1) !important; }
        }
      `}</style>

      {/* Ambient background orbs */}
      <div
        className="pointer-events-none absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-primary/8 blur-3xl dark:bg-dark-accent/10"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -right-24 bottom-1/4 h-80 w-80 rounded-full bg-soft-green/20 blur-3xl dark:bg-primary/15"
        aria-hidden
      />

      {/* Lines from nodes to center (below nodes) */}
      <div className="pointer-events-none absolute inset-0 z-0" aria-hidden>
        <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <linearGradient id="auth-line-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#2D6A4F" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#5AB587" stopOpacity="0.75" />
            </linearGradient>
          </defs>
          {viewport.width > 0 &&
            NODES.map((node) => {
              const { x1, y1, x2, y2 } = lineEndpointsOnRadii(node, viewport.width, viewport.height);
              return (
                <line
                  key={`line-${node.id}`}
                  className="auth-line"
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  pathLength="1"
                  stroke="url(#auth-line-gradient)"
                  strokeWidth="0.35"
                  strokeLinecap="round"
                />
              );
            })}
        </svg>
      </div>

      {/* Bouncing circles (above lines) */}
      <div className="pointer-events-none absolute inset-0 z-10" aria-hidden>
        {NODES.map((node, index) => (
          <div
            key={node.id}
            className="auth-circle absolute rounded-full border border-primary/40 bg-gradient-to-br from-emerald-100 to-emerald-200/90 shadow-[0_0_24px_rgba(45,106,79,0.35)] dark:border-dark-accent/50 dark:from-[#1a3d2e] dark:to-[#234a38]"
            style={{
              top: `${node.top}%`,
              left: `${node.left}%`,
              width: node.size,
              height: node.size,
              animationDelay: `${circleStartMs[index]}ms`,
            }}
          />
        ))}

        {/* Center target circle */}
        <div
          className="auth-center-circle absolute left-1/2 top-1/2 h-14 w-14 rounded-full border border-primary/40 bg-gradient-to-br from-emerald-100 via-emerald-200/90 to-emerald-50 shadow-[0_0_34px_rgba(45,106,79,0.38)] dark:border-dark-accent/50 dark:from-[#1a3d2e] dark:via-[#234a38] dark:to-[#152a22]"
          style={{ animationDelay: `${circleStartMs[8]}ms` }}
        />
      </div>

      {/* Center glow where lines converge */}
      <div
        className="auth-center-glow pointer-events-none absolute left-1/2 top-1/2 z-[5] h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-0"
        style={{ background: "radial-gradient(circle, rgba(45,106,79,0.22) 0%, rgba(149,212,179,0.08) 45%, transparent 70%)" }}
        aria-hidden
      />

      {/* Login card */}
      <div className="relative z-20 flex min-h-screen items-center justify-center px-4 py-10">
        <div className="auth-card w-full max-w-md">
          <div className="relative overflow-hidden rounded-2xl border border-white/60 bg-white/85 p-8 shadow-[0_24px_64px_-12px_rgba(27,67,50,0.18),0_0_0_1px_rgba(45,106,79,0.06)] backdrop-blur-xl dark:border-dark-border/80 dark:bg-dark-surface/90 dark:shadow-[0_24px_64px_-12px_rgba(0,0,0,0.55),0_0_0_1px_rgba(90,181,135,0.08)]">
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-primary to-transparent dark:via-dark-accent"
              aria-hidden
            />

            <div className="mb-7 text-center">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-deep-green text-lg font-bold text-white shadow-md dark:from-dark-accent dark:to-primary">
                A
              </div>
              <h1 className="text-2xl font-bold tracking-[0.2em] text-deep-green dark:text-dark-accent">
                AGRIGRAPH AI
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-dark-text-secondary">
                County-level dairy sustainability forecasting
              </p>
            </div>

            <div className="mb-6 flex rounded-xl border border-slate-200/60 bg-slate-100/80 p-1 dark:border-dark-border dark:bg-dark-bg/60">
              <button
                type="button"
                className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition-all duration-200 ${
                  mode === "login"
                    ? "bg-white text-primary shadow-sm ring-1 ring-primary/10 dark:bg-dark-surface dark:text-dark-accent dark:ring-dark-accent/20"
                    : "text-slate-500 hover:text-slate-700 dark:text-dark-text-secondary dark:hover:text-dark-text-primary"
                }`}
                onClick={() => setMode("login")}
              >
                Sign in
              </button>
              <button
                type="button"
                className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition-all duration-200 ${
                  mode === "signup"
                    ? "bg-white text-primary shadow-sm ring-1 ring-primary/10 dark:bg-dark-surface dark:text-dark-accent dark:ring-dark-accent/20"
                    : "text-slate-500 hover:text-slate-700 dark:text-dark-text-secondary dark:hover:text-dark-text-primary"
                }`}
                onClick={() => setMode("signup")}
              >
                Sign up
              </button>
            </div>

            <form className="space-y-4" onSubmit={onSubmit}>
              {mode === "signup" ? (
                <label className="block text-sm">
                  <span className="mb-1.5 block font-medium text-slate-700 dark:text-dark-text-primary">
                    Full name
                  </span>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className={inputClass}
                    placeholder="Optional"
                  />
                </label>
              ) : null}
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-slate-700 dark:text-dark-text-primary">Email</span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                  placeholder="you@example.com"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-slate-700 dark:text-dark-text-primary">Password</span>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass}
                  placeholder="••••••••"
                />
              </label>
              {displayError ? (
                <p className="rounded-xl border border-red-200/80 bg-red-50/90 px-3.5 py-2.5 text-sm text-red-700 shadow-sm dark:border-red-900/60 dark:bg-red-950/50 dark:text-red-200">
                  {displayError}
                </p>
              ) : null}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-xl bg-gradient-to-r from-primary to-deep-green px-4 py-3 text-sm font-semibold text-white shadow-md transition-all hover:shadow-lg hover:brightness-105 active:scale-[0.99] disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300 disabled:shadow-none dark:from-dark-accent dark:to-primary dark:disabled:from-slate-600 dark:disabled:to-slate-600"
              >
                {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
