# 📚 Code-Beispiele für HA WebHost

## Python-Beispiele

### WordPress-Site erstellen & Plugins installieren

```python
import requests
import json

BASE_URL = "http://ha-server.local"

# 1. WordPress-Site erstellen
def create_wordpress_site(name, blog_name, admin_email):
    response = requests.post(
        f"{BASE_URL}/api/sites/wordpress",
        data={
            "name": name,
            "blog_name": blog_name,
            "admin_email": admin_email
        }
    )
    
    if response.status_code == 201:
        site = response.json()
        print(f"✅ Site erstellt!")
        print(f"Admin: {site.get('wordpress_admin_user')}")
        print(f"Email: {site.get('wordpress_admin_email')}")
        return site
    else:
        print(f"❌ Fehler: {response.json()}")
        return None

# 2. Popular Plugins installieren
def install_popular_plugins(site_name):
    plugins = [
        ("yoast-seo", "SEO Optimization"),
        ("elementor", "Page Builder"),
        ("jetpack", "Security & Stats"),
        ("woocommerce", "E-Commerce"),
    ]
    
    for slug, name in plugins:
        response = requests.post(
            f"{BASE_URL}/api/sites/{site_name}/plugins/install",
            data={"slug": slug, "activate": True}
        )
        
        if response.status_code == 200:
            print(f"✅ {name} installiert")
        else:
            print(f"❌ {name} fehlgeschlagen")

# 3. Updates prüfen & installieren
def check_and_install_updates(site_name):
    # Prüfen
    updates = requests.get(
        f"{BASE_URL}/api/sites/{site_name}/updates/check"
    ).json()
    
    print(f"Updates verfügbar:")
    print(f"  - Core: {updates.get('core_update_available', False)}")
    print(f"  - Plugins: {updates.get('plugin_updates_available', 0)}")
    print(f"  - Themes: {updates.get('theme_updates_available', 0)}")
    
    # Installieren
    if updates.get('total_updates', 0) > 0:
        response = requests.post(
            f"{BASE_URL}/api/sites/{site_name}/updates/install",
            params={"core": True, "plugins": True, "themes": True}
        )
        print(f"Updates installiert: {response.json()}")

# 4. Health-Check
def check_site_health(site_name):
    health = requests.get(
        f"{BASE_URL}/api/sites/{site_name}/health"
    ).json()
    
    if health['healthy']:
        print(f"✅ Site is healthy!")
    else:
        print(f"❌ Issues found:")
        for issue in health.get('issues', []):
            print(f"  - {issue}")

# 5. Backup erstellen
def backup_site(site_name):
    response = requests.post(
        f"{BASE_URL}/api/sites/{site_name}/backup"
    ).json()
    
    print(f"Backup erstellt:")
    print(f"  - Datei: {response['backup_file']}")
    print(f"  - Größe: {response['size_mb']} MB")

# Beispiel-Aufruf
if __name__ == "__main__":
    # Site erstellen
    site = create_wordpress_site(
        "mein-projekt",
        "Mein toller Blog",
        "ich@example.com"
    )
    
    if site:
        # Plugins installieren
        install_popular_plugins("mein-projekt")
        
        # Updates prüfen
        check_and_install_updates("mein-projekt")
        
        # Health-Check
        check_site_health("mein-projekt")
        
        # Backup
        backup_site("mein-projekt")
```

### Plugin-Suche & Installation

```python
import requests

BASE_URL = "http://ha-server.local"

def search_and_install_plugin(site_name, search_term):
    """Sucht ein Plugin und installiert das beste Ergebnis."""
    
    # Suche
    search_results = requests.get(
        f"{BASE_URL}/api/sites/{site_name}/plugins/search",
        params={"q": search_term}
    ).json()
    
    if not search_results:
        print(f"Keine Plugins gefunden für '{search_term}'")
        return
    
    # Beste Ergebnis anzeigen
    best = search_results[0]
    print(f"\n🔍 Beste Ergebnis:")
    print(f"  Name: {best['name']}")
    print(f"  Rating: {best['rating']}/100")
    print(f"  Aktive Installationen: {best['active_installs']:,}")
    print(f"  Version: {best['version']}")
    
    # Installieren
    response = requests.post(
        f"{BASE_URL}/api/sites/{site_name}/plugins/install",
        data={"slug": best['slug'], "activate": True}
    )
    
    if response.status_code == 200:
        print(f"✅ Plugin '{best['name']}' installiert!")
    else:
        print(f"❌ Installation fehlgeschlagen")

# Beispiel
search_and_install_plugin("mein-projekt", "backup")
```

## JavaScript/Fetch-Beispiele

### Site-Liste laden & darstellen

```javascript
const BASE_URL = "http://ha-server.local";

async function loadAndDisplaySites() {
    try {
        // Sites laden
        const response = await fetch(`${BASE_URL}/api/sites`);
        const sites = await response.json();
        
        // HTML generieren
        const html = sites.map(site => `
            <div class="site-card">
                <h3>${site.name}</h3>
                <p>Quelle: ${site.source_type}</p>
                <span class="badge ${site.status}">${site.status}</span>
                <a href="/sites/${site.name}/" target="_blank">Öffnen</a>
            </div>
        `).join("");
        
        document.getElementById("sites-container").innerHTML = html;
    } catch (error) {
        console.error("Fehler beim Laden:", error);
    }
}

loadAndDisplaySites();
```

### WordPress-Site mit Health-Check erstellen

```javascript
async function createWordPressSite(name, blogName, email) {
    const formData = new FormData();
    formData.append("name", name);
    formData.append("blog_name", blogName);
    formData.append("admin_email", email);
    
    try {
        // Erstellen
        const response = await fetch(
            `${BASE_URL}/api/sites/wordpress`,
            { method: "POST", body: formData }
        );
        
        if (!response.ok) throw new Error(await response.text());
        
        const site = await response.json();
        console.log(`✅ Site erstellt: ${site.name}`);
        
        // Health-Check in 5 Sekunden starten
        await new Promise(r => setTimeout(r, 5000));
        
        // Health-Check
        const healthResponse = await fetch(
            `${BASE_URL}/api/sites/${name}/health`
        );
        const health = await healthResponse.json();
        
        if (health.healthy) {
            console.log("✅ Site ist healthy!");
            return site;
        } else {
            console.warn("⚠️ Issues:", health.issues);
            return site;
        }
    } catch (error) {
        console.error("❌ Fehler:", error);
    }
}
```

### Real-Time Plugin-Installation mit Progress

```javascript
async function installPluginWithProgress(siteName, pluginSlug) {
    const progressDiv = document.getElementById("progress");
    
    try {
        progressDiv.textContent = "Suche Plugin...";
        
        // Plugin suchen
        const searchResponse = await fetch(
            `${BASE_URL}/api/sites/${siteName}/plugins/search?q=${pluginSlug}`
        );
        const results = await searchResponse.json();
        
        if (results.length === 0) {
            progressDiv.textContent = "❌ Plugin nicht gefunden";
            return;
        }
        
        const plugin = results[0];
        progressDiv.textContent = `Installiere ${plugin.name}...`;
        
        // Installieren
        const formData = new FormData();
        formData.append("slug", plugin.slug);
        formData.append("activate", true);
        
        const installResponse = await fetch(
            `${BASE_URL}/api/sites/${siteName}/plugins/install`,
            { method: "POST", body: formData }
        );
        
        const result = await installResponse.json();
        
        if (result.status === "success") {
            progressDiv.textContent = `✅ ${plugin.name} installiert!`;
        } else {
            progressDiv.textContent = `❌ Installation fehlgeschlagen`;
        }
    } catch (error) {
        progressDiv.textContent = `❌ Fehler: ${error.message}`;
    }
}
```

## Bash/cURL Beispiele

### WordPress-Site via cURL erstellen

```bash
#!/bin/bash

SITE_NAME="mein-blog"
BLOG_NAME="Mein persönlicher Blog"
ADMIN_EMAIL="ich@example.com"
BASE_URL="http://ha-server.local"

# Site erstellen
curl -X POST "$BASE_URL/api/sites/wordpress" \
  -d "name=$SITE_NAME" \
  -d "blog_name=$BLOG_NAME" \
  -d "admin_email=$ADMIN_EMAIL"

echo "✅ WordPress-Site erstellt!"
echo "URL: $BASE_URL/sites/$SITE_NAME/"
```

### Plugins in Bulk installieren

```bash
#!/bin/bash

SITE_NAME="$1"
BASE_URL="http://ha-server.local"

PLUGINS=(
    "yoast-seo"
    "elementor"
    "jetpack"
    "all-in-one-wp-migration"
)

for plugin in "${PLUGINS[@]}"; do
    echo "Installiere $plugin..."
    curl -X POST "$BASE_URL/api/sites/$SITE_NAME/plugins/install" \
      -d "slug=$plugin" \
      -d "activate=true"
    echo ""
done

echo "✅ Alle Plugins installiert!"
```

### Tägliche Backup-Cronjob

```bash
#!/bin/bash

BASE_URL="http://ha-server.local"
SITES_TO_BACKUP=("blog" "portfolio" "galerie")

for site in "${SITES_TO_BACKUP[@]}"; do
    echo "[$(date)] Backup: $site"
    
    curl -X POST "$BASE_URL/api/sites/$site/backup" \
      -s | jq '.backup_file'
done

echo "[$(date)] Backups abgeschlossen"
```

### Health-Check Monitor

```bash
#!/bin/bash

BASE_URL="http://ha-server.local"
CHECK_INTERVAL=3600  # Stündlich

while true; do
    echo "[$(date)] Health-Check läuft..."
    
    # Alle WordPress-Sites prüfen
    sites=$(curl -s "$BASE_URL/api/sites" | jq -r '.[] | select(.source_type=="wordpress") | .name')
    
    for site in $sites; do
        health=$(curl -s "$BASE_URL/api/sites/$site/health")
        healthy=$(echo $health | jq '.healthy')
        
        if [ "$healthy" != "true" ]; then
            echo "⚠️ $site ist UNHEALTHY!"
            echo $health | jq '.issues'
        fi
    done
    
    sleep $CHECK_INTERVAL
done
```

## Automatisierungs-Beispiele

### Auto-Update Scheduler

```python
import schedule
import requests
import time

BASE_URL = "http://ha-server.local"

def update_all_sites():
    """Updated alle WordPress-Sites."""
    sites = requests.get(f"{BASE_URL}/api/sites").json()
    
    for site in sites:
        if site['source_type'] == 'wordpress':
            print(f"Updating {site['name']}...")
            
            requests.post(
                f"{BASE_URL}/api/sites/{site['name']}/updates/install",
                params={"core": True, "plugins": True, "themes": True}
            )
            
            print(f"✅ {site['name']} updated")

def backup_all_sites():
    """Backup aller WordPress-Sites."""
    sites = requests.get(f"{BASE_URL}/api/sites").json()
    
    for site in sites:
        if site['source_type'] == 'wordpress':
            requests.post(f"{BASE_URL}/api/sites/{site['name']}/backup")
            print(f"✅ Backup: {site['name']}")

# Schedule Jobs
schedule.every().day.at("02:00").do(update_all_sites)  # 2 AM tägliche Updates
schedule.every().day.at("03:00").do(backup_all_sites)  # 3 AM täglich Backup

# Starten
while True:
    schedule.run_pending()
    time.sleep(60)
```

### Monitoring & Alerts

```python
import requests
import smtplib
from email.mime.text import MIMEText

BASE_URL = "http://ha-server.local"
ADMIN_EMAIL = "admin@example.com"

def send_alert(subject, message):
    """Sendet Email-Alert."""
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = ADMIN_EMAIL
    msg['To'] = ADMIN_EMAIL
    
    # SMTP-Server (anpassen!)
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(ADMIN_EMAIL, "app-password")
        server.send_message(msg)

def check_all_sites():
    """Prüft alle Sites und sendet Alerts bei Problemen."""
    sites = requests.get(f"{BASE_URL}/api/sites").json()
    
    for site in sites:
        if site['source_type'] == 'wordpress':
            # Health-Check
            health = requests.get(
                f"{BASE_URL}/api/sites/{site['name']}/health"
            ).json()
            
            if not health['healthy']:
                send_alert(
                    f"❌ {site['name']} ist down!",
                    f"Issues: {', '.join(health['issues'])}"
                )
            
            # Updates prüfen
            updates = requests.get(
                f"{BASE_URL}/api/sites/{site['name']}/updates/check"
            ).json()
            
            if updates.get('total_updates', 0) > 5:
                send_alert(
                    f"📦 {site['name']} hat {updates['total_updates']} Updates",
                    "Bitte manuell überprüfen"
                )

# Starten
check_all_sites()
```

---

## 🚀 Mehr Ideen?

Möchtest du deine Beispiele hinzufügen? Erstelle einen PR oder ein Issue!
