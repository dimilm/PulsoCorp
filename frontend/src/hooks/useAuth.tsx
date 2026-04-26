import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { api, AUTH_LOST_EVENT, setCsrfToken } from "../api/client";

export type AuthUser = { username: string; role: string } | null;

interface AuthContextValue {
  user: AuthUser;
  loading: boolean;
  setUser: (user: AuthUser) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Bootstrap the current session by hitting `/auth/me` once on mount.
 *
 * Provides `user`, `loading`, `setUser` and `logout` via React Context so
 * components don't have to thread the values through props. The provider also
 * listens for the global `AUTH_LOST_EVENT` (emitted by the axios 401
 * interceptor) so any subsequent failure logs the user out across the whole
 * app instead of silently leaving stale state.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .get("/auth/me")
      .then((res) => {
        if (cancelled) return;
        setUser({ username: res.data.username, role: res.data.role });
      })
      .catch(() => {
        if (cancelled) return;
        setCsrfToken(null);
        setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function onAuthLost() {
      setCsrfToken(null);
      setUser(null);
    }
    window.addEventListener(AUTH_LOST_EVENT, onAuthLost);
    return () => window.removeEventListener(AUTH_LOST_EVENT, onAuthLost);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      setUser,
      logout: async () => {
        await logoutRequest();
        setUser(null);
      },
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}

export async function logoutRequest(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } catch {
    // Even if the network call fails the client should consider itself logged
    // out so it stops sending requests with stale credentials.
  }
  setCsrfToken(null);
}
