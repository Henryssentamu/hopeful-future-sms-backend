"""Probe the actual WSGI server using its configured allowed host."""

import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    host = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")[0].strip().lstrip(".")
    request = Request("http://127.0.0.1:8000/health/ready/", headers={"Host": host})
    try:
        with urlopen(request, timeout=5) as response:
            return 0 if response.status == 200 else 1
    except (HTTPError, URLError, TimeoutError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
