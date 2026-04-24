import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, setCsrfToken } from "../api/client";
import { extractApiError } from "../lib/apiError";
import type { AuthUser } from "../hooks/useAuth";

interface Props {
  onLogin: (user: AuthUser) => void;
}

export function LoginPage({ onLogin }: Props) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("changeme");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.post("/auth/login", { username, password });
      setCsrfToken(res.data.csrf_token);
      onLogin({ username: res.data.username, role: res.data.role });
      nav("/");
    } catch (err) {
      setError(extractApiError(err, "Login fehlgeschlagen"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page narrow">
      <h1>CompanyTracker Login</h1>
      <form onSubmit={submit}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Benutzername"
          autoComplete="username"
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Passwort"
          type="password"
          autoComplete="current-password"
        />
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Anmelden..." : "Login"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
