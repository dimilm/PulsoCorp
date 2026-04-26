import { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

interface Props {
  children: ReactNode;
}

export function Protected({ children }: Props) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
