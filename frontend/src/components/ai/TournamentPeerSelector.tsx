import { useState } from "react";

import { useStockPeers } from "../../hooks/useStockQueries";

interface Props {
  isin: string;
  onChange: (peers: string[]) => void;
}

export function TournamentPeerSelector({ isin, onChange }: Props) {
  const peersQuery = useStockPeers(isin, 7);
  const peers = peersQuery.data ?? [];
  const [selected, setSelected] = useState<Set<string>>(new Set());

  function toggle(peerIsin: string) {
    const next = new Set(selected);
    if (next.has(peerIsin)) next.delete(peerIsin);
    else next.add(peerIsin);
    setSelected(next);
    onChange(Array.from(next));
  }

  if (peersQuery.isLoading) {
    return <span className="ai-peer-empty">Lade Vorschläge…</span>;
  }
  if (peers.length === 0) {
    return (
      <span className="ai-peer-empty">
        Keine Peers gefunden — Agent nutzt automatisch ähnliche Sektor-Aktien.
      </span>
    );
  }

  return (
    <div className="ai-peer-selector">
      <span className="ai-peer-label">Peers für das Turnier (optional, sonst auto):</span>
      <div className="ai-peer-list">
        {peers.map((p) => (
          <label key={p.isin} className="ai-peer-chip">
            <input
              type="checkbox"
              checked={selected.has(p.isin)}
              onChange={() => toggle(p.isin)}
            />
            {p.name}
            <span className="ai-peer-chip-isin">{p.isin}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
