import hashlib
import http.server
import threading
from functools import partial

import pytest

from adoption_lens.fetch import ChecksumError, fetch, sha256_of


@pytest.fixture()
def server(tmp_path):
    root = tmp_path / "served"
    root.mkdir()
    payload = b"geo_id,value\r\nCA,1\r\n" * 5000
    (root / "file.csv").write_bytes(payload)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/file.csv", payload
    httpd.shutdown()


def _spec(url, payload, sha=None):
    return {"one": {"file": "file.csv", "url": url, "bytes": len(payload), "sha256": sha or hashlib.sha256(payload).hexdigest()}}


def test_download_is_verified_and_recorded(server, tmp_path):
    url, payload = server
    out = tmp_path / "raw"
    manifest = fetch(out, _spec(url, payload))
    assert (out / "file.csv").read_bytes() == payload
    assert manifest["one"]["sha256"] == sha256_of(out / "file.csv")
    assert (out / "manifest.json").exists()


def test_an_existing_verified_file_is_not_downloaded_again(server, tmp_path):
    url, payload = server
    out = tmp_path / "raw"
    fetch(out, _spec(url, payload))
    stamp = (out / "file.csv").stat().st_mtime_ns
    fetch(out, _spec("http://127.0.0.1:1/unreachable.csv", payload))
    assert (out / "file.csv").stat().st_mtime_ns == stamp


def test_a_checksum_mismatch_raises_and_removes_the_file(server, tmp_path):
    url, payload = server
    out = tmp_path / "raw"
    with pytest.raises(ChecksumError):
        fetch(out, _spec(url, payload, sha="0" * 64))
    assert not (out / "file.csv").exists()
    assert not list(out.glob("*.part"))
