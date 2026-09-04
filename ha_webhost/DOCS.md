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
- Fotogalerie-Sites: gemeinsame Foto-Wand, auf die jeder mit dem Link ohne
  eigenen Account Fotos hochladen kann (z.B. für ein Familienfest) - Fotos
  liegen direkt auf diesem Server, siehe Abschnitt "Fotogalerie-Sites"
- WordPress-Sites: vollständiges WordPress inkl. Plugin-/Theme-Marketplace,
  Updates, Backups, Health-Checks - eigene MariaDB-Datenbank pro Site, PHP
  läuft über einen **eigenen, ressourcenschonenden PHP-FPM-Pool pro Site**
  (siehe Abschnitt "PHP-Hosting (WordPress)" unten)
- PHP-Upload-Sites: eigene/beliebige PHP-Apps per ZIP hochladen (wie
  ZIP-Upload, aber `.php`-Dateien werden tatsächlich ausgeführt, gleicher
  PHP-FPM-Pool-Mechanismus wie bei WordPress) - ohne eigene
  Datenbank-Provisionierung
- Python-Upload-Sites: eigene/beliebige Python-Apps (Flask/FastAPI/beliebig)
  per ZIP hochladen, eigener überwachter Prozess pro Site (kein
  Docker-Container) - siehe Abschnitt "Python-Hosting" unten
- Redeploy per Knopfdruck (git pull bei Git-Sites, erneuter ZIP-Upload
  unter demselben Namen bei Upload-/PHP-Upload-/Python-Upload-Sites –
  "🔄 Update"-Button)
- Einfacher Datei-Browser/-Editor über die API (`/api/files/...`)
- Manuelles Backup aller Sites als ein ZIP-Download ("📦 Alle Sites
  sichern"-Button im Panel, `.git`-/`.deps`-Verzeichnisse werden
  ausgeschlossen)
- Zwei getrennte Zugriffswege: Port 8000 (Ingress, Admin-UI + API + Sites,
  HA-Login nötig) und Port 8090 (**nur** `/sites/<name>/*`, kein
  Admin-Zugriff - für öffentliche Freigabe gedacht, siehe unten)
- Reverse Proxy (Caddy) inkl. SPA-Fallback (`try_files … /index.html`)
- Läuft komplett ohne Docker-Socket-Zugriff → kein erhöhtes Sicherheitsrisiko
  für den Host

### Bewusst NICHT enthalten (siehe Roadmap)

- Datenbank-Verwaltung für eigene/generische Apps (MariaDB/PostgreSQL) -
  WordPress-Datenbanken werden automatisch verwaltet, das ist unabhängig
  davon
- Automatische Backups nach Zeitplan (bewusst nicht geplant)
- Mehrere gleichzeitige Admin-Benutzer (Auth läuft komplett über HA)

Grund: Auf typischer HA-Hardware (insbesondere < 8 GB RAM) sprengt der volle
Funktionsumfang aus dem ursprünglichen Konzept die verfügbaren Ressourcen,
und Docker-Socket-Zugriff für App-Container ist ein erhebliches
Sicherheitsrisiko (praktisch Root-Zugriff auf den Host). Diese Punkte kommen
erst in späteren Phasen, dann bewusst und einzeln abgesichert.

## PHP-Hosting (WordPress)

**Update (ab v0.1.15):** WordPress-Sites laufen jetzt tatsächlich - vorher
wurden sie zwar korrekt angelegt (Datenbank, `wp-config.php`, Dateien), beim
Aufruf im Browser kam aber ein **404**, weil PHP-Dateien nie ausgeführt
wurden. Ursache war eine Regression bei der Umstellung von einer statischen
Caddyfile (die noch zu nginx+PHP-FPM auf Port 8080 durchgereicht hat, siehe
`cont-init.d/10-init-data.sh`) auf die dynamisch generierte Caddyfile in
`services/caddy_service.py` - die dynamische Variante hat jede Site
(inklusive WordPress) nur noch statisch ausgeliefert. `nginx` war dadurch
faktisch totes Gewicht im Container (installiert, konfiguriert, aber nie im
tatsächlichen Request-Pfad erreicht) und wurde entfernt.

**Aktuelle Architektur:** Caddy spricht für PHP-Sites direkt per eingebautem
`php_fastcgi` (FastCGI-Protokoll) mit PHP-FPM - kein nginx mehr als
Zwischenstation nötig, ein laufender Prozess weniger im Container. Jede
WordPress-Site bekommt dabei einen **eigenen PHP-FPM-Pool** (eigener
Unix-Socket unter `/run/php-fpm/<name>.sock`, `services/php_fpm_service.py`):

- `pm = ondemand` statt `dynamic`/`static`: PHP-Worker-Prozesse werden erst
  bei der ersten Anfrage gestartet und nach Leerlauf (`process_idle_timeout
  = 15s`) wieder beendet. Eine gerade nicht besuchte Site verbraucht damit
  dauerhaft **0 MB RAM** statt staendig laufender Leerlauf-Worker - wichtig
  bei mehreren WordPress-Sites mit wenig gleichzeitigem Traffic auf
  schwacher Hardware.
- `pm.max_children = 3` pro Pool (begrenzt maximale gleichzeitige PHP-Last
  je Site), `memory_limit = 128M` (WordPress-Mindestempfehlung).
- Pool-Configs liegen (wie die Caddyfile) unter `/data/php-fpm-pools/` und
  werden bei jedem App-Start sowie bei jedem Anlegen/Löschen einer Site aus
  dem DB-Stand neu erzeugt (`site_service.sync_proxy()`) - PHP-FPM liest sie
  per `SIGUSR2` neu ein (graceful reload, laufende Requests werden nicht
  abgebrochen).
- **Site-Typen mit PHP-FPM-Pool:** `wordpress` und `php` (Site-Typ
  "PHP-Upload", seit v0.1.21 - eigene/beliebige PHP-Apps per ZIP). Ein
  Upload über den Site-Typ "ZIP-Upload" bleibt bewusst rein statisch
  (PHP-Quelltext würde als Text/Download ausgeliefert, nicht ausgeführt) -
  wer PHP-Ausführung braucht, nutzt "PHP-Upload" statt "ZIP-Upload".

## Python-Hosting

Site-Typ **"PHP-Upload"'s Pendant für Python** (seit v0.1.22): eigene/
beliebige Python-Apps per ZIP hochladen, `POST /api/sites/python-upload`.

**Voraussetzung:** Die ZIP muss eine `main.py` im Root enthalten, die
selbst per HTTP auf `0.0.0.0:$PORT` lauscht (Umgebungsvariable `PORT` wird
vom Add-on gesetzt) - Standard-Konvention, passt zu den meisten Flask-/
FastAPI-Quickstarts (`app.run(host='0.0.0.0',
port=int(os.environ['PORT']))` bzw. `uvicorn.run(app, host='0.0.0.0',
port=int(os.environ['PORT']))`). Eine optionale `requirements.txt` im Root
wird automatisch installiert.

**Architektur** (`services/python_app_service.py`): Kein Docker-Container
pro App (siehe Sicherheitshinweis oben) - stattdessen ein eigener,
überwachter Betriebssystem-Prozess pro Site:

- Abhängigkeiten werden per `pip install --target=<site>/.deps`
  installiert (kein eigenes virtualenv - das venv-Stdlib-Modul ist auf
  Alpine nicht zuverlässig garantiert vorhanden, `--target` braucht nur das
  ohnehin vorhandene `pip3`) und zur Laufzeit per `PYTHONPATH`
  eingebunden - dadurch pro Site isoliert, ohne einen kompletten
  Stdlib-Klon je App.
- Jede Site bekommt einen deterministischen, kollisionsfreien lokalen Port
  (`9100 + Site-ID`), Caddy leitet Requests unter `/sites/<name>/*` per
  `reverse_proxy` direkt dorthin.
- Prozess-Überwachung: bei jedem App-Start und jedem Site-Create/-Delete
  (`sync_proxy()`) wird geprüft, ob für jede aktive Python-Site ein Prozess
  läuft - fehlende/abgestürzte Prozesse werden automatisch neu gestartet
  (`ensure_running()`), verwaiste Prozesse gelöschter Sites gestoppt
  (`stop_orphaned()`). Kein separater Cron/Watchdog nötig, da `sync_proxy()`
  ohnehin bei jedem relevanten Ereignis läuft.
- Build-Tools (`build-base`, `python3-dev`) bleiben im Container dauerhaft
  installiert (nicht nur für den eigenen Backend-Build), damit `pip
  install` auch Pakete mit C-Extensions kompilieren kann, für die es kein
  fertiges Wheel für die Ziel-Architektur gibt (v.a. relevant auf armv7) -
  kostet Image-Größe, nicht Laufzeit-RAM.

**Bekannte Einschränkungen:**
- Alle Python-Apps teilen sich dieselbe im Container installierte
  Python-Version - keine App-spezifische Interpreter-Version wählbar.
- Kein Datenbank-Zugang out-of-the-box (wie bei PHP-Upload) - eigene
  Datenbank-Provisionierung pro App ist weiterhin Roadmap Phase 4.
- Kein Log-Rotation für die App-eigene Log-Datei (`<site>/.app.log`,
  sammelt stdout/stderr der App) - wächst über die Zeit unbegrenzt, bei
  Bedarf manuell über den Datei-Manager leeren/löschen.
- Geringere Isolation zwischen Apps als bei getrennten Containern (alle
  Prozesse laufen im selben Betriebssystem-Namespace) - für kleine,
  vertrauenswürdige Apps ein sinnvoller Kompromiss, kein Ersatz für
  Multi-Tenant-Hosting mit nicht vertrauenswürdigem Code.

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

## Fotogalerie-Sites

Über "Neue Site: Fotogalerie" im Panel lässt sich eine gemeinsame Foto-Wand
anlegen (z.B. für ein Familienfest): jeder mit dem Link kann - ganz ohne
eigenen Google-/HA-Account - Fotos hochladen, alle sehen dieselbe Galerie
(Polling alle ~12s). Optional lässt sich ein externer Link (z.B. zu einem
Google-Fotos-Album) hinterlegen, der als zusätzlicher Button angezeigt wird.

Technisch:

- Fotos werden beim Hochladen serverseitig per Pillow verkleinert (max.
  1600px Kante) und als JPEG neu kodiert (Qualität 82) - hält Speicher- und
  RAM-Verbrauch auf der Zielhardware in Grenzen und verwirft dabei
  eingebettete EXIF-Metadaten (z.B. GPS-Standort) bis auf die für die
  Ausrichtung nötige Rotation.
- Limits pro Galerie: max. 8 MB pro Foto, max. 300 Fotos, max. 300 MB
  Gesamtgröße (siehe `core/config.py`, `MAX_GALLERY_*`) - schützt vor
  vollem `/data` bzw. Missbrauch.
- Hochgeladene Dateien werden per Pillow tatsächlich als Bild geöffnet und
  validiert (nicht nur Dateiendung/Content-Type geprüft) - eine als „.jpg“
  getarnte Nicht-Bild-Datei wird abgelehnt.
- Der Foto-Upload/-Abruf ist bewusst der **einzige** Backend-Endpunkt, der
  auch auf dem öffentlichen Port 8090 ohne HA-Login erreichbar ist (Route
  `/sites/<name>/api/*`, streng getrennt vom Admin-`/api/*`) - Gäste haben
  ja keinen HA-Zugang. Es gibt darüber **kein** Löschen und keine sonstige
  Admin-Funktion.
- Moderation: unerwünschte Fotos einfach über den normalen "📂
  Dateien"-Knopf der Site im Ordner `uploads/` löschen - die Galerie
  entfernt den Eintrag automatisch beim nächsten Laden (kein eigener
  Lösch-Endpunkt nötig).
- Da der öffentliche Port keine Anmeldung kennt, ist die (lange, nicht
  erratbare) URL der eigentliche Zugriffsschutz - wie bei allen Sites auf
  Port 8090. Für sensiblere Anlässe ggf. den Link nur gezielt teilen statt
  öffentlich zu posten.

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
zurückgestellt.

1. **Phase 2 (schlanke Variante) - abgeschlossen seit v0.1.21** (Mechanismus
   seit v0.1.15 fürs WordPress-Hosting, generischer Site-Typ "PHP-Upload"
   seit v0.1.21): PHP-Hosting über einen **einzigen, geteilten PHP-FPM-Prozess** im
   Add-on-Container – läuft als weiterer Subprozess, analog zum bereits
   vorhandenen Caddy, statt eigener Container pro App. Jede PHP-Site
   bekommt einen eigenen FPM-**Pool** (eigenes RAM-Limit über
   `pm.max_children`, `pm=ondemand` für 0 MB RAM im Leerlauf), Caddy
   leitet per `php_fastcgi` direkt an den passenden Pool weiter - siehe
   Abschnitt "PHP-Hosting (WordPress)" oben für die tatsächliche
   Umsetzung und `services/php_fpm_service.py`.
   - **Kein `docker_api: true` nötig** – der ursprünglich größte
     Kritikpunkt (Docker-Socket-Zugriff, siehe Sicherheitshinweis oben)
     entfällt damit komplett.
   - Deutlich schlanker als "ein Container pro App": kein zusätzlicher
     OS-Layer und Container-Boot je App – spart RAM auf schwacher
     Hardware (Zielgerät: i3-Notebook, 4GB RAM).
   - Trade-off: geringere Isolation zwischen Apps als bei vollständiger
     Container-Trennung – ein PHP-Interpreter mit mehreren Pools statt
     komplett getrennter Umgebungen. Für kleine, vertrauenswürdige Apps
     (eigene/Familien-/Vereinsprojekte) ein sinnvoller Kompromiss.
   - **Site-Typ "PHP-Upload"** (seit v0.1.21): ZIP hochladen wie bei
     "ZIP-Upload", `.php`-Dateien werden aber tatsächlich ausgeführt
     (eigener PHP-FPM-Pool, siehe oben). API: `POST /api/sites/php-upload`
     (Formfelder `name` + `file`, wie `/api/sites/upload`).
   - **Bewusst noch nicht enthalten:** Eigene Datenbank-Provisionierung pro
     App (SQLite oder MariaDB) - das war ursprünglich Teil der Phase-2-Idee,
     ist aber auf Phase 4 verschoben (siehe unten). Eine hochgeladene
     PHP-App kann sich aktuell nur manuell mit der bereits laufenden
     MariaDB verbinden (Zugangsdaten müsste man sich selbst einrichten,
     z.B. über die MariaDB-Kommandozeile im Container) - keine
     automatische Erstellung/Verwaltung wie bei WordPress.
2. **Phase 3 - abgeschlossen seit v0.1.22, anders umgesetzt als ursprünglich
   geplant**: Python-App-Hosting (Flask/FastAPI/Django/beliebiges `main.py`).
   Ursprünglich hier vorgesehen: ein eigener Container pro App (mangels
   einheitlichem Pool-Modell wie bei PHP, wegen unterschiedlicher
   Python-Versionen/Abhängigkeiten je App), mit `docker_api: true`. Bewusst
   **nicht** so umgesetzt (siehe Sicherheitshinweis oben) - stattdessen wie
   bei PHP ein eigener, überwachter **Prozess** pro Site (kein Container,
   kein Docker-Socket-Zugriff nötig). Siehe Abschnitt "Python-Hosting"
   unten und `services/python_app_service.py`.
   - Trade-off: alle Python-Apps teilen sich dieselbe im Container
     installierte Python-Version; Abhängigkeiten werden trotzdem pro Site
     isoliert (`pip install --target=.deps`, zur Laufzeit per `PYTHONPATH`
     eingebunden - kein eigenes virtualenv, das venv-Stdlib-Modul ist auf
     Alpine nicht zuverlässig garantiert vorhanden).
3. **Monitoring - abgeschlossen seit v0.1.27**: Speicherplatz-, RAM- und
   CPU-Nutzung pro Site, abrufbar über `GET /api/sites/{name}/monitoring`
   und im Admin-Panel per "📊 Monitoring"-Knopf pro Site. Speicherplatz gibt
   es für jeden Site-Typ (rekursive Verzeichnisgröße). RAM/CPU gibt es nur
   für Site-Typen mit eigenem Prozess:
   - **Python-Apps**: trivial, da bereits eine PID pro Site getrackt wird
     (`python_app_service.get_pid()`) - RAM/CPU direkt aus `/proc/<pid>/...`.
   - **WordPress/PHP-Upload**: PHP-FPM (`pm=ondemand`) hat keine feste PID
     pro Pool - Worker-Prozesse werden stattdessen über den von PHP-FPM
     gesetzten Prozesstitel gefunden (`php-fpm: pool <name>`, sichtbar unter
     `/proc/<pid>/cmdline`). Ist ein Pool gerade idle, gibt es schlicht
     keinen Worker - RAM/CPU werden dann als 0 ausgewiesen (`running: false`,
     normaler Leerlauf-Zustand, kein Fehler).
   - **Statische/Git-/Galerie-Sites**: kein eigener Prozess, nur
     Speicherplatz (`running: null`).
   - Implementierung bewusst ohne Sub-Prozess-Aufruf (kein `ps`, kein
     `shell_exec`) - liest ausschließlich direkt aus dem `/proc`-
     Pseudo-Dateisystem, siehe `services/monitoring_service.py`.
4. **Live-Log-Viewer - abgeschlossen seit v0.1.28**: letzte Log-Zeilen einer
   Site direkt im Admin-Panel, abrufbar über `GET /api/sites/{name}/logs`
   und per "📜 Logs"-Knopf. Verfügbar für Site-Typen mit eigenem Prozess:
   - **Python-Apps**: stdout/stderr des App-Prozesses.
   - **WordPress/PHP-Upload**: PHP-Fehler-Log des zugehörigen PHP-FPM-Pools
     (`catch_workers_output` + `error_log` je Pool, siehe
     `php_fpm_service.py`) - vorher gingen PHP-Fehler faktisch ins Leere
     (nur im gemeinsamen Caddy-Zugriffslog sichtbar, wenn überhaupt).
   - **Statische/Git-/Galerie-Sites**: kein eigener Prozess, `available:
     false`.
   - Logs liegen zentral unter `/data/logs/` statt im Site-Verzeichnis
     selbst - landen dadurch nicht versehentlich in ZIP-Backups oder im
     Datei-Manager der Site, überleben aber (anders als `/run`) einen
     Container-Neustart. Siehe `services/log_service.py`.
   - Bewusst kein automatisches Live-Tailing/WebSocket - ein "🔄 neu laden"
     per Knopf-Klick reicht für den Zweck (Fehlersuche) und hält die
     Implementierung einfach.
5. **Bewusst nicht geplant**: automatische Backup-Zeitpläne (auf
   ausdrücklichen Wunsch nicht Teil des Projekts - Backups bleiben manuell
   über "Alle Sites sichern"/die Health-Check-Backups pro WordPress-Site).
   MariaDB/PostgreSQL-Provisioning für generische PHP-/Python-Apps ist
   weiterhin offen (Phase 4).
