# 🏠 HA WebHost – Das einfachste Website-Hosting für Home Assistant

**Hosting, das so einfach ist, dass du nicht glaubst, dass es funktioniert.**

> Starte deine Website von Zuhause aus. Keine Server-Admin-Kenntnisse nötig. Alles im Browser.

---

## ⚡ Was ist das?

**HA WebHost** ist ein **Home Assistant Add-On**, mit dem du Websites direkt auf deinem Home Assistant laufen lässt:

- **WordPress-Blogs** – Vollwertig mit Plugins & Themes
- **Statische Websites** – HTML/CSS/JS von ZIP-Upload
- **Fotogalerien** – Fotos hochladen, Link teilen, fertig
- **Git-basierte Websites** – Auto-Deploy von GitHub/GitLab
- **Alles in einem Browser** – Kein Terminal, kein SSH, kein Kommandozeilen-Wahnsinn

### Wer sollte das nutzen?

✅ **Perfekt für dich, wenn du:**
- Ein Home Assistant hast
- Eine Website starten willst (Blog, Portfolio, Shop, whatever)
- Nicht in Server-Admin-Sachen reingehen willst
- Deine Daten lieber selbst hosten als an Big Tech zu geben
- Mit Tailscale/VPN von überall zugreifen möchtest

❌ **Nicht ideal, wenn du:**
- Eine absolut hochperformante Multi-Server-Infrastruktur brauchst
- Millionen von Besuchern gleichzeitig erwartest
- Nur für die Cloud-Lösung arbeiten möchtest

---

## 🚀 Quick Start (5 Minuten)

### Schritt 1: Installation im Home Assistant
1. **Home Assistant öffnen** → Settings → Add-ons → Add-on Store
2. **Nach "HA WebHost" suchen** und installieren
3. **"Start on Boot" einschalten**
4. **WebUI öffnen** (Button im Add-on-Panel)

### Schritt 2: Erste Website erstellen

#### Option A: WordPress-Blog (Einfachste Variante)
```
Im HA WebHost Panel:
1. "Neue Site: WordPress" → Name eingeben → "WordPress installieren"
2. Warten (1-2 Minuten)
3. Link klicken → WordPress-Setup durchlaufen (Blog-Name, Admin-Passwort, etc.)
4. Fertig! Dein Blog läuft.
```

**Was passiert:**
- WordPress wird automatisch heruntergeladen
- Datenbank wird erstellt
- Admin-Account wird angelegt
- Deine Website ist online unter `/sites/dein-name/`

#### Option B: Statische Website (ZIP-Upload)
```
1. "Neue Site: ZIP-Upload" → Name eingeben → ZIP-Datei auswählen
2. Hochladen & warten
3. Fertig! Website läuft.
```

**Was brauchst du:**
- Eine ZIP-Datei mit HTML/CSS/JS
- Wichtig: Der Hauptordner in der ZIP muss ein `index.html` haben

#### Option C: Fotogalerie (Gemeinsame Fotos ohne Accounts)
```
1. "Neue Site: Fotogalerie" → Name eingeben
2. Link weitergeben
3. Jeder kann Fotos hochladen, alle sehen dieselbe Galerie
```

#### Option D: Git-Deploy (Auto-Deploy von GitHub)
```
1. "Neue Site: Git-Deployment" → GitHub-URL eingeben
2. Bei jedem Push wird die Website automatisch aktualisiert
3. Perfect für Entwickler
```

---

## 🎯 Echte Beispiele

### Beispiel 1: Blog für die Hobbys

**Das wollen wir:** Ein persönlicher Blog über deine Hobbys (Fotografie, Gärtnern, Reisen, etc.)

**So geht's:**
```
1. WordPress installieren (sieh oben)
2. Im WordPress Admin:
   - Blog-Titel anpassen
   - Ein paar Plugins installieren (z.B. "Yoast SEO" für besseres Google-Ranking)
   - Ein schönes Theme installieren (z.B. "OceanWP")
3. Erste Blog-Posts schreiben
4. Link freunden zeigen/in Social Media teilen
```

**Admin-Panel:**
- Dein Blog unter: `http://ha-server.local/sites/mein-hobby-blog/`
- Admin unter: `http://ha-server.local/sites/mein-hobby-blog/wp-admin` (Benutzer: admin)

### Beispiel 2: Portfolio für deine Arbeit

**Das wollen wir:** Ein Portfolio-Website um deine Arbeiten zu zeigen

**Option 1 (Einfach):**
```
1. Eine HTML-Portfolio-Website lokal bauen
2. Als ZIP exportieren
3. ZIP in HA WebHost hochladen
4. Fertig, online!
```

**Option 2 (Developer-freundlich):**
```
1. Portfolio auf GitHub hosten
2. In HA WebHost: Git-Deployment mit deinem GitHub-Repo
3. Bei jedem Push auf GitHub wird deine Website aktualisiert
4. Zero-Downtime Updates
```

### Beispiel 3: Fotogalerie für die Familie

**Das wollen wir:** Fotos von Familien-Events teilen (Hochzeit, Urlaub, etc.)

**So geht's:**
```
1. "Neue Site: Fotogalerie" erstellen
2. Name: "hochzeit-2024"
3. Link an Familie weitergeben: http://ha-server.local/sites/hochzeit-2024/
4. Familie kann hochladen, ohne Account zu erstellen!
5. Alle Fotos landen auf deinem Server (privat!)
```

### Beispiel 4: Wiki / Dokumentation

**Das wollen wir:** Ein Wiki für Familien-Wissen oder interne Dokumentation

**So geht's:**
```
1. WordPress installieren
2. Plugin installieren: "BookPress" oder "Doku Wiki"
3. Strukturierte Seite zum Wiki-Format aufbauen
4. Team kann Beiträge schreiben
```

**API-Aufruf (für Entwickler):**
```bash
# Plugin suchen
curl http://ha-server.local/api/sites/mein-wiki/plugins/search?q=wiki

# Plugin installieren
curl -X POST http://ha-server.local/api/sites/mein-wiki/plugins/install \
  -d "slug=documentpress&activate=true"
```

---

## 🎮 Features im Detail

### 🎨 WordPress-Sites
- ✅ Vollständiges WordPress 6.x
- ✅ MariaDB-Datenbank (automatisch)
- ✅ Plugins aus WordPress.org Marketplace installieren
- ✅ Themes installieren + aktivieren
- ✅ Admin-Passwort automatisch generiert
- ✅ Automatische DB-Backups
- ✅ Security Hardening (wp-config geschützt)
- ✅ Auto-Updates für Core/Plugins/Themes
- ✅ Health-Checks (DB-Status, etc.)

**API:**
```bash
# WordPress-Site erstellen
POST /api/sites/wordpress
  - name: "mein-blog"
  - blog_name: "Mein persönlicher Blog"
  - admin_email: "ich@example.com"

# Plugin suchen
GET /api/sites/{name}/plugins/search?q=seo

# Plugin installieren
POST /api/sites/{name}/plugins/install
  - slug: "yoast-seo"
  - activate: true

# Updates prüfen
GET /api/sites/{name}/updates/check

# Updates installieren
POST /api/sites/{name}/updates/install?core=true&plugins=true

# Health-Check
GET /api/sites/{name}/health

# Backup erstellen
POST /api/sites/{name}/backup
```

### 📦 ZIP-Upload Sites
- ✅ React/Vue/Angular Apps (mit relativem Base-Path)
- ✅ Statische HTML-Websites
- ✅ Single-Page-Applications
- ✅ Re-Upload = Auto-Update
- ✅ Datei-Manager im Browser (upload/edit/delete)

### 🖼️ Fotogalerien
- ✅ Gäste können hochladen (kein Account nötig)
- ✅ Automatische Thumbnail-Generierung
- ✅ Responsive Design
- ✅ Google-Fotos Integration (optional)
- ✅ Einzeln-Download oder ZIP-Download

### 🚀 Git-Deployment
- ✅ Auto-Deploy von GitHub/GitLab
- ✅ Bei jedem Push automatisch aktualisiert
- ✅ Private Repos mit Access-Tokens
- ✅ Branch-Auswahl
- ✅ Redeploy-Button im Panel

### 🛡️ Sicherheit & Backups
- ✅ Verschlüsselte DB-Passwörter
- ✅ Automatische tägliche Backups
- ✅ wp-config.php ist geschützt
- ✅ Security Headers (X-Frame-Options, etc.)
- ✅ .htaccess geschützt
- ✅ Isolation zwischen Sites

### 📊 Monitoring & Updates
- ✅ Health-Check API
- ✅ Update-Checker (Core, Plugins, Themes)
- ✅ One-Click Updates
- ✅ Error-Logging
- ✅ Multi-Site-Validierung

---

## 🔧 Für Entwickler

### API-Übersicht

```bash
# Sites auflisten
GET /api/sites

# Site-Details
GET /api/sites/{name}

# WordPress-Site erstellen
POST /api/sites/wordpress

# Datei-Manager
GET /api/files/{name}?path=/
POST /api/files/{name}/upload?path=/
DELETE /api/files/{name}?path=/datei.txt

# Plugin-Marketplace
GET /api/sites/{name}/plugins/search?q=...
POST /api/sites/{name}/plugins/install
GET /api/sites/{name}/plugins/list
DELETE /api/sites/{name}/plugins/{slug}

# Updates
GET /api/sites/{name}/updates/check
POST /api/sites/{name}/updates/install

# Backups
POST /api/sites/{name}/backup
GET /api/sites/backup  # Alle Sites als ZIP

# Health-Check
GET /api/sites/{name}/health
GET /api/system/validate-wordpress
```

### Beispiel: Site programmgesteuert erstellen

```python
import requests

BASE_URL = "http://ha-server.local"

# WordPress-Site erstellen
response = requests.post(
    f"{BASE_URL}/api/sites/wordpress",
    data={
        "name": "mein-projekt",
        "blog_name": "Mein Projekt Blog",
        "admin_email": "ich@example.com"
    }
)

site = response.json()
print(f"Admin: {site['wordpress_admin_user']}")
print(f"Passwort: {site['wordpress_admin_password']}")  # Nur einmal angezeigt!
print(f"URL: {BASE_URL}/sites/mein-projekt/")

# Plugin installieren
requests.post(
    f"{BASE_URL}/api/sites/mein-projekt/plugins/install",
    data={
        "slug": "elementor",  # Page-Builder
        "activate": True
    }
)

# Health-Check
health = requests.get(f"{BASE_URL}/api/sites/mein-projekt/health").json()
print(f"Site healthy: {health['healthy']}")
```

---

## 📱 Was ist möglich?

### Kleine Projekte
- 📝 Persönlicher Blog
- 🎨 Portfolio-Website
- 🖼️ Fotogalerie
- 📋 To-Do/Notiz-App
- 🎵 Musik-Blog

### Mittlere Projekte
- 💼 Business-Website
- 📚 Dokumentation/Wiki
- 🛒 Kleiner Shop (mit WooCommerce)
- 👥 Community-Forum (mit bbPress)
- 📧 Newsletter-Seite

### Fortgeschrittene Projekte
- 🤖 Multi-User-Systeme
- 🔄 API-basierte Apps
- 📊 Dashboards
- 🎮 Web-Spiele
- 🔗 Blockchain-Integration (theoretisch)

---

## ⚙️ Installation & Setup

### Voraussetzungen
- Home Assistant Installation
- 2 GB freier Speicher (für Add-on + eine WordPress-Site)
- Stabiles Netzwerk

### Installation
1. Home Assistant öffnen
2. Settings → Add-ons → Add-on Store
3. Suchen: "HA WebHost"
4. Installieren
5. "Start on Boot" einschalten
6. Neustarten
7. WebUI öffnen

### Externe Zugriff (Tailscale)
```bash
# In Home Assistant SSH:
curl -fsSL https://tailscale.com/install.sh | sh

# Oder im Home Assistant SSH Add-on:
tailscale up
```

Dann:
```
https://dein-ha-host.ts.net:8000
```

---

## 📚 Häufig gestellte Fragen

### F: Brauche ich technische Kenntnisse?
**A:** Nein! Das Panel ist so gestaltet, dass Nicht-Techniker alles schaffen. Für fortgeschrittene Sachen (API, wp-cli) brauchst du Grundkenntnisse.

### F: Wie viele Websites kann ich hosten?
**A:** Theoretisch unbegrenzt (solange RAM/Speicher reichen). Erfahrungsgemäß: **5-10 WordPress-Sites** auf einem moderaten System problemlos.

### F: Sind meine Daten sicher?
**A:** Ja! Deine Daten bleiben auf deinem Home Assistant. Backups werden lokal gespeichert. Passwörter sind verschlüsselt.

### F: Kann ich die Sites von außen erreichen?
**A:** Ja, mit:
- **Tailscale** (einfach, sicher)
- **Wireguard** (manuell aber sicher)
- **HA Cloud Remote UI** (eingebaute HA-Lösung)
- **SSH-Tunnel** (für Experten)
- **Port-Forwarding** (nicht empfohlen, sicherheitsrisiko)

### F: Was ist wenn der Server runterfährt?
**A:** Add-on startet automatisch neu (wenn "Start on Boot" an ist). Backups bleiben erhalten.

### F: Kann ich Datenbanken backup?
**A:** Ja! Automatisch täglich. Auch manuell via API (`POST /api/sites/{name}/backup`).

### F: Performance?
**A:** Für kleine-mittlere Projekte sehr gut. Nicht für 100k+ requests/Stunde optimiert (dafür sind dann größere Server nötig).

---

## 🐛 Troubleshooting

### "WordPress-Installation fehlgeschlagen"
**Ursachen:**
- MariaDB läuft nicht → Add-on neu starten
- Nicht genug Speicherplatz → Speicher freimachen
- Netzwerkfehler beim WordPress-Download → Später erneut versuchen

**Lösung:**
```
1. Add-on neustarten
2. Logs überprüfen: Add-on Panel → "Logs" unten
3. Nochmal versuchen
```

### "Plugin-Installation funktioniert nicht"
**Lösung:**
```bash
# SSH in Container
docker exec -it <container-id> wp plugin install <slug> --activate
```

### "Site antwortet mit 404"
**Checken:**
```bash
# Health-Check
GET /api/sites/{name}/health

# Nginx Logs
docker logs <container-id> | grep nginx
```

### "Passwort vergessen"
**Lösung:**
```bash
# Neues Passwort setzen (als root in Container)
wp user update admin --prompt=user_pass
```

---

## 🤝 Beitragen

**HA WebHost ist Open-Source!** Fehler gefunden? Ideen? Improvements?

```bash
# Fork → PR senden
# Oder: Issues erstellen auf GitHub
```

**Gewünschte Beiträge:**
- Bug-Reports
- Feature-Requests
- Dokumentations-Verbesserungen
- Übersetzungen
- Themes/Plugins-Empfehlungen

---

## 📜 Lizenz

GPL-3.0 (Like WordPress!)

---

## 🙏 Credits

Basierend auf:
- 🏠 [Home Assistant](https://home-assistant.io/)
- 📝 [WordPress](https://wordpress.org/)
- 🗄️ [MariaDB](https://mariadb.org/)
- 🚀 [Caddy](https://caddyserver.com/)
- 🔷 [Nginx](https://nginx.org/)

---

## 📞 Support

- 📖 [Dokumentation](https://github.com/yourusername/ha-webhost/wiki)
- 🐛 [Issues](https://github.com/yourusername/ha-webhost/issues)
- 💬 [Discussions](https://github.com/yourusername/ha-webhost/discussions)
- 🏠 [Home Assistant Community](https://community.home-assistant.io/)

---

**Viel Spaß beim Hosten! 🚀**

*Made with ❤️ for Home Assistant enthusiasts*
