# Namecheap shared-hosting production test

This is the first deployment target; Linode will use `PRODUCTION.md` later.

Approved public addresses:

- Existing school website: `https://www.hopefulfuture.ac.ug/`
- Portal: `https://www.hopefulfuture.ac.ug/schoolsystem/`
- API base: `https://api.hopefulfuture.ac.ug/api`

`schoolsystem` is a directory on the existing website; only the API needs a new
subdomain. Confirm the API subdomain's DNS and SSL in cPanel. The existing school
website's files must not be replaced by this release.
Read the complete production configuration runbook in `AGENT.md` first.
Never deploy example secrets or domains. This document is a setup procedure,
not evidence that the hosting account has been provisioned or verified.

For the confirmed premium65 account, use private application root
`/home/sisitzyt/hopeful-future-sms`, API document root
`/home/sisitzyt/api.hopefulfuture.ac.ug`, and portal directory
`/home/sisitzyt/public_html/hopefulfuture.ac.ug/schoolsystem/`.
The school domain shares the account with main domain `sisit.it.com`.
Namecheap support confirmed sanitized protocol/client-IP forwarding for this
installation: use `DJANGO_TRUST_PROXY_SSL_HEADER=True` and `DRF_NUM_PROXIES=1`.
Reconfirm those values if the request path or proxy/CDN changes.

## Runtime

Use cPanel **Setup Python App**, Python **3.12**, application startup file
`passenger_wsgi.py`, and entry point `application`. Put the application root
outside public document roots. Set the application URL to the API subdomain
root, not `/api`, because Django already owns the `/api/` prefix.
Build a source-only archive locally with `python scripts/package_cpanel.py /tmp/sms-cpanel.zip` (the output must not already exist).
Upload and extract that archive in the private application root through SFTP or cPanel.
The packager includes only Python source, required dependency lists, and deployment guides/templates, excluding
`.git`, virtual environments, local `.env`, dumps, logs, and local data.

Passenger serves Django. Do not start Gunicorn, Docker, Redis, or a Celery
worker on this shared account. Results already run synchronously.
`DJANGO_CACHE_BACKEND=database` stores shared login-throttle state in MySQL's
`sms_cache` table across Passenger processes. It adds database traffic and is
intended for the initial modest-load test; move to Redis on Linode. Never use
process-local memory caching for production throttling.

Activate the exact virtual environment command shown by cPanel, then run:

```bash
python -m pip install -r requirements-cpanel.txt
```

This uses the project's existing PyMySQL driver fallback without requiring
system compiler packages. The server's MySQL/MariaDB version and SQL behavior
must pass the application checks and workflow smoke tests before use.

## Configuration

Create a dedicated database and user in cPanel; use the full account-prefixed
names assigned there. Grant that user access only to this database. Confirm the
SQL hostname with Namecheap; do not copy Docker's `mysql` hostname.

Set the variables from `cpanel.env.example` in cPanel's Python App environment
configuration. A protected `.env` file in the private application root is also
supported for command-line management operations. Use identical values for
Passenger and management commands. Do not put secrets in `public_html` or
paste them into shell command arguments, logs, or support tickets.

The backend allowed host is `api.hopefulfuture.ac.ug`. CORS and CSRF origins
are `https://www.hopefulfuture.ac.ug` with no `/schoolsystem` path: origins
contain only scheme and host. Enable valid HTTPS for both hosts.

From the frontend repository, build the portal:

```bash
VITE_API_BASE_URL=https://api.hopefulfuture.ac.ug/api npm run build:cpanel
```

Upload the **contents** of `dist`, including its hidden `.htaccess`, only into
`schoolsystem/` under the existing website's actual document root. Do not upload
into the website root or overwrite its `index` or `.htaccess` files. The supplied
rewrite file stays inside `schoolsystem/` and sends non-file routes to that
folder's `index.html`. The build sets Vite assets and React Router to the same
`/schoolsystem/` base; authentication redirects and the school badge use it too.

Inspect the existing website's parent rewrite rules before release. If a CMS
catch-all intercepts `/schoolsystem/...`, back up its `.htaccess` and insert a
scoped exclusion before that catch-all, preserving its other directives:

```apache
RewriteRule ^schoolsystem(?:/|$) - [L]
```

This is conditional on the actual site's configuration; never replace the
existing root rules wholesale. Verify both the public school homepage and a
direct portal route such as `/schoolsystem/students` after release. Keep the
portal SPA rewrite out of the API domain.

For HTTPS, first confirm that Passenger supplies Django's native HTTPS WSGI
indicator. In that topology use `DJANGO_TRUST_PROXY_SSL_HEADER=False` and
`DRF_NUM_PROXIES=0`. If the provider instead uses forwarded headers, have support
confirm header sanitization and the exact proxy count before changing these
values. Verify HTTP redirects and HTTPS succeeds; never disable SSL redirect
to hide a loop.

Set `DJANGO_STATIC_ROOT` to an absolute `static` directory under the API domain's
actual public document root. Set `DJANGO_MEDIA_ROOT` to a private directory
outside all document roots. Only collected static assets are public. Student
photos now upload from a device and are served by the authenticated student
photo endpoint. Install the updated requirements (including Pillow), make this
private directory writable by Passenger, and include it in backups. Do not
expose private media with a public directory alias.

The application enables `STRICT_TRANS_TABLES` for each database connection,
preserving other server SQL modes. If preflight reports `mysql.W002`, update
`config/settings.py` from the current release before applying migrations;
do not silence the warning or change the shared server’s global SQL mode.

## Controlled release

Keep the app unavailable to users while preparing the database. Activate the
cPanel virtual environment and load the same production settings, then run:

```bash
python manage.py check
python manage.py check --deploy --tag security
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

Only the two staged-HSTS advisories documented in `AGENT.md` are expected.
Before updating an existing database, create and verify a backup. Then:

```bash
python manage.py migrate
python manage.py load_advanced_subjects
python manage.py createcachetable
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Create the superuser only on the first install and enter its password through
the interactive prompt. Do not run demo seeding in production. Restart the app
using cPanel's Python App controls after every code/environment change.

Check HTTPS `/health/live/` (process) and `/health/ready/` (SQL plus cache),
Django Admin styling, real-origin CORS/login/refresh/logout, each role's allowed
read and denied cross-role read, and a result confirmation/report card. Verify a
device photo upload and authorized display, anonymous/unauthorized photo denial,
receipt lookup, an opening balance, and automatic excess-payment allocation.
The catalogue loader preserves existing papers; configure teaching allocations
and paper definitions before enrollment. Review held legacy receipts against
original historical enrollment/charges before releasing their credit.
Readiness returns only `ok` or HTTP 503 `unavailable`, never configuration or
school records. It is excluded from HTTP-to-HTTPS redirects for container
compatibility; configure external monitors to use HTTPS explicitly.

## Backups and monitoring

Before accepting school records, configure the account's backup feature or a
provider-approved backup schedule. Include SQL, the private media directory,
release identifier, and separately protected configuration. Keep an encrypted
copy off the hosting account; a backup stored only on the account is not a
recovery plan. Choose retention and recovery targets with the school.

Test restoration into a separate, empty database and private media directory:
restore SQL/files, point an isolated app at them, run migration checks, verify
record counts and representative results/payments/permissions, and record the
backup date, restore duration, and outcome. Never restore a test over live data.
The cache table can be recreated; do not rely on cache content as business data.

Use an HTTPS monitor for `/health/ready/` and certificate expiry with an agreed
alert recipient. Review cPanel resource-limit failures and Passenger errors;
confirm the provider's log access and retention. Application exceptions must
not be copied into public tickets with credentials or student information.
Any custom cron checks must respect Namecheap's minimum five-minute interval.
Edge rate limits and centralized log shipping require provider-supported
facilities; confirm them with the account rather than assuming root access.

These external services, backup scheduling, restore rehearsal, and real-domain
smoke tests are deployment acceptance gates and cannot be certified locally.

## Move to Linode

Use the Docker/Gunicorn and optional worker runtime in `PRODUCTION.md`, private
MySQL/Redis, `DJANGO_CACHE_BACKEND=redis`, and the sanitized TLS proxy template.
Take a final consistent backup while writes are paused, restore to Linode,
verify before switching DNS, and preserve the Namecheap copy for rollback.
Do not allow both deployments to receive independent writes during cutover.
Rebuild the frontend only if its public API URL changes. Keep result confirmation
synchronous unless a separate workflow design explicitly changes it.

## Provider references

- [Namecheap Django deployment](https://www.namecheap.com/support/knowledgebase/article.aspx/10753/2182/how-to-deploy-a-django-application-on-shared-servers/)
- [Python App configuration](https://www.namecheap.com/support/knowledgebase/article.aspx/10048/2182/how-to-work-with-python-app/)
- [Shared-host resource/process restrictions](https://www.namecheap.com/support/knowledgebase/article.aspx/157/22/do-you-have-any-server-resource-restrictions/)
- [Available server software](https://www.namecheap.com/support/knowledgebase/article.aspx/129/22/what-version-of-the-software-is-used-on-your-servers/)


### O-Level catalogue update

After installing the 2026-10-08 O-Level backend update and restarting the Python app, use **Load NCDC O-Level subjects** in the updated portal, or run `DJANGO_ENVIRONMENT=production python manage.py load_ordinary_subjects`. This is repeatable and preserves school configuration. Configure class-specific subject choices and papers separately; the menu does not enroll students. No migration or pip install is required for this update.
