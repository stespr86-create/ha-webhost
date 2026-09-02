# Changelog

## 0.1.4

- Neu: "📦 Alle Sites sichern"-Button im Panel — lädt alle aktiven Sites
  gebündelt als ein ZIP herunter (`.git`-Verzeichnisse ausgeschlossen).
- Sicherheitsfix: Git-Access-Token wurde beim Klonen in die Remote-URL
  eingebettet und landete dadurch dauerhaft im Klartext in `.git/config`
  der jeweiligen Site (lesbar über den Datei-Manager, hätte auch in
  Backups mit exportiert). Token wird jetzt nur noch per
  `-c http.extraHeader=...` für den einzelnen Git-Aufruf übergeben, nie
  mehr persistiert.
- Doku: Bekannte Lösung für "Update zeigt neue Version, liefert aber
  alten Code" ohne Datenverlust (Supervisor-Repository-Repair-Endpunkt)
  ergänzt.

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
