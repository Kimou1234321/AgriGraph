import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchMe, login as apiLogin, logout as apiLogout, signup as apiSignup } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [authError, setAuthError] = useState("");

  const refreshMe = useCallback(async () => {
    try {
      setAuthError("");
      const profile = await fetchMe();
      setUser(profile);
      return profile;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const boot = async () => {
      setLoadingAuth(true);
      await refreshMe();
      if (!cancelled) setLoadingAuth(false);
    };
    boot();
    return () => {
      cancelled = true;
    };
  }, [refreshMe]);

  const login = useCallback(async (email, password) => {
    setAuthError("");
    const profile = await apiLogin({ email, password });
    setUser(profile);
    return profile;
  }, []);

  const signup = useCallback(async (email, password, fullName) => {
    setAuthError("");
    const profile = await apiSignup({ email, password, full_name: fullName || null });
    setUser(profile);
    return profile;
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loadingAuth,
      authError,
      setAuthError,
      login,
      signup,
      logout,
      refreshMe,
      isAuthenticated: Boolean(user),
    }),
    [user, loadingAuth, authError, login, signup, logout, refreshMe]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider.");
  return ctx;
}
