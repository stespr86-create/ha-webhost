# HA WebHost – Dokumentation

## Was macht dieses Add-on (v0.1.0 / MVP)

HA WebHost hostet **statische Websites** (HTML/CSS/JS sowie fertige
React-/Vue-/Angular-Builds) direkt aus Home Assistant heraus. Jede Site ist
unter `/sites/<name>/` erreichbar, verwaltet über eine kleine Weboberfläche
im HA-Ingress-Panel.

### Enthalten

- ZIP-Upload mit automatischem, sicherem Entpacken (Zip-Slip-Schutz)
- Deployment aus öffentlichen und privaten Git-Repositories (GitHub/GitLab/
  Gitea, per HTTPS-URL + optionalem Access Token)
- Redeploy per Knopfdruck (git pull)
- Einfacher Datei-Browser/-Editor über die API (`/api/files/...`)
- Manuelles Backup aller Sites als ein ZIP-Download ("📦 Alle Sites
  sichern"-Button im Panel, `.git`-Verzeichnisse werden ausgeschlossen)
- Reverse Proxy (Caddy) inkl. SPA-Fallback (`try_files … /index.html`)
- Läuft komplett ohne Docker-Socket-Zugriff → kein erhöhtes Sicherheitsrisiko
  für den Host

### Bewusst NICHT enthalten (siehe Roadmap)

- PHP-/Python-Hosting mit eigenem Laufzeit-Container pro App
- Datenbank-Verwaltung (MariaDB/PostgreSQL)
- Automatische Backups nach Zeitplan, Monitoring, Live-Log-Viewer
- Mehrere gleichzeitige Admin-Benutzer (Auth läuft komplett über HA)

Grund: Auf typischer HA-Hardware (insbesondere < 8 GB RAM) sprengt der volle
Funktionsumfang aus dem ursprünglichen Konzept die verfügbaren Ressourcen,
und Docker-Socket-Zugriff für App-Container ist ein erhebliches
Sicherheitsrisiko (praktisch Root-Zugriff auf den Host). Diese Punkte kommen
erst in späteren Phasen, dann bewusst und einzeln abgesichert.

## Bekannte Einschränkung: Sub-Path-Routing

Sites werden unter einem **Unterpfad** (`/sites/<name>/`) ausgeliefert, nicht
unter einer eigenen Domain/Subdomain. Viele Frontend-Build-Tools erzeugen
standardmäßig **absolute** Pfade ab `/`, was unter einem Unterpfad zu
kaputten CSS-/JS-/API-Links führt.

**Vor dem Build unbedingt den Base-Path relativ setzen:**

| Tool | Einstellung |
|---|---|
| Vite | `base: './'` in `vite.config.js` |
| Create React App | `"homepage": "."` in `package.json` |
| Vue CLI | `publicPath: './'` in `vue.config.js` |
| Angular CLI | `ng build --base-href ./` |

Serverseitige Frameworks (WordPress, Laravel, Nextcloud, Flask/FastAPI/
Django) sind **nicht** Teil dieses MVP, da sie eigene Laufzeitumgebungen und
i.d.R. eigene DB-Anbindung brauchen – siehe Roadmap.

## Installation als lokales Add-on-Repository

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ →
   Repositories**.
2. Repository-URL eures Git-Repositories eintragen (dieses Projekt muss dazu
   auf GitHub/GitLab/Gitea liegen, `repository.yaml` liegt bereits im
   Projekt-Root).
3. "HA WebHost" erscheint im Store → installieren → starten.
4. Panel "WebHost" erscheint in der HA-Sidebar (Ingress).

Alternativ für lokale Entwicklung ganz ohne Git-Hosting: Projektordner nach
`/addons/ha_webhost` auf dem HA-Host kopieren (z.B. via Samba-/SSH-Add-on) –
lokale Add-ons werden vom Supervisor automatisch erkannt.

## ⚠️ Update liefert manchmal alten Code aus – Lösung ohne Datenverlust

Beobachtetes Problem: Nach einem Push + Update/Rebuild zeigt HA zwar
korrekt die neue Version und den neuen Changelog-Text an, der tatsächlich
laufende Container liefert aber weiterhin den **alten** Code aus. Ursache
ist vermutlich ein nicht sauber aktualisierter lokaler Git-Checkout des
Repositories auf dem Supervisor-Host.

**Lösung (kein Datenverlust, `/data` bleibt unangetastet):** Supervisor
bietet dafür einen dedizierten Repository-Repair-Endpunkt, der einen
frischen Git-Checkout erzwingt, ohne das Add-on zu deinstallieren:

```js
// Im Browser auf einer beliebigen HA-Seite in der Konsole ausfuehren
// (oder ueber javascript_exec einer Browser-Automatisierung):
const ha = document.querySelector("home-assistant");
await ha.hass.callWS({
  type: "supervisor/api",
  endpoint: "/store/repositories/38ef203b/repair",  // 38ef203b = Repo-Slug
  method: "post",
});
// Danach normal ueber die UI oder per WS "update" auf das Add-on anwenden.
```

Quelle/Hintergrund: `Repository.reset()` in
[supervisor/store/repository.py](https://github.com/home-assistant/supervisor/blob/main/supervisor/store/repository.py),
aufgerufen über `POST /store/repositories/{repository}/repair` in
[supervisor/api/store.py](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/store.py) -
siehe auch [DeepWiki: Repository Management](https://deepwiki.com/home-assistant/supervisor/4.1-repository-management).
Der Repo-Slug steht in den Add-on-Infos (`repository`-Feld) oder in der
Repository-Liste (`GET /store/repositories`).

**Falls das nicht hilft:** Deinstallieren + Neuinstallieren erzwingt
garantiert einen kompletten Neuklon, **löscht dabei aber `/data` restlos**
(getestet, kein automatischer Datenerhalt bei diesem Setup) – vorher
unbedingt über den **"📦 Alle Sites sichern"**-Button im Panel ein Backup
ziehen (siehe unten), sofern die Inhalte nicht ohnehin per Git deployt und
damit extern gesichert sind.

## Sicherheitshinweise

- Der Git-Access-Token wird derzeit **unverschlüsselt** in der SQLite-DB
  (`/data/webhost.db`) gespeichert. `/data` ist nur für das Add-on selbst
  und Root auf dem Host lesbar – für ein Einzelnutzer-Setup akzeptabel,
  für produktiven/mehrbenutzer Einsatz wäre Verschlüsselung (z.B. Fernet mit
  Schlüssel aus HA Supervisor Secrets) ein sinnvoller nächster Schritt.
  Über die API wird der Token nie zurückgegeben (`SitePublic`-Response-Model
  ohne `git_token`-Feld) – auch nicht an den authentifizierten Admin selbst.
  Der Token wird beim Klonen/Pullen per `-c http.extraHeader=...` nur für
  den jeweiligen Git-Aufruf übergeben und landet dadurch **nicht** in
  `.git/config` der Site (wichtig auch fürs Backup, da sonst jeder Export
  den Token mit hätte).
- Datei-/Ordnernamen werden im Datei-Manager konsequent escaped
  (`escapeHtml()` im Frontend) – verhindert gespeicherte XSS über
  bösartig benannte Dateien in Uploads oder Git-Repos.
- Der optionale Port 8000 (siehe `config.yaml` → `ports`) veröffentlicht
  gehostete Sites **ohne** HA-Login direkt im Netzwerk, falls aktiviert.
  Nur aktivieren, wenn das gewünscht ist.
- Alle Datei-Operationen (Upload, ZIP-Entpacken, Datei-Browser) sind gegen
  Path-Traversal und Zip-Slip abgesichert (`core/security.py`).

## Roadmap (spätere Phasen)

Reihenfolge auf Wunsch angepasst: PHP-Hosting vorgezogen, Python-Hosting
zurückgestellt. Beide brauchen aber gleichermaßen einen eigenen
Laufzeit-Container pro App und damit `docker_api: true` (siehe
Sicherheitshinweis oben) – das Vorziehen ändert nichts an diesem Risiko,
nur an der Reihenfolge, in der es angegangen wird.

1. **Phase 2**: PHP-Hosting (Apache/Nginx + PHP-FPM) über je einen eigenen
   Container pro App, SQLite-Datenbank-Verwaltung pro App – erfordert
   `docker_api: true` im Add-on, wird als klar gekennzeichnete, optionale
   Erweiterung mit eigener Bedrohungsanalyse eingeführt.
2. **Phase 3**: Python-App-Hosting (Flask/FastAPI/Django) über je einen
   eigenen Container pro App – gleiche Architektur/Risiko wie Phase 2, nur
   für eine andere Laufzeitumgebung.
3. **Phase 4**: MariaDB/PostgreSQL-Provisioning, automatische
   Backup-Zeitpläne, Monitoring (CPU/RAM/Storage pro App), Live-Log-Viewer.
