from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

from . import config


class ChecksumError(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, expected_bytes: int, attempts: int = 3) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "adoption-lens"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as out:
                total = int(resp.headers.get("Content-Length") or expected_bytes)
                done, last = 0, 0.0
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if time.time() - last > 1.0:
                        print(f"\r  {dest.name}: {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", file=sys.stderr)
                        last = time.time()
            print(file=sys.stderr)
            part.replace(dest)
            return
        except Exception:
            part.unlink(missing_ok=True)
            if attempt == attempts:
                raise
            time.sleep(2 * attempt)


def fetch(raw_dir: Path = config.DATA_RAW, sources: dict | None = None, force: bool = False) -> dict:
    sources = config.SOURCES if sources is None else sources
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for key, spec in sources.items():
        dest = raw_dir / spec["file"]
        if dest.exists() and not force and sha256_of(dest) == spec["sha256"]:
            print(f"{spec['file']}: already downloaded and verified")
        else:
            print(f"{spec['file']}: downloading from {spec['url']}")
            _download(spec["url"], dest, spec["bytes"])
            got = sha256_of(dest)
            if got != spec["sha256"]:
                dest.unlink()
                raise ChecksumError(f"{spec['file']}: expected sha256 {spec['sha256']}, got {got}")
            print(f"{spec['file']}: verified")
        manifest[key] = {"file": spec["file"], "url": spec["url"], "sha256": spec["sha256"], "bytes": dest.stat().st_size}
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    fetch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
