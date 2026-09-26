"""Build a source-only cPanel release archive without local data or secrets."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILES = (
    "manage.py", "passenger_wsgi.py", "requirements-cpanel.txt",
    "requirements-local.txt", "CPANEL.md", "AGENT.md", "AGENTS.md",
    "cpanel.env.example",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New zip archive path; existing files are never overwritten")
    args = parser.parse_args()
    files = [ROOT / name for name in RELEASE_FILES]
    for directory in ("apps", "config"):
        files.extend(sorted((ROOT / directory).rglob("*.py")))
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            parser.error("Release sources must be regular files inside the repository.")
    with ZipFile(args.output, "x", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
    print(f"Created {args.output} with {len(files)} source/documentation files; no runtime configuration or data.")


if __name__ == "__main__":
    main()
