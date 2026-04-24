# Anforderungen – Aktien-Tracker (Web-Anwendung)

Status: Entwurf v1.0
Quelle der Bestandsdaten: [Comp_List.csv](Comp_List.csv)
Vorlage / UI-Referenz: [Bild1.png](assets/c__Users_imd2si_Documents_2026_99_Cursor_14_CompanyTracker_Bild1.png)

---

## 1. Projektname & Zweck

**Projektname:** CompanyTracker (Arbeitstitel)

**Zweck:** Ablösung der bisherigen Excel-Liste (`Comp_List.csv`, ca. 100+ Aktien) durch eine moderne, browserbasierte Web-Anwendung. Die Anwendung pflegt eine Watchlist von Aktien (in Anlehnung an den Investment-Stil von F. Helmes), kennzeichnet Aktien mit besonders starkem **Burggraben** als eigenes Merkmal, aktualisiert Kurse und Kennzahlen täglich automatisch und unterstützt den Anwender bei Bewertungsentscheidungen mit Hilfe von KI.

**Wesentliche Verbesserungen gegenüber Excel:**

- Tagesaktuelle Kurse und Kennzahlen ohne manuelles Pflegen
- Visuelle Aufbereitung mit Filter / Sortierung / Suche
- KI-gestützte Bewertungsvorschläge (DCF, NAV, Burggraben)
- Mehrbenutzerfähig im lokalen Netz oder auf vServer

---

## 2. Zielgruppe & Nutzungsszenario

- **Nutzer:** Privatanleger (1–3 Personen im Haushalt / Bekanntenkreis)
- **Häufigkeit:** tägliche Kurzkontrolle (5–10 min), monatliche Tranchen-Käufe à 1.000 €
- **Hauptaufgaben:**
  1. Beobachten, welche Aktien aktuell günstig und qualitativ stark sind (Unterbewertung + Score + Burggraben)
  2. Erhalten und Prüfen von klaren BUY / RISK BUY-Empfehlungen inkl. Begründung
  3. Entscheiden, welche Tranche im Monat gekauft wird
  4. KI-Vorschläge zu Bewertung und Burggraben übernehmen, verwerfen oder manuell überschreiben
  

---

## 3. Anwendungstyp & Betrieb

| Aspekt | Festlegung |
|---|---|
| Anwendungstyp | Web-Anwendung (Browser) |
| Hosting | Lokales Heim- / Firmennetz (z. B. NAS, Heim-Server, Mini-PC) |
| Nutzer | 1–3, mit einfachem Login (Benutzername + Passwort) |
| Zugriff | Nur aus dem lokalen Netzwerk (kein Public-Internet-Zugriff im MVP) |
| Datenhaltung | Lokal (Datenbank auf dem Host), keine Cloud-Pflicht |
| Backup | Tägliches Backup der Datenbank auf separates Verzeichnis / Laufwerk |

---

## 4. Funktionale Anforderungen

### 4.0 Priorisierung (MVP vs. später)

| Funktionsblock | Priorität |
|---|---|
| Aktien-Stammdaten inkl. Burggraben-Flag | MVP |
| Live-Kurse + Kennzahlen + Watchlist-Filter | MVP |
| Empfehlungslogik BUY / RISK BUY inkl. Begründung | MVP |
| Dashboard mit Kaufkandidaten und Laufstatus | MVP |
| KI-gestützte Bewertung (Fundamental-Score, Burggraben, DCF/NAV) | MVP |
| Kauf-/Verkaufs-Historie | Später (nicht Teil MVP) |
| Push-/E-Mail-Benachrichtigungen | Später |
| Erweiterte Multi-Depot-/Mandanten-Funktion | Später |

### 4.1 Aktien-Stammdaten

- Anlegen / Bearbeiten / Löschen von Aktien
- Pflichtfelder: ISIN, Aktienname, Sektor, Währung
- Optional: Begründung (Freitext, mehrzeilig), externe Links (Yahoo Finance, finanzen.net, onvista)
- **Burggraben-Flag** (Ja/Nein) – kennzeichnet Aktien mit besonders starkem Wettbewerbsvorteil; in der Hauptliste als eigene Spalte sichtbar und filterbar
- Aktien werden in **einem** gemeinsamen Depot verwaltet (siehe 4.4)

### 4.2 Live-Kursabruf

- Tagesaktueller Kurs in Originalwährung
- Tagesänderung in % (Vortagesschlusskurs vs. aktueller / letzter Schlusskurs)
- Anzeige des Zeitpunkts der letzten Aktualisierung pro Aktie
- Fehlerhafte Abrufe werden markiert und im Lauflog protokolliert

### 4.3 Automatischer Abruf weiterer Kennzahlen

Pro Aktie sollen folgende Kennzahlen automatisch (sofern verfügbar) gezogen werden:

- KGV (aktuell, geschätzt für nächstes Jahr)
- Min / Max / Ø KGV der letzten Jahre (z. B. 5J)
- Dividendenrendite (aktuell und Ø über 5 Jahre)
- Analysten-Kursziel (1 Jahr, Median)
- Marktkapitalisierung
- Eigenkapitalquote, Verschuldungsgrad, Umsatzwachstum (für Fundamental-Analyse)

### 4.4 Depot-Verwaltung

- **Ein** gemeinsames Depot für alle Aktien
- Pro Aktie: Anzahl Tranchen (1 Tranche = 1.000 €)
- Vereinfachte MVP-Logik: investiertes Kapital je Aktie = Tranchen × 1.000 €
- Exakte Performance-Berechnung über Stückzahl / Einstiegspreis ist **nicht** Teil des MVP und wird als spätere Erweiterung geführt
- Optional: Auswertungen / Filter nach Burggraben-Flag (z. B. "Wie hoch ist der Anteil meiner Burggraben-Aktien am Gesamtdepot?")

### 4.5 Empfehlungslogik (BUY / RISK BUY)

- Manuelle Markierung pro Aktie: keine / `BUY` / `RISK BUY`
- KI-Vorschlag (siehe Abschnitt 6), den der Nutzer übernehmen oder verwerfen kann
- Empfehlungen werden farblich hervorgehoben (siehe Abschnitt 9)

### 4.6 KI-gestützte Bewertungs-Kennzahlen

Folgende Werte sollen mit Unterstützung der KI ermittelt / vorgeschlagen werden:

- **Fundamental-Score** (0–10)
- **DCF (Discounted Cashflow)**: geschätzter fairer Wert
- **NAV / NTA**: Plausibilisierung / Schätzung
- **Burggraben-Bewertung** (Freitext + Score)
- **BUY / RISK BUY-Vorschlag** mit Begründung

Details siehe Abschnitt 6.

### 4.7 Berechnete Felder

- Über-/Unterbewertung in % (aktueller Kurs vs. fairer Wert DCF)
- Über-/Unterbewertung in % (aktueller Kurs vs. fairer Wert NAV)
- Abstand zum Analysten-Kursziel in %
- Investiertes Kapital pro Aktie (Tranchen × 1.000 €)

### 4.8 Filter, Sortierung, Suche

- Filter nach: Sektor, Empfehlung (BUY / RISK BUY), Burggraben-Flag, Score-Bereich, Über-/Unterbewertung
- Volltextsuche nach Aktienname / ISIN
- Sortierung jeder Spalte aufsteigend / absteigend
- Speicherbare Filter-Presets (z. B. "Heutige Kaufkandidaten")

### 4.9 Externe Verlinkung

Pro Aktie ein-Klick-Links zu:

- Yahoo Finance (Chart, Analysten)
- finanzen.net (Kursziele)
- onvista (Chart, Fundamental, Kennzahlen)

### 4.10 Dashboard

Startseite zeigt auf einen Blick:

- Tagesgewinner / -verlierer (Top 5 je)
- Aktuelle Kaufkandidaten (Aktien mit BUY-Empfehlung **und** günstiger DCF/NAV-Bewertung)
- Depotübersicht (Gesamtwert, Tagesveränderung in % und €, Anteil Burggraben-Aktien)
- Status des letzten Auto-Update-Laufs (Uhrzeit, Erfolg / Fehler)

---

## 5. Scheduler / Automatisierung

| Aspekt | Anforderung |
|---|---|
| Lauf-Häufigkeit | Täglich, 1× pro Tag |
| Lauf-Uhrzeit | Konfigurierbar in den Einstellungen (Default: 22:30 lokale Zeit, nach US-Börsenschluss) |
| Wochenende / Feiertage | Optional abschaltbar (kein Lauf an Sa/So und an Hauptbörsen-Feiertagen) |
| Manueller Trigger | "Jetzt aktualisieren"-Button (gesamt **und** einzelne Aktie) |
| Lauf-Logging | Jeder Lauf wird protokolliert: Startzeit, Dauer, Anzahl Aktien, Erfolge, Fehler, Fehlermeldungen |
| Anzeige in der UI | Letzter erfolgreicher Lauf + letzter Fehler-Lauf jederzeit sichtbar |
| Fehlerverhalten | Einzelner Aktien-Fehler stoppt Gesamtlauf nicht; Aktien mit Fehler werden markiert |
| Retry | Bis zu 3 Wiederholungen pro Aktie mit kurzer Wartezeit |
| Parallel-/Mehrinstanz-Schutz | Pro geplanter Lauf darf nur **eine** Job-Instanz aktiv sein (DB-basierter Job-Lock) |

---

## 6. KI-Integration

### 6.1 Provider

Der KI-Provider ist **austauschbar** und in den Einstellungen konfigurierbar:

- OpenAI (z. B. GPT-4 / GPT-5)
- Anthropic Claude
- Lokales LLM (z. B. Ollama, LM Studio)
- Weitere via OpenAI-kompatibler Schnittstelle

Konfigurierbar pro Provider: Endpoint-URL, API-Key, Modellname, Temperatur, max. Tokens.
**API-Keys werden verschlüsselt** in der Datenbank gespeichert.

### 6.2 Anwendungsfälle der KI

| Anwendungsfall | Eingabe | Ausgabe |
|---|---|---|
| Burggraben-Bewertung | Aktienname, Sektor, Begründungstext, Marktstellung | Score 0–10 + Begründung |
| Fundamental-Score | Aktuelle Kennzahlen (KGV, EK-Quote, Wachstum, etc.) | Score 0–10 + Begründung |
| DCF-Schätzung | Cashflow-Historie, Wachstumsannahmen, Diskontsatz | Geschätzter fairer Wert + Annahmen |
| NAV / NTA-Plausibilisierung | Bilanzdaten | Geschätzter NAV pro Aktie |
| BUY / RISK BUY-Vorschlag | Alle obigen Werte + aktueller Kurs | Empfehlung + Begründung + Risikohinweis |
| News-Zusammenfassung | Aktuelle News-Headlines zur Aktie | Kurzfassung in Deutsch (max. 5 Sätze) |
| Risikohinweise | Aktien-Profil | Aufzählung der wichtigsten Risiken |

### 6.3 Bedienung

- KI-Ergebnisse sind **Vorschläge**: Nutzer kann **Übernehmen** / **Verwerfen** / **Überschreiben**
- Pro Feld ist sichtbar, woher der Wert stammt (manuell / live / berechnet / KI)
- Manuell überschriebene Werte werden vom Auto-Update **nicht** überschrieben (Sperre / Lock-Symbol)

### 6.4 Caching & Kostenkontrolle

- KI-Antworten werden gecached
- Standard-Refresh: monatlich (DCF, NAV, Burggraben ändern sich nicht täglich)
- Konfigurierbar: täglich / wöchentlich / monatlich / nur manuell
- Anzeige der geschätzten Kosten pro Lauf (Token-Verbrauch × Provider-Preis)

---

## 7. Nicht-funktionale Anforderungen

| Bereich | Anforderung |
|---|---|
| Performance | Hauptliste mit 100+ Aktien lädt in < 2 s |
| Verfügbarkeit | Anwendung läuft als Hintergrunddienst auf Heim-Server / NAS / PC |
| Sicherheit | Login-Pflicht, Passwörter gehasht (z. B. bcrypt/argon2), API-Keys verschlüsselt, Session über HttpOnly-Cookie + CSRF-Schutz |
| Backup | Tägliches automatisches Backup der Datenbank, mind. 14 Tage rollierend |
| Sprache | Deutsch primär, Englisch als optionale UI-Sprache |
| Browser-Support | Aktuelle Versionen Chrome, Edge, Firefox |
| Responsiveness | Bedienbar auf Tablet (Querformat), Desktop primär |
| Logging | Anwendungs-Log persistent, einsehbar für Admin-Nutzer |
| Datenexport | CSV-Export der Watchlist jederzeit möglich |

---

## 8. Datenmodell (abgeleitet aus `Comp_List.csv`)

Quellen-Legende: **M** = manuell, **L** = live (API), **B** = berechnet, **KI** = KI-generiert

### 8.1 Tabelle Aktie (Stammdaten)

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| ISIN | String (12) | M | Eindeutige ID der Aktie |
| Name | String | M | Anzeigename |
| Sektor | String | M | Branche / Sektor |
| Währung | String (3) | M | EUR / USD / etc. |
| Burggraben | Boolean | M | Flag: starker Wettbewerbsvorteil ja/nein |
| Begründung | Text | M | Warum interessant (Burggraben-Story) |
| Link Yahoo | URL | M | externer Link |
| Link finanzen.net | URL | M | externer Link |
| Link onvista (Chart) | URL | M | externer Link |
| Link onvista (Fundamental) | URL | M | externer Link |

### 8.2 Tabelle Kursdaten (1× pro Aktie, jeweils aktualisiert)

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| Aktueller Kurs | Decimal | L | Letzter verfügbarer Kurs |
| Tagesänderung % | Decimal | L | Vortagesschluss → aktuell |
| Letzte Aktualisierung | Timestamp | L | Wann zuletzt erfolgreich gezogen |
| Status letzter Abruf | Enum | L | OK / Fehler |

### 8.3 Tabelle Kennzahlen

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| KGVe | Decimal | L | Geschätztes KGV |
| KGV Min (5J) | Decimal | L | |
| KGV Max (5J) | Decimal | L | |
| KGV Ø (5J) | Decimal | L | |
| Dividende aktuell % | Decimal | L | |
| Dividende Ø % | Decimal | L | |
| Analysten-Kursziel 1J | Decimal | L | Median |
| Marktkapitalisierung | Decimal | L | |
| EK-Quote % | Decimal | L | |
| Umsatzwachstum % | Decimal | L | |

### 8.4 Tabelle Bewertung (KI / manuell)

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| Fundamental-Score | Integer (0–10) | KI / M | Score |
| Burggraben-Score | Integer (0–10) | KI / M | Score |
| Burggraben-Text | Text | KI / M | Begründung |
| Fairer Wert DCF | Decimal | KI / M | |
| Fairer Wert NAV / NTA | Decimal | KI / M | |
| Empfehlung | Enum | KI / M | keine / BUY / RISK BUY |
| Empfehlungs-Begründung | Text | KI / M | |
| Risikohinweise | Text | KI | |
| Quelle des Werts (pro Feld) | Enum | System | M / L / B / KI |
| Manuell gesperrt? | Boolean | M | Wenn true: Auto-Update überschreibt nicht |

### 8.5 Tabelle Berechnete Felder

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| Über-/Unterbewertung DCF % | Decimal | B | (Kurs − DCF) / DCF |
| Über-/Unterbewertung NAV % | Decimal | B | (Kurs − NAV) / NAV |
| Abstand Analysten-Kursziel % | Decimal | B | (Kursziel − Kurs) / Kurs |
| Investiertes Kapital (EUR) | Decimal | B | Tranchen × 1.000 € (vereinfachte MVP-Logik) |

### 8.6 Tabelle Depot-Position

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| ISIN | FK | – | Verweis auf Aktie (eindeutig, da nur ein Depot) |
| Anzahl Tranchen | Integer | M | 1 Tranche = 1.000 € |

### 8.7 Tabelle Lauf-Log

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| Startzeit | Timestamp | System | |
| Dauer (s) | Integer | System | |
| Aktien gesamt | Integer | System | |
| Aktien Erfolg | Integer | System | |
| Aktien Fehler | Integer | System | |
| Fehler-Details | Text | System | JSON / Liste |

### 8.8 Tabelle Benutzer

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| Benutzername | String | M | |
| Passwort-Hash | String | System | bcrypt/argon2 |
| Rolle | Enum | M | Admin / Nutzer |

### 8.9 Tabelle Einstellungen

| Feld | Typ | Quelle | Beschreibung |
|---|---|---|---|
| Update-Uhrzeit | Time | M | Default 22:30 |
| Update an Wochenenden | Boolean | M | Default false |
| KI-Provider | Enum | M | OpenAI / Anthropic / Local |
| KI-Endpoint | URL | M | |
| KI-API-Key | String (verschlüsselt) | M | |
| KI-Modell | String | M | |
| KI-Refresh-Intervall | Enum | M | Täglich / Wöchentlich / Monatlich / Manuell |

---

## 9. Visualisierungsregeln (Ampelsystem)

Übernommen aus dem Excel-Vorbild ([Bild1.png](assets/c__Users_imd2si_Documents_2026_99_Cursor_14_CompanyTracker_Bild1.png)):

| Spalte | Bedingung | Farbe |
|---|---|---|
| Tagesänderung % | > +4 % | Grün |
| Tagesänderung % | < −4 % | Rot |
| DCF (Über-/Unterbewertung) | Kurs günstiger als DCF | Blau |
| NAV / NTA | Kurs günstiger als NAV | Blau |
| Analysten-Kursziel | Kursziel > 10 % über Kurs | Türkis |
| Dividendenrendite | > 4 % | Türkis |
| Empfehlung | BUY | Grün |
| Empfehlung | RISK BUY | Lila |
| Fundamental-Score | ≥ 8 | Grün-Akzent |
| Fundamental-Score | ≤ 3 | Rot-Akzent |

Alle Schwellwerte sollen in den Einstellungen anpassbar sein.

---

## 10. Datenimport

- Einmaliger Initial-Import aus [Comp_List.csv](Comp_List.csv)
- Mapping der CSV-Spalten auf das Datenmodell (ISIN, Name, Sektor, Währung, Burggraben-Flag, Tranchen, Begründung, Links). Hinweis: Aktien, die in der CSV im "Burggraben-Depot" Tranchen haben, werden mit gesetztem Burggraben-Flag importiert; die Tranchenzahlen aus beiden Excel-Depots werden zu einem gemeinsamen Tranchen-Wert addiert
- Import-Reportausgabe: Anzahl importierter / übersprungener Zeilen, Fehlerliste
- Nach dem Import: erster Live-Abruf zur Befüllung von Kursen und Kennzahlen
- Mehrfach-Import möglich (Update statt Duplikate, Schlüssel = ISIN)

---

## 11. Externe Datenquellen

Mögliche Quellen (Auswahl im Lauf der Umsetzung):

- **Kursdaten / Kennzahlen:** Yahoo Finance (z. B. via `yfinance`), Alpha Vantage, finanzen.net (Scraping), onvista (Scraping)
- **News:** Yahoo Finance News, Google News RSS
- **KI:** OpenAI, Anthropic, lokales LLM via Ollama / LM Studio

Hinweise:

- Rate-Limits beachten (insb. kostenfreie APIs)
- Fallback-Strategie: bei Ausfall einer Quelle automatisch auf eine zweite umschalten
- Quelle pro Kennzahl konfigurierbar

---

## 12. Offene Punkte / spätere Entscheidungen

| Thema | Offen |
|---|---|
| Backend-Sprache | Python (FastAPI / Django) vs. Node.js vs. .NET – noch nicht festgelegt |
| Frontend | React / Vue / Svelte / serverseitig gerendert (Streamlit, etc.) |
| Datenbank | SQLite (einfach, lokal) vs. PostgreSQL |
| Konkrete Kursdaten-API | Yahoo Finance bevorzugt, Alternativen prüfen |
| Konkreter KI-Provider | Wird über Einstellungen austauschbar; Default noch zu wählen |
| Hosting-Hardware | Heim-Server / NAS / Mini-PC – konkretes Gerät zu klären |
| Deployment | Docker-Container vs. nativer Dienst |
| Notifications | Optional: Mail / Push bei Auffälligkeiten (z. B. > 4 % Kursabfall) |
| Mehr-Währungs-Anzeige | Umrechnung in EUR über tägliche FX-Rate |

---

## 13. Glossar

- **Burggraben (Moat):** Strukturelle Wettbewerbsvorteile eines Unternehmens (Marke, Patente, Netzwerkeffekte, Skalenvorteile, Wechselkosten), die langfristig hohe Margen sichern. In dieser Anwendung als Boolean-Flag pro Aktie hinterlegt.
- **Tranche:** Hier eine fest definierte Investitionseinheit von 1.000 €.
- **DCF (Discounted Cashflow):** Bewertungsverfahren auf Basis abdiskontierter zukünftiger Cashflows zur Ermittlung des fairen Werts.
- **NAV / NTA:** Net Asset Value / Net Tangible Assets – substanzbasierter fairer Wert.
- **KGV / KGVe:** Kurs-Gewinn-Verhältnis (e = geschätzt für die Zukunft).
- **Fundamental-Score:** Hier eine ganzzahlige Bewertung (0–10) der fundamentalen Qualität eines Unternehmens.
- **BUY / RISK BUY:** Kauf-Empfehlungen; "RISK BUY" weist auf erhöhtes Risiko hin.
- **KI-Provider:** Anbieter eines Sprachmodells (LLM) – austauschbar (OpenAI, Anthropic, lokales LLM).

---

*Ende des Dokuments.*
