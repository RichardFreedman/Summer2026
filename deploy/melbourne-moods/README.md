# Deploying Melbourne Moods

Serves the `moodrec` Streamlit app at
<https://dhworkshops.researchsoftware.unimelb.edu.au/melbourne-moods/> behind a
single shared username/password, on the `workshops` server.

Stack: Docker Compose running Caddy (automatic HTTPS, basic auth, path
routing) in front of the Streamlit container. Nothing else is installed on
the host.

## First-time setup

1. Sync the code and start the stack:
   ```
   deploy/melbourne-moods/deploy.sh
   ```
   The first run stops because `.env` is missing. On the server:
   ```
   ssh workshops
   cd ~/melbourne-moods/deploy/melbourne-moods
   cp .env.example .env
   docker run --rm caddy:2 caddy hash-password --plaintext 'the-shared-password'
   nano .env   # paste API keys, user, and the hash (keep the hash in single quotes)
   ```
2. Run `deploy/melbourne-moods/deploy.sh` again. Caddy obtains a Let's
   Encrypt certificate on first request (ports 80 and 443 must be open in
   the cloud firewall / security group).

## Updating

Commit, then run `deploy/melbourne-moods/deploy.sh` again. It rsyncs the
tree and rebuilds only the app image.

## Adding another app on the same domain

1. Add a service to `docker-compose.yml`.
2. Copy the `handle /melbourne-moods/*` block in `Caddyfile` with a new
   prefix and upstream. Use `handle_path` instead of `handle` if the app
   does not know its own prefix (Streamlit does, via `--server.baseUrlPath`).
3. `docker compose up -d --build`.

## Useful commands (on the server)

```
docker compose logs -f melbourne-moods   # app logs
docker compose logs -f caddy             # TLS / auth / routing
docker compose restart melbourne-moods
```

## Notes

- Genre-fit and tag caches (`*_cache.json`) are baked into the image at
  build time; new entries written at runtime live in the container and are
  lost on rebuild. Fine for a demo; mount a volume if that matters.
- The shared login is HTTP basic auth at the Caddy layer, so it also covers
  Streamlit's websocket and static assets. Change it by regenerating the
  hash in `.env` and `docker compose restart caddy`.
