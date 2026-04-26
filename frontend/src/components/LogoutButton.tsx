import { useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export function LogoutButton() {
  const { logout } = useAuth();
  const nav = useNavigate();
  async function handleClick() {
    await logout();
    nav("/login", { replace: true });
  }
  return (
    <button type="button" className="nav-logout" onClick={handleClick} title="Ausloggen">
      Logout
    </button>
  );
}
