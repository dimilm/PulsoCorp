interface Props {
  label?: string;
}

export function Spinner({ label }: Props) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      {label && <span className="loading-label">{label}</span>}
    </div>
  );
}
