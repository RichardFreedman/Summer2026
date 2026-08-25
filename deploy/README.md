# Deployment

Everything runs on the `workshops` server (Ubuntu, Docker only) from a git
clone of this repo at `/volume/summer2026`, behind a single shared Caddy at
<https://dhworkshops.researchsoftware.unimelb.edu.au/>. Each app gets a path
prefix rather than a subdomain, so adding an app never touches DNS.

```
deploy/
  caddy/                 shared reverse proxy: TLS, auth, path routing
    Caddyfile            domain block; imports sites/*.caddy
    sites/<app>.caddy    one routing snippet per app
    .env.example         one USER / PASSWORD_HASH pair per protected app
  melbourne-moods/       the moodrec Streamlit app
    docker-compose.yml   app container only, joins the "web" network
    .env.example         API keys, GENRE_MODE
```

## Apps

| Path | App | Source | Login |
|---|---|---|---|
| `/melbourne-moods/` | Melbourne Moods | `moodrec/` | shared user + password (`deploy/caddy/.env`) |

## How deploys work

Each `deploy/<x>/deploy.sh` pulls `main` in the server clone and then runs
`docker compose up` for that stack. Only code merged to `main` gets deployed;
work on a branch, open a PR, merge, then deploy. `.env` files are gitignored
and untouched by pulls.

## First-time setup of the server

```
ssh workshops
  sudo mkdir -p /volume/summer2026 && sudo chown $USER /volume/summer2026
  git clone https://github.com/dan321/Summer2026.git /volume/summer2026
  cd /volume/summer2026/deploy/caddy && cp .env.example .env
  docker run --rm caddy:2 caddy hash-password --plaintext 'the-password'
  nano .env                         # paste the hash in single quotes
deploy/caddy/deploy.sh              # creates the "web" network, starts Caddy, gets a certificate
```
Ports 80 and 443 must be open in the cloud firewall for the certificate.

Then each app, e.g.:
```
deploy/melbourne-moods/deploy.sh    # stops: .env missing
ssh workshops
  cd /volume/summer2026/deploy/melbourne-moods && cp .env.example .env && nano .env
deploy/melbourne-moods/deploy.sh
```

## Updating

- App code changed: commit, push, `deploy/<app>/deploy.sh` (pull + rebuild that app only).
- Routing changed: commit, push, `deploy/caddy/deploy.sh` (pull + reload).
- Passwords changed (`deploy/caddy/.env` on the server): `docker compose up -d --force-recreate caddy`.
- `.env` changed on the server: `docker compose up -d --force-recreate <service>`
  in that directory. `docker compose restart` does not reload `.env`.

## Adding another app

1. Make it serve under a prefix (Streamlit: `--server.baseUrlPath=<app>`;
   otherwise use `handle_path` in the snippet to strip it).
2. Add `deploy/<app>/docker-compose.yml` with no published ports and
   `networks: [web]` (copy `deploy/melbourne-moods/`).
3. Add `deploy/caddy/sites/<app>.caddy` (copy `melbourne-moods.caddy`). For a
   password, add a `<APP>_USER` / `<APP>_PASSWORD_HASH` pair to `deploy/caddy/.env`.
4. `deploy/caddy/deploy.sh`, then `deploy/<app>/deploy.sh`.

## Notes

- Basic auth at the Caddy layer covers Streamlit's websocket and static assets
  too. Each app can have its own credentials.
- Melbourne Moods bakes its `*_cache.json` files into the image; entries written
  at runtime live in the container and are lost on rebuild.
- Useful: `docker compose logs -f` in either directory.
