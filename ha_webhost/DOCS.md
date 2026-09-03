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

**Tailscale Funnel erlaubt nur drei öffentliche Ports: 443, 8443, 10000.**
Dieses Projekt nutzt bewusst **Port 10000** dafür (nicht 8443!) – dazu
gleich mehr.

### ⚠️ Vorher unbedingt prüfen: belegt ein anderer Dienst schon einen dieser Ports?

**Konkret bei uns passiert:** Auf dem Referenzsystem war Port 8443 bereits
für einen anderen Dienst (n8n/Telegram-Webhook) reserviert. Ein
`tailscale serve --https=8443 ...` für WebHost hat diese bestehende
Zuordnung **kommentarlos überschrieben** – der andere Dienst war damit
nicht mehr erreichbar, ohne dass eine Fehlermeldung kam. Tailscale warnt
davor nicht.

**Vor der Einrichtung immer erst prüfen:**

```bash
tailscale funnel status
```

Zeigt das bereits einen Eintrag für Port 8443 (oder 443), **diesen Port
nicht für WebHost verwenden** – auf **10000** ausweichen (das einzige der
drei Ports, der bei uns frei war). Prüft man das nicht und ein Konflikt
tritt trotzdem auf: der andere Dienst fällt sofort und ohne
Fehlermeldung aus.

### Zwei Befehle nötig – beide, nicht nur einen

`tailscale serve` (legt die lokale Zuordnung fest) und `tailscale funnel`
(schaltet sie öffentlich) sind **zwei getrennte Schritte**. Wird nach einer
Änderung nur `serve` erneut ausgeführt, wird die Funnel-Freigabe dabei
**entfernt** ("Removing Funnel..." in der Ausgabe) – der Port ist dann nur
noch tailnet-intern erreichbar, nicht mehr öffentlich. Immer **beide**
Befehle zusammen ausführen:

```bash
tailscale serve --bg --https=10000 http://127.0.0.1:8090
tailscale funnel --bg --https=10000 8090
```

Wichtig zur Syntax (hat sich mit neueren Tailscale-Versionen geändert,
`tailscale funnel --help` zeigt die für die jeweils installierte Version
gültige Form): `<target>` ist immer der **lokale** Port/URL (hier 8090),
nicht der öffentliche. Der öffentliche Port wird über `--https=` gesetzt.

**Falls `tailscale` nicht direkt im Terminal gefunden wird** (z.B. im HA-OS
Host-Terminal): Der Tailscale-Client läuft im eigenen Add-on-Container,
nicht auf dem nackten Host. Dorthinein wechseln:

```bash
docker ps | grep -i tailscale        # Container-Namen finden
docker exec -it <container-name> sh  # hinein wechseln
find / -name "tailscale" -type f 2>/dev/null   # Pfad zur Binary finden (oft /opt/tailscale)
```

**Status jederzeit prüfen:**

```bash
tailscale funnel status
```

Danach sind alle aktiven Sites erreichbar unter:

```
https://<euer-tailscale-hostname>:10000/sites/<name>/
```

(z.B. `https://homeassistant.tailf85481.ts.net:10000/sites/gresu-feuerwehrmann/`)

**Wieder deaktivieren:**

```bash
tailscale funnel --https=10000 off
```

**Sicherheitshinweis:** Sobald Funnel aktiv ist, ist Port 8090 (und damit
alle aktiven Sites) für **jeden im Internet** erreichbar, ohne HA-Login.
Nur Sites deployen, die tatsächlich öffentlich sein sollen. Das Admin-Panel
selbst bleibt davon unberührt (weiterhin nur über HA-Ingress erreichbar).

### ⚠️ Bekannte Einschränkung: Port 10000 in manchen Netzwerken blockiert

Getestet und bestätigt: Aus einem Firmennetzwerk war die öffentliche URL
(Port 10000) **nicht erreichbar** (Timeout), aus Mobilfunknetz und freiem
WLAN dagegen problemlos. Ursache: Viele Firmen-Firewalls lassen ausgehend
nur Standard-Ports (80/443) durch, unübliche Ports wie 10000 werden
blockiert. Der Server/Funnel selbst war dabei nachweislich gesund (von
außerhalb per `curl` mit sauberem TLS-Handshake bestätigt) – es liegt am
jeweiligen Netzwerk, nicht an dieser Konfiguration.

**Aktueller Stand:** Bewusst so belassen (Stand: nach Rücksprache) – Port
10000 ist der einzige der drei von Tailscale erlaubten Funnel-Ports (443,
8443, 10000), der auf dem Referenzsystem nicht bereits durch einen anderen
Dienst (n8n, siehe oben) belegt war.

**Falls das später zum Problem wird, Optionen für einen Standard-Port**
(443 oder 8443, in restriktiven Netzwerken zuverlässiger erreichbar):
- Den anderen Dienst (der aktuell 443/8443 belegt) auf einen internen
  Port verschieben, um den Standard-Port für WebHost freizumachen –
  **nur mit Vorsicht**, siehe Vorfall oben: unbedingt vorher
  `tailscale funnel status` prüfen und die Config des anderen Dienstes
  danach explizit gegentesten.
- Alternativ prüfen, ob die Firmen-IT Port 10000 ausgehend freigeben kann.

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

**Echte Lösung (kein Deinstallieren nötig, kein Datenverlust):** Seit
Version 0.1.9 gibt es dafür den Knopf **"🔄 Cache leeren & neu laden"**
oben im Panel – einfach anklicken, fertig. Löscht gezielt nur die
WebHost-eigenen Cache-Einträge (nicht den gesamten HA-Cache).

Falls der Knopf selbst noch die alte Version zeigt (z.B. direkt nach dem
allerersten Update auf 0.1.9): einmalig manuell nachhelfen, entweder per
Hard-Reload (Cmd/Ctrl+Shift+R – hilft nicht immer, da das nur den
normalen HTTP-Cache leert, nicht den Service-Worker-Cache) oder
zuverlässiger über die Chrome-Entwicklertools: `F12` → Tab **"Application"**
→ **"Service Workers"** → bei der HA-Domain auf **"Unregister"** klicken
→ Seite neu laden. Danach funktioniert auch der Knopf selbst wieder für
alle zukünftigen Updates.

Alternativ (z.B. für eigene Scripts) direkt per Konsole/`javascript_exec`
einer Browser-Automatisierung:

```js
const cache = await caches.open("workbox-runtime-https://<eure-ha-domain>/");
const requests = await cache.keys();
for (const req of requests) {
  if (req.url.includes("static/")) await cache.delete(req);
}
```

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
