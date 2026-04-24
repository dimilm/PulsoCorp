import { useNavigate } from "react-router-dom";

import { logoutRequest } from "../hooks/useAuth";

interface Props {
  onLoggedOut: () => void;
}

export function LogoutButton({ onLoggedOut }: Props) {
  const nav = useNavigate();
  async function handleClick() {
    await logoutRequest();
    onLoggedOut();
    nav("/login", { replace: true });
  }
  return (
    <button type="button" className="nav-logout" onClick={handleClick} title="Ausloggen">
      Logout
    </button>
  );
}
