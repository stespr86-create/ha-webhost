# Changelog

## 0.1.22

- Neu: Site-Typ **"Python-App"** - eigene/beliebige Python-Apps (Flask/
  FastAPI/beliebig) per ZIP hochladen, `POST /api/sites/python-upload`.
  Braucht eine `main.py`, die selbst auf `0.0.0.0:$PORT` lauscht;
  optionale `requirements.txt` wird automatisch installiert.
- Architektur bewusst **ohne** Docker-Socket-Zugriff (`docker_api`): jede
  Python-Site läuft als eigener, überwachter Betriebssystem-Prozess statt
  in einem eigenen Container - kein root-äquivalenter Zugriff auf den
  Host. Abhängigkeiten werden per `pip install --target` pro Site isoliert
  installiert (kein virtualenv nötig). Prozesse werden bei jedem
  App-Start/Site-Create/-Delete automatisch überwacht und bei Bedarf
  (neu) gestartet.
- Build-Tools (`build-base`, `python3-dev`) sind jetzt dauerhaft im
  Container installiert (vorher nur temporär für den eigenen
  Backend-Build), damit `pip install` von Nutzer-Apps auch Pakete mit
  C-Extensions kompilieren kann.
- Details siehe DOCS.md, Abschnitt "Python-Hosting".

## 0.1.21

- Neu: Site-Typ **"PHP-Upload"** - eigene/beliebige PHP-Apps per ZIP
  hochladen (wie "ZIP-Upload", aber `.php`-Dateien werden tatsächlich
  ausgeführt, nutzt denselben PHP-FPM-Pool-Mechanismus wie WordPress-Sites).
  Neuer Endpunkt `POST /api/sites/php-upload`, neues Formular im Panel,
  "🔄 Update"-Knopf funktioniert auch für diesen Typ.
- Bewusst (noch) ohne eigene Datenbank-Provisionierung pro App - siehe
  DOCS.md, Roadmap Phase 2/4.

## 0.1.20

- **Fix: Plugin-/Theme-Suche im Marketplace lieferte immer leere Ergebnisse**
  (eigenständiger Bug, unabhängig von der wp-cli-Installation - reiner
  Python-Code, kein wp-cli). Ursache: Die WordPress.org-APIs liefern/
  erwarten kein JSON, sondern PHP's `serialize()`-Format - dieselbe Art,
  wie WordPress selbst intern damit spricht. Der bisherige Code hat
  `json.loads()` direkt auf diese Antwort losgelassen, was immer
  fehlschlug (`Expecting value: line 1 column 1`). Zusätzlich fehlte das
  korrekte Request-Format (Plugin-API will POST mit PHP-serialisiertem
  `request`-Feld, Theme-API will GET mit demselben Feld als
  Query-Parameter - liefert dafür aber echtes JSON zurück, jede API tickt
  anders).
- Neu: Kleiner, eigenständiger PHP-serialize/unserialize-Codec
  (`services/php_serialize.py`, keine neue Abhängigkeit) - live gegen die
  echte WordPress.org-API verifiziert (u.a. Yoast SEO, Rank Math SEO als
  Suchtreffer für "seo").

## 0.1.19

- **Fix: `wp core install` (0.1.18) schlug fehl** - "Class 'Phar' not
  found". Der Container hatte nie die PHP-Extension `phar` installiert,
  ohne die sich die wp-cli `.phar`-Datei selbst nicht ausführen lässt.
  Vermutlich schon immer kaputt, fiel aber nie auf, da vor 0.1.15
  niemand echten PHP-Code (inkl. wp-cli-Aufrufen) auf einer laufenden
  Site testen konnte. Ergänzt außerdem weitere von WordPress-Core und
  wp-cli üblicherweise benötigte Extensions, die ebenfalls fehlten:
  mbstring, xml, dom, simplexml, ctype, tokenizer, openssl, zip (u.a.
  für Multibyte-Strings, XML-Verarbeitung und Plugin-/Theme-Installation
  per ZIP).

## 0.1.18

- **Fix: WordPress-Datenbank-Setup war unvollständig (eigenständiger,
  bisher verdeckter Bug).** Seit PHP jetzt tatsächlich ausgeführt wird
  (0.1.15-0.1.17), kam zum Vorschein: Das bisherige, handgeschriebene
  SQL-Setup legte nur 4 der ~12 WordPress-Kern-Tabellen an und nur eine
  Handvoll der von WordPress erwarteten Standard-Optionen. Fehlende
  Optionen `blog_charset`/`html_type` führten zu einem leeren, kaputten
  `Content-Type`-Header (`; charset=` statt `text/html; charset=UTF-8`) -
  Browser hätten WordPress-Seiten als Datei-Download statt als Webseite
  behandelt. Zusätzlich nutzte die Admin-Erstellung eigenes,
  WordPress-inkompatibles MD5-Passwort-Hashing statt echtem phpass - der
  Admin-Login hätte nicht funktioniert.
- Fix: WordPress wird jetzt über echtes `wp core install` (wp-cli, bereits
  im Container vorhanden) eingerichtet statt über Hand-SQL - legt das
  vollständige Standardschema und alle Standard-Optionen korrekt an,
  Admin-Passwort wird mit WordPress' eigenem Hashing gespeichert.
- Fix: Der beim Anlegen einer WordPress-Site eingegebene Blog-Name wurde
  bisher beim eigentlichen Setup ignoriert (immer "WordPress Site") - wird
  jetzt korrekt übernommen.

## 0.1.17

- **Fix: PHP-FPM startete seit 0.1.16 gar nicht mehr** ("unknown entry
  'pid'", "failed to load configuration file"). Der `pid`-Eintrag wurde ans
  Ende der php-fpm.conf angehängt statt davor - da `include=` inline
  verarbeitet wird, landete `pid` dadurch physisch hinter den eingebundenen
  Pool-Dateien, also im Abschnitt des zuletzt geladenen Pools statt in
  `[global]` (wo `pid` gültig ist). Jetzt wird die Zeile korrekt vor
  `include=` eingefügt.

## 0.1.16

- **Fix: PHP-FPM-Boot-Crashloop seit 0.1.15.** PHP-FPM verweigert den Start
  komplett, wenn sein Pool-Ordner keine einzige Config enthält ("No pool
  defined") - das war beim Containerstart immer der Fall, solange noch
  keine WordPress-Site existiert (die App schreibt die echten Pools erst
  nach ihrem eigenen Start). Betraf jeden frischen Container-Boot ohne
  WordPress-Sites, unabhängig davon ob man selbst WordPress nutzt.
  Behoben mit einem harmlosen Platzhalter-Pool, der PHP-FPM immer
  startfähig hält (nie von der Caddyfile referenziert, kein RAM-Verbrauch
  dank `pm=ondemand`).

## 0.1.15

- **Fix: WordPress-Sites waren nicht aufrufbar (404).** PHP wurde nie
  ausgeführt - eine Regression aus der Umstellung auf die dynamisch
  generierte Caddyfile hatte die vorgesehene Weiterleitung an nginx+PHP-FPM
  verloren, WordPress-Sites wurden seitdem nur noch statisch (und damit
  kaputt) ausgeliefert.
- Neu: Caddy leitet PHP-Requests jetzt direkt per `php_fastcgi` an einen
  **eigenen, ressourcenschonenden PHP-FPM-Pool pro WordPress-Site** weiter
  (`pm=ondemand` - 0 MB RAM für nicht besuchte Sites). Kein nginx mehr im
  Container nötig, dadurch ein laufender Prozess weniger.
- Details siehe DOCS.md, Abschnitt "PHP-Hosting (WordPress)".

## 0.1.14

- Fix: Regex-Pattern der Name-Eingabefelder (`[a-z0-9-]`) war ungültiges
  HTML5-Pattern und hat die Formular-Validierung im gesamten Panel
  blockiert - Buttons wie "Klonen & deployen" oder "Hochladen & deployen"
  ließen sich dadurch nicht mehr anklicken. Bindestrich in der
  Zeichenklasse jetzt escaped (`[a-z0-9\-]`).

## 0.1.13

- Fotogalerie: Download-Knopf unter jedem Foto in der Fotowand (Raster)
  sowie in der Lightbox - Fotos lassen sich jetzt auch einzeln
  herunterladen, nicht nur als Gesamt-ZIP.
- Datei-Manager: Dateigrößen werden jetzt als KB/MB statt in rohen Bytes
  angezeigt.

## 0.1.12

- Fotogalerie: Lightbox zeigt Fotos jetzt deutlich größer (bis 80% der
  Bildschirmhöhe statt vorher ca. 520px) und lässt sich mit den
  Pfeiltasten (← →) sowie per Klick auf die neuen ‹/›-Knöpfe der Reihe
  nach durchklicken (springt am Ende wieder zum Anfang).
- Neu: "⬇ Alle herunterladen"-Button auf der Galerie-Seite - lädt alle
  Fotos der Galerie gebündelt als ZIP herunter.
- Neu: "🔄 Seite aktualisieren"-Knopf bei Fotogalerie-Sites im Panel -
  zieht die neueste Galerie-Oberfläche (z.B. nach diesem Update) auf eine
  bereits angelegte Galerie, ohne hochgeladene Fotos anzutasten.

## 0.1.11

- Neu: Site-Typ "Fotogalerie" - eine gemeinsame Foto-Wand, auf die jeder mit
  dem Link ohne eigenen Account Fotos hochladen kann; alle sehen dieselbe
  Galerie. Fotos werden serverseitig verkleinert/als JPEG neu kodiert
  (Pillow) und liegen direkt in `/data`, nicht bei einem Drittanbieter.
  Optional lässt sich ein externer Link (z.B. zu einem bestehenden
  Google-Fotos-Album) hinterlegen. Moderation über den vorhandenen
  Datei-Manager (Foto im Ordner `uploads/` löschen, Galerie räumt den
  Eintrag automatisch auf).
- Dafür: neuer, eng gefasster Backend-Endpunkt (`/sites/<name>/api/*`),
  der - anders als die restliche Admin-API - auch auf dem öffentlichen
  Port 8090 ohne HA-Login erreichbar ist, da Gäste keinen HA-Zugang haben.
  Nur Foto-Upload und -Abruf, kein Löschen oder sonstige Admin-Funktion.
- Fix während der Entwicklung gefunden: Caddys Caddyfile-Adapter sortiert
  `handle`/`handle_path`-Blöcke selbstständig um, unabhängig von der
  Schreibreihenfolge - dadurch landete der neue API-Proxy-Block hinter dem
  allgemeinen Site-Dateien-Block und wurde nie erreicht. Behoben durch
  explizites `route { }` um beide Blöcke, das die Schreibreihenfolge
  erzwingt.
- DB-Schema erweitert (neue, optionale Spalten für den Galerie-Link) -
  bestehende Installationen bekommen die Spalten per einfacher
  Mini-Migration beim Start automatisch nachgezogen, ohne Datenverlust.

## 0.1.10

- Neu: Dunkles, aufgeräumteres Design für das gesamte Panel (Farben,
  Buttons, Badges, Tabellen, Datei-Manager) - keine funktionalen
  Änderungen.
- Fix: "Aktionen"-Spalte der Sites-Tabelle konnte auf schmaleren
  Fenstern abgeschnitten werden (verschärft durch die nun länger
  angezeigten externen URLs). Tabelle scrollt jetzt bei Bedarf
  horizontal; lange URLs werden mit "..." gekürzt (Volltext als
  Tooltip beim Hovern).

## 0.1.9

- Neu: "🔄 Cache leeren & neu laden"-Button im Panel-Header. Löscht
  gezielt nur die WebHost-eigenen Einträge aus dem Service-Worker-Cache
  der Home-Assistant-PWA (nicht den gesamten HA-Cache) und lädt neu -
  behebt das bekannte "Update zeigt neue Version, UI bleibt alt"-Problem
  per Klick, ohne die Browser-Entwicklertools zu öffnen.

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
