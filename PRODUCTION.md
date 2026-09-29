# Production WSGI runtime (Linode / VPS)

For the initial Namecheap shared-hosting test, use [CPANEL.md](CPANEL.md).
This Docker runtime requires a server with Docker access; it is not the cPanel deployment path.

Read the complete **Production Deployment Configuration** runbook in
[AGENT.md](AGENT.md#production-deployment-configuration) before using these files.
This runtime prepares the application server; it does not provision a public
deployment, database, Redis, TLS, media/static delivery, monitoring, or backups.

## Image and configuration

`Dockerfile.production` builds MySQL dependencies in a separate build stage and
runs Gunicorn as UID/GID 10001. Only application code and server configuration
are copied into the runtime. `.dockerignore` excludes local environments,
secrets, database dumps, media, and Git metadata from the build context.

`requirements-production.txt` adds pinned Gunicorn to the backend dependencies.
`gunicorn.conf.py` starts two synchronous workers on port 8000. Set
`WEB_CONCURRENCY` to a positive integer after measuring memory, request latency,
and database connection capacity. Requests have a 60-second worker timeout;
shutdown allows 30 seconds for active requests, with a 45-second container grace
period. No migration or seed command runs on server startup.

Access logs go to stdout and errors to stderr. Access logs contain source IP,
method, URL path, status, and duration, but omit query strings, headers, and
bodies. Apply your platform's access controls and retention policy to these logs.
Gunicorn's forwarded-header interpretation and administrative control socket are disabled so Django's Phase 28
proxy configuration remains authoritative. The reverse proxy must sanitize
forwarded headers and enforce request-size, buffering, and timeout limits.
See the [Gunicorn settings reference](https://gunicorn.org/reference/settings/).

## Standalone Compose topology

Use `compose.production.yml` on its own; never merge it with the development
Compose file. It binds to **127.0.0.1:8001** on the host, for a TLS reverse proxy
running on that same host. A proxy on another host or in another container needs
an explicitly configured private network instead. Never expose this HTTP port
directly to public clients.

Provision MySQL and Redis separately, on private addresses reachable from this
container. `localhost` inside the container is not the host. The development
Compose service names `mysql` and `redis` will not resolve on this separate
network unless an operator deliberately configures that networking.

Place real production configuration in a protected file outside the repository
(or adapt the platform to inject secrets directly). Set its absolute path:

```bash
export PRODUCTION_ENV_FILE=/absolute/path/to/protected/production.env
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml build web
docker compose -f compose.production.yml run --rm web python manage.py check
docker compose -f compose.production.yml run --rm web python manage.py check --deploy --tag security
docker compose -f compose.production.yml run --rm web python manage.py makemigrations --check --dry-run
docker compose -f compose.production.yml run --rm web python manage.py migrate --plan
```

Do not use `production.env.example` as the runtime file. Do not print the expanded
Compose configuration: it contains injected secrets. The Compose file forces
the production profile and debug off, and gives the container a read-only root
filesystem with a writable temporary directory.

After the runbook's verified database backup and controlled migration approval:

```bash
docker compose -f compose.production.yml run --rm web python manage.py migrate
docker compose -f compose.production.yml up -d web
```

Before public traffic, complete the runbook's real-origin HTTPS, CORS,
authentication, permissions, and throttling verification. Confirm graceful
shutdown and size the worker count against representative school workloads.
Keep the prior image available for application rollback; schema rollback requires
its own reviewed migration/restore procedure.

## Static files, storage, and probes

The image collects Django static assets during its build without production
secrets. Before starting public traffic, export the assets from the release
image to the host proxy's static directory (create that directory first):

```bash
docker compose -f compose.production.yml run --rm --no-deps web tar -C /app/staticfiles -cf - . | tar -xf - -C /srv/hopeful-future/static
```

Review `deploy/nginx.conf.example`, replace the reserved hostname and certificate
paths, run `nginx -t`, and reload through the host's service manager. It serves
static assets, sanitizes forwarded headers, limits authentication traffic, and
blocks public health/media paths. Its topology requires proxy trust enabled and
one proxy hop. Do not install it unchanged or combine it with another proxy
without reviewing header trust. Access logs omit queries and bodies; standard
Nginx error logs may contain request URLs and require restricted retention.

The `media` named volume persists private files at `/app/media` across container
replacement. Include it in backups. Do not use `docker compose down -v` on a
real deployment. No public media alias or new file-upload API is introduced.

`/health/live/` checks process responsiveness. `/health/ready/` checks SQL and a
short-lived cache write/read/delete. Both return minimal uncached JSON and accept
GET/HEAD only. These exact paths are HTTPS-redirect exempt for the internal
probe; the provided public proxy blocks them. Compose probes the actual WSGI
server using the configured allowed host. An unhealthy container is a signal
for monitoring, not an automatic restart policy.

## Optional worker

The `worker` Compose profile adds a non-root Celery worker and a targeted ping
health check. When introducing actual background tasks, set
`CELERY_TASK_ALWAYS_EAGER=False` in the VPS production environment and start:

```bash
docker compose -f compose.production.yml --profile worker up -d web worker
```

Result confirmation stays synchronous and transactional. Starting the worker
does not move that workflow to a queue. No worker is used on Namecheap shared
hosting. Both services rotate local container logs (five 10 MB files each).

## External acceptance gates

Provision real SQL/Redis services, DNS/TLS, backup scheduling and encrypted
storage, off-host log collection, monitoring and alert recipients. Test restoring
SQL and private media into an isolated environment and record the result.
Validate real-origin role workflows and graceful shutdown before traffic opens.
Local container log rotation is not centralized logging, and a successful image
build is not a verified public deployment. The existing `docker-compose.yml`
remains the development runtime.
