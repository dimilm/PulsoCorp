const PALETTE_SIZE = 8;

function hashString(input: string): number {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function tagColorClass(name: string): string {
  const normalized = (name ?? "").trim().toLowerCase();
  if (!normalized) return "tag-c0";
  return `tag-c${hashString(normalized) % PALETTE_SIZE}`;
}
