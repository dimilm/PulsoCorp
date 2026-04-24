import { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import type { AuthUser } from "../hooks/useAuth";

interface Props {
  user: AuthUser;
  children: ReactNode;
}

export function Protected({ user, children }: Props) {
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
