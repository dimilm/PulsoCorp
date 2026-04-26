import { useEffect, useState } from "react";

import { api, AUTH_LOST_EVENT, setCsrfToken } from "../api/client";

export type AuthUser = { username: string; role: string } | null;

/** Bootstrap the current session by hitting `/auth/me` once on mount.
 *
 * The hook also listens for the global `AUTH_LOST_EVENT` (emitted by the
 * axios 401 interceptor) so any subsequent failure logs the user out across
 * the whole app instead of silently leaving stale state in components.
 *
 * Note: `/auth/me` does NOT return a CSRF token. Token rotation happens
 * exclusively on `/login` and `/refresh`; in-flight calls read the value
 * straight from the (non-HttpOnly) CSRF cookie via the axios interceptor.
 */
export function useAuth() {
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

  return { user, setUser, loading };
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
