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
- Redeploy per Knopfdruck (git pull bei Git-Sites, erneuter ZIP-Upload
  unter demselben Namen bei Upload-Sites – "🔄 Update"-Button)
- Einfacher Datei-Browser/-Editor über die API (`/api/files/...`)
- Manuelles Backup aller Sites als ein ZIP-Download ("📦 Alle Sites
  sichern"-Button im Panel, `.git`-Verzeichnisse werden ausgeschlossen)
- Zwei getrennte Zugriffswege: Port 8000 (Ingress, Admin-UI + API + Sites,
  HA-Login nötig) und Port 8090 (**nur** `/sites/<name>/*`, kein
  Admin-Zugriff - für öffentliche Freigabe gedacht, siehe unten)
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

## Öffentliche Erreichbarkeit über Tailscale Funnel

Sites lassen sich über Port 8090 öffentlich freigeben, **ohne** das
Admin-Panel mit zu exponieren (siehe oben, strikt getrennter Caddy-Listener,
nur `/sites/<name>/*`, sonst `404`).

**Wichtig, falls bereits andere Dienste über Tailscale freigegeben sind**
(z.B. über die neuere "Services"/`svc:name`-Funktion): Das hier beschriebene
Vorgehen nutzt bewusst den **klassischen, seit Jahren stabilen**
Funnel-Mechanismus direkt auf dem Geräte-Hostnamen (`tailscale serve` +
`tailscale funnel <port> on`), nicht die neuere Beta-"Services"-Funktion –
beide Mechanismen laufen unabhängig nebeneinander und beeinflussen sich
nicht, solange unterschiedliche Ports verwendet werden.

**Voraussetzung:** Die ACL-Policy des Tailnets muss Funnel bereits erlauben
(`"nodeAttrs": [{"target": ["autogroup:member"], "attr": ["funnel"]}]` oder
äquivalent für das jeweilige Gerät) – ohne das schlägt `tailscale funnel`
mit einer Fehlermeldung fehl. In den meisten bestehenden Setups, die schon
einen anderen Dienst per Funnel freigeben, ist das bereits der Fall.

**Einrichtung** (auf dem HA-Host, z.B. über das "Advanced SSH & Web
Terminal"-Add-on):

```bash
# 1. Lokalen Port 8090 als HTTPS-Ziel auf Port 8443 konfigurieren
#    (443 bewusst vermieden, falls dort schon ein anderer Dienst liegt)
tailscale serve --bg --https=8443 http://127.0.0.1:8090

# 2. Oeffentlich schalten
tailscale funnel 8443 on

# Status pruefen
tailscale funnel status
```

Danach sind alle aktiven Sites erreichbar unter:

```
https://<euer-tailscale-hostname>:8443/sites/<name>/
```

(z.B. `https://homeassistant.tailf85481.ts.net:8443/sites/gresu-feuerwehrmann/`)

**Wieder deaktivieren:**

```bash
tailscale funnel 8443 off
```

**Sicherheitshinweis:** Sobald Funnel aktiv ist, ist Port 8090 (und damit
alle aktiven Sites) für **jeden im Internet** erreichbar, ohne HA-Login.
Nur Sites deployen, die tatsächlich öffentlich sein sollen. Das Admin-Panel
selbst bleibt davon unberührt (weiterhin nur über HA-Ingress erreichbar).

## ⚠️ "Update zeigt neue Version, UI bleibt trotzdem alt" – eigentliche Ursache

**Korrigiert:** Frühere Versionen dieser Doku vermuteten hier einen
Supervisor-Bug (stale Git-Checkout beim Rebuild). Das war eine
**Fehldiagnose**. Die tatsächliche Ursache: Die Home-Assistant-Frontend-PWA
registriert einen **Workbox-Service-Worker**, der `static/`-Anfragen
(also `app.js`/`style.css` des Add-ons) im `workbox-runtime-...`-Cache
Storage ablegt und dabei die Query-String-Parameter ignoriert - normales
`fetch(url, {cache: "no-store"})` und selbst Cache-Busting per
`?v=<timestamp>` greifen dagegen **nicht**, da der Service Worker der
Anfrage vorgelagert ist und sie unabhängig von den Fetch-Cache-Optionen
aus dem eigenen Cache Storage bedient. Ein geänderter Ingress-Token (z.B.
durch Deinstallieren/Neuinstallieren) "löst" das Problem nur scheinbar,
weil dadurch zufällig eine neue, noch nicht gecachte URL entsteht - der
Supervisor-Build war die ganze Zeit korrekt.

**Echte Lösung (kein Deinstallieren nötig, kein Datenverlust):** Nach
einem Update den Service-Worker-Cache für die Add-on-Assets leeren. Im
Browser auf einer beliebigen HA-Seite in der Konsole ausführen (oder per
`javascript_exec` einer Browser-Automatisierung):

```js
const cache = await caches.open("workbox-runtime-https://<eure-ha-domain>/");
const requests = await cache.keys();
for (const req of requests) {
  if (req.url.includes("static/")) await cache.delete(req);
}
```

Alternativ reicht oft auch ein normaler Hard-Reload (Cmd/Ctrl+Shift+R) im
Browser oder ein Schließen/Neuöffnen des Panels nach ein paar Minuten,
da Workbox Runtime-Caches i.d.R. irgendwann von selbst revalidieren.

**Falls trotzdem nichts hilft** (echter Build-Fehler, nicht nur Anzeige):
Supervisor bietet einen Repository-Repair-Endpunkt
(`POST /store/repositories/{repository}/repair`, ruft intern
`Repository.reset()` auf - siehe
[supervisor/store/repository.py](https://github.com/home-assistant/supervisor/blob/main/supervisor/store/repository.py)
und [supervisor/api/store.py](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/store.py)),
der einen frischen Git-Checkout erzwingt, ohne das Add-on zu
deinstallieren. Nur als allerletzter Ausweg: Deinstallieren +
Neuinstallieren **löscht `/data` restlos** (getestet, kein automatischer
Datenerhalt bei diesem Setup) – vorher über den **"📦 Alle Sites
sichern"**-Button im Panel ein Backup ziehen.

## Sicherheitshinweise

- Der Git-Access-Token wird **verschlüsselt** in der SQLite-DB
  (`/data/webhost.db`) gespeichert (Fernet, `cryptography`-Paket). Der
  Schlüssel liegt unter `/data/secret.key` (0600, beim ersten Start
  generiert) – `/data` bleibt damit weiterhin die Vertrauensgrenze
  (nur Add-on selbst + Root auf dem Host lesbar), aber ein reines
  Auslesen der DB-Datei allein (z.B. versehentlich geteilt, aus einem
  Backup ohne `secret.key`) legt den Token nicht mehr offen.
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
