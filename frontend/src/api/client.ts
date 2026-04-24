import axios from "axios";

const CSRF_COOKIE_NAME = "ct_csrf";

export const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
});

function readCsrfFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(`${CSRF_COOKIE_NAME}=`));
  if (!match) return null;
  try {
    return decodeURIComponent(match.slice(CSRF_COOKIE_NAME.length + 1));
  } catch {
    return null;
  }
}

export function setCsrfToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["X-CSRF-Token"] = token;
  } else {
    delete api.defaults.headers.common["X-CSRF-Token"];
  }
}

// On every outgoing request fall back to the CSRF cookie if no token has been
// set yet (e.g. right after a hard reload before /auth/me has resolved). The
// backend no longer rotates the token on /me, so reading the cookie value is
// the canonical source.
api.interceptors.request.use((config) => {
  if (!config.headers["X-CSRF-Token"]) {
    const fromCookie = readCsrfFromCookie();
    if (fromCookie) {
      config.headers["X-CSRF-Token"] = fromCookie;
    }
  }
  return config;
});

export const AUTH_LOST_EVENT = "ct:auth-lost";

// 401 -> session expired or never authenticated. Surface this to the app
// layer via a window event so any component can react (clear caches, redirect
// to /login, ...). We do not auto-redirect here because the /auth/me probe in
// useAuth legitimately returns 401 for anonymous visitors.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url: string | undefined = error?.config?.url;
    const isMeProbe = typeof url === "string" && url.includes("/auth/me");
    if (status === 401 && !isMeProbe && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(AUTH_LOST_EVENT));
    }
    return Promise.reject(error);
  }
);
