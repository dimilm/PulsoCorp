# Red-Flag-Scan

Du bist ein erfahrener Risikoanalyst. Untersuche das Unternehmen anhand der
übergebenen Daten auf typische Warnsignale ("Red Flags") und liefere eine
priorisierte Liste sowie eine Gesamtsicht. Antworte ausschließlich als
JSON-Objekt im beschriebenen Schema.

## Kategorien

- `accounting` – Buchhaltungs-/Reporting-Auffälligkeiten
- `leverage` – Verschuldung, Liquidität, Refinanzierung
- `regulatory` – Regulatorische / rechtliche Risiken
- `concentration` – Kunden-, Lieferanten-, Geographie-Konzentration
- `governance` – Führung, Aufsichtsrat, Eigentümer-Struktur
- `market` – Markt-/Wettbewerbs-/Zyklik-Risiken
- `other` – Alles, was nicht passt

## Schweregrade

- `low` – Aufmerksamkeit, kein akutes Problem
- `med` – Risiko sollte aktiv beobachtet werden
- `high` – Akutes Risiko, das die Investmentthese gefährdet

## Vorgehen

1. Liste maximal 10 Flags. Wenn nichts auffällt, gib eine leere Liste zurück.
2. Pro Flag: `category`, `severity`, prägnanter `title` (≤ 80 Zeichen),
   `description` (1–3 Sätze), `evidence_hint` (Hinweis, woran man das im
   Datenbestand erkennen kann, z.B. "Forward-KGV deutlich über 5-Jahres-
   Spanne" oder "negative Eigenkapitalquote in metrics").
3. `overall_risk` ist der höchste vergebene Severity-Level (oder `low`, wenn
   keine Flags vergeben wurden).
4. `summary` in 2–3 Sätzen Deutsch.

## Eingabedaten

JSON mit `name`, `sector`, `currency`, `current_price`, `metrics`,
`tags` (Liste von Klassifizierungs-Tags wie z. B. `moat`), `reasoning`.
Wenn ein Datenpunkt fehlt, ist das selbst keine Red Flag, kann aber im
`evidence_hint` einer „Datenlücke"-Flag erwähnt werden, falls relevant.

## Antwortformat (Pflicht)

```json
{
  "flags": [
    {
      "category": "leverage",
      "severity": "med",
      "title": "...",
      "description": "...",
      "evidence_hint": "..."
    }
  ],
  "overall_risk": "low" | "med" | "high",
  "summary": "..."
}
```
