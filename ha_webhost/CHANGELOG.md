# Changelog

## 0.1.8

- Neu: Einstellung "Öffentliche Basis-URL" im Panel (z.B. für Tailscale
  Funnel). Wenn gesetzt, wird bei jeder Site zusätzlich zum internen
  HA-Link ("🏠") ein externer Link ("🌐") angezeigt und ist direkt
  anklickbar/kopierbar. Persistiert in `/data/settings.json`.

## 0.1.7

- Neu: Zweiter, strikt getrennter Caddy-Listener auf Port 8090 - liefert
  ausschließlich `/sites/<name>/*` aus, niemals Admin-UI oder `/api/*`.
  Gedacht für öffentliche Freigabe (z.B. via Tailscale Funnel), ohne
  dabei das Admin-Panel zu exponieren.
- Sicherheitsfix während der Entwicklung gefunden und behoben: Ein
  Caddy-Server-Block ohne jede Route antwortet mit `200 leer`, nicht
  automatisch mit `404` - der ursprüngliche Entwurf hätte dadurch
  versehentlich Admin-UI/API auch auf Port 8090 exponiert. Jetzt
  expliziter `respond 404`-Catch-all, verifiziert dass Admin-UI/API auf
  8090 durchgehend 404 liefern, während Sites korrekt ausgeliefert werden.
- Doku: Anleitung für Tailscale Funnel auf Port 8090 ergänzt (klassischer
  `tailscale serve`/`funnel`-Mechanismus, unabhängig von der neueren
  Services-Funktion, um bestehende Freigaben nicht zu stören).

## 0.1.6

- Neu: "🔄 Update"-Button für Upload-Sites — erneutes Hochladen einer ZIP
  unter demselben Namen ersetzt jetzt den Inhalt (statt mit `409` zu
  scheitern), analog zu "Redeploy" bei Git-Sites. `id`/`created_at`
  bleiben erhalten, `updated_at`/`last_deploy_at` werden aktualisiert.
  Ein Upload gegen eine bestehende Site anderen Typs (z.B. Git) bleibt
  weiterhin ein klarer `409`-Konflikt.

## 0.1.5

- Sicherheitsverbesserung: Git-Access-Token wird jetzt verschlüsselt in
  der SQLite-DB gespeichert (Fernet, Schlüssel unter `/data/secret.key`,
  0600, beim ersten Start generiert). Verifiziert per direktem
  SQLite-Zugriff, dass nur noch Ciphertext in der DB steht, und dass
  Redeploy den Token korrekt entschlüsselt und weiterverwendet.
- Build auf amd64 (Zielarchitektur i3-Notebook) explizit getestet, da
  `cryptography` ein kompiliertes Paket ist – Wheel-Installation ohne
  Kompilierung bestätigt (~12s, kein Rust/Build-Toolchain nötig).

## 0.1.4

- Neu: "📦 Alle Sites sichern"-Button im Panel — lädt alle aktiven Sites
  gebündelt als ein ZIP herunter (`.git`-Verzeichnisse ausgeschlossen).
- Sicherheitsfix: Git-Access-Token wurde beim Klonen in die Remote-URL
  eingebettet und landete dadurch dauerhaft im Klartext in `.git/config`
  der jeweiligen Site (lesbar über den Datei-Manager, hätte auch in
  Backups mit exportiert). Token wird jetzt nur noch per
  `-c http.extraHeader=...` für den einzelnen Git-Aufruf übergeben, nie
  mehr persistiert.
- Doku-Korrektur: "Update liefert alten Code aus" war **kein**
  Supervisor-Bug, sondern der Workbox-Service-Worker der HA-Frontend-PWA,
  der `static/`-Assets im Cache Storage vorhält (ignoriert dabei sogar
  Cache-Busting-Query-Parameter). Echte Lösung (Cache-Eintrag löschen)
  dokumentiert, Repository-Repair-Endpunkt als Fallback für echte
  Build-Probleme belassen.

## 0.1.3

- Sicherheitsfix: Datei-/Ordnernamen im Datei-Manager wurden ungefiltert
  als HTML gerendert (gespeicherte XSS). Ein Git-Repo oder eine ZIP-Datei
  mit einem bösartig benannten File (z.B. `<img src=x onerror=...>`)
  hätte beim Öffnen des Datei-Managers Skriptcode im Admin-Panel
  ausgeführt. Jetzt konsequent per `escapeHtml()` escaped, verifiziert
  mit echtem XSS-Payload-Dateinamen.

## 0.1.2

- Sicherheitsfix: `GET /api/sites` und alle anderen Site-Endpunkte gaben den
  Git-Access-Token im Klartext zurück. Neues `SitePublic`-Response-Model
  ohne `git_token`-Feld eingeführt - der Token wird jetzt nie mehr über die
  API ausgegeben.
- Neu: Datei-Manager-UI im Web-Panel (Ordner navigieren, Dateien anlegen,
  hochladen, im Browser bearbeiten, löschen) - nutzt die bereits
  vorhandene `/api/files/...`-API.
- Roadmap angepasst: PHP-Hosting (Phase 2) vor Python-Hosting (Phase 3)
  vorgezogen.

## 0.1.1

- Fix: Ingress-Root-Aufruf lieferte `404 Not Found` statt der UI, weil Home
  Assistant Ingress einen doppelten Trailing-Slash an die Basis-URL anhängt
  (`.../<token>//`). Explizites `ingress_entry: /` aus `config.yaml`
  entfernt (Ursache) und zusätzlich `uri replace // / 1` in der Caddyfile
  ergänzt (Absicherung gegen ähnliche Fälle).
- Backend generiert die Caddyfile jetzt bei jedem Start neu aus dem
  DB-Stand, damit Konfig-Fixes wie dieser sofort greifen, auch ohne dass
  vorher eine Site an-/abgelegt wird.

## 0.1.0

- Erste MVP-Version: statisches Website-Hosting via ZIP-Upload und
  Git-Deployment (GitHub/GitLab/Gitea), Caddy-Reverse-Proxy mit
  SPA-Fallback, einfacher Datei-Browser, HA-Ingress-Integration.
