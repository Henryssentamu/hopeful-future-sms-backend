"""Production WSGI process settings; Django owns trusted HTTPS headers."""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
if workers < 1:
    raise ValueError("WEB_CONCURRENCY must be a positive integer")
worker_class = "sync"
timeout = 60
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
# Omit query strings, authorization headers, and request bodies from access logs.
access_log_format = '%(h)s %(m)s %(U)s %(s)s %(L)s'

# Keep HTTPS interpretation exclusively in Django's explicitly configured
# SECURE_PROXY_SSL_HEADER policy; Gunicorn must not trust additional headers.
secure_scheme_headers = {}
forwarded_allow_ips = ""
forwarder_headers = ""
# The read-only runtime does not need Gunicorn's administrative control socket.
control_socket_disable = True
