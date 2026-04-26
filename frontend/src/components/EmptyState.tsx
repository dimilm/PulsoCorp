import { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  variant?: "card" | "inline";
}

// Lightweight empty-state primitive. Used wherever a table/list/section has
// nothing to show so we replace the silent gap with a clear next step.
//
//   <EmptyState
//     title="Noch keine Werte"
//     description="…"
//     action={<button>Hinzufügen</button>}
//   />
export function EmptyState({
  icon,
  title,
  description,
  action,
  variant = "card",
}: EmptyStateProps) {
  return (
    <div className={`empty-state empty-state-${variant}`} role="status">
      {icon && <div className="empty-state-icon" aria-hidden="true">{icon}</div>}
      <div className="empty-state-title">{title}</div>
      {description && <div className="empty-state-description">{description}</div>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}

export default EmptyState;
