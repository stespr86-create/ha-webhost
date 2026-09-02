# HA WebHost

Statisches Website-Hosting direkt in Home Assistant – als schlankes MVP für
Systeme mit begrenzten Ressourcen (getestet für ~4 GB RAM Zielhardware).

Details zu Funktionsumfang, bekannten Einschränkungen und Roadmap: siehe
[DOCS.md](DOCS.md).

## Schnellstart (lokale Entwicklung ohne HA)

Das Backend lässt sich auch ohne Home Assistant lokal testen:

```bash
cd ha_webhost/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p /tmp/ha_webhost_data/sites   # ersetzt /data für lokale Tests
DATA_DIR=/tmp/ha_webhost_data uvicorn main:app --reload --port 8001
```

> Hinweis: `core/config.py` ist aktuell fest auf `/data` verdrahtet (wie im
> Add-on-Kontext). Für lokale Tests ohne Container entweder `/data` lokal
> anlegen (`sudo mkdir -p /data && sudo chown $USER /data`) oder
> `core/config.py` temporär anpassen.

## Als Home Assistant Add-on

Siehe [DOCS.md](DOCS.md#installation-als-lokales-add-on-repository).
