# Grenville Capitals — deployment

Two hosts, one box, one shared Caddy:

| | |
|---|---|
| Marketing site | `https://grenvillecapitals.com` (+ `www` → 301 apex) — static, served by Caddy `file_server` |
| App | `https://dashboard.grenvillecapitals.com` — Django, `grenville-backend` container |
| Host | Contabo VPS #1, `156.67.28.100` (`ssh root@…`) |
| Repo on host | `/opt/grenville/repo` |
| Shared compose | `/opt/swifteagle/docker-compose.yml` (service `grenville`) |
| Shared Caddyfile | `/opt/swifteagle/Caddyfile` |
| Docker network | `swifteagle-net` — `expose: 8000`, **no published host port** |
| Database | Railway Postgres, project `summitteachable-db`, service `Postgres-bC0j`, public proxy `junction.proxy.rlwy.net:25592` |
| Uploads | named volume `swifteagle_grenville_media` → `/app/media` |
| Mail | Resend, sending domain `noreply.grenvillecapitals.com` |

This box also runs swifteagle, provena, webwave, bloomvest, summitteachable and
swiftexpress. **Never start a second Caddy**, and never `docker compose down -v` —
`caddy_data` holds the Let's Encrypt certificates for *every* site here.

## Deploy a change

```bash
# from this repo
rsync -az --delete \
  --exclude '.git' --exclude staticfiles --exclude venv --exclude __pycache__ \
  --exclude '.env' --exclude '.env.*' --exclude db.sqlite3 --exclude media \
  ./ root@156.67.28.100:/opt/grenville/repo/

# frontend only: nothing else to do, Caddy serves it straight off the bind mount.
# backend:
ssh root@156.67.28.100 'cd /opt/swifteagle && docker compose up -d --build grenville'
```

## Caddy

`caddy reload`, **never** `caddy restart` — restarting has taken sibling sites down before:

```bash
ssh root@156.67.28.100 'docker exec swifteagle-caddy caddy reload --config /etc/caddy/Caddyfile'
```

Recreating the Caddy *container* (`docker compose up -d caddy`) is only needed when adding a
new bind mount. It drops all sites for a few seconds; named volumes and certs survive.

## Env

`/opt/grenville/repo/backend/.env.prod`, mode 600, never committed. Keys are in
`backend/.env.example`. Two traps:

- `DEBUG` **defaults to True** in `config/settings.py` — it must be set explicitly.
- Keep `$` out of `SECRET_KEY`: Compose interpolates it and silently mangles the value.

## Verify after deploying

```bash
ssh root@156.67.28.100 '
  docker ps --filter name=grenville-backend --format "{{.Names}} {{.Status}}"
  docker logs grenville-backend 2>&1 | tail -20'

curl -sI https://grenvillecapitals.com/ | head -1
curl -sI https://dashboard.grenvillecapitals.com/auth/login/ | head -1

# regression: every sibling must still answer
for h in swifteagledelivery.info bloomvestcapital.com summitteachable.com \
         provenadigitalassets.com swiftexpresslogistics.info; do
  echo "$h $(curl -s -o /dev/null -w '%{http_code}' https://$h/)"
done
```

## Known gaps

- No inbound mailbox: the domain has no apex MX, so mail *to* `@grenvillecapitals.com` bounces.
- `faqs/` still explains FDIC deposit insurance as though it applies to this bank.
- Team page, news items and the marketing imagery are placeholders inherited from the
  scrape source and need real content before this is a finished product.
