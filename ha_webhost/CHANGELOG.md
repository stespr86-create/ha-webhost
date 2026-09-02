# Changelog

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
