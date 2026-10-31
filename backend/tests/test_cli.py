"""Phase 4: the CLI drives the real API (TestClient stands in for the network)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from app import cli

from .conftest import AUTHOR, AUTHOR_ID, capture


class _Borrowed:
    """Lend the running TestClient without re-entering its lifespan."""

    def __init__(self, client) -> None:
        self.client = client

    def __enter__(self):
        return self.client

    def __exit__(self, *exc) -> None:
        return None


@pytest.fixture
def run(client, monkeypatch):
    monkeypatch.setattr(cli, "make_client", lambda: _Borrowed(client))
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: True)
    runner = CliRunner()

    def invoke(*args: str, input: str | None = None):
        return runner.invoke(cli.app, list(args), input=input)

    return invoke


def test_bulk_archive_then_pending_list(run, client, tmp_path):
    capture(client)
    urls = tmp_path / "urls.txt"
    urls.write_text(
        "# yorum satırı\n"
        + "\n".join(f"https://x.com/{AUTHOR}/status/18300000000000000{i:02d}" for i in range(3))
        + "\nhttps://x.com/baska/status/1\n",
        encoding="utf-8",
    )
    declined = run("bulk-archive", "--handle", AUTHOR, "--urls-file", str(urls), input="n\n")
    assert declined.exit_code == 0 and client.get("/api/pending").json() == []

    result = run("bulk-archive", "--handle", f"@{AUTHOR}", "--urls-file", str(urls), "--yes")
    assert result.exit_code == 0, result.output
    assert "3 gönderi sıraya alındı" in result.output and "1 bağlantı atlandı" in result.output
    listed = run("pending", "list")
    assert listed.output.count("https://x.com/") == 3


def test_archive_manual_loop_rejects_then_accepts(run, client):
    capture(client)
    worker = client.app.state.worker
    while worker.tick():
        pass
    jobs = client.get("/api/archive/jobs", params={"status": "manual_pending"}).json()
    assert len(jobs) == 2  # x.com: both services manual-first

    pending = run("archive", "pending")
    assert "ADR-025" in pending.output

    paste = "https://example.com/nope\nhttps://web.archive.org/web/20261031120000/https://x.com/a/status/1\n\n"
    result = run("archive", "manual", "--no-browser", input=paste)
    assert result.exit_code == 0, result.output
    assert "Kabul edilmedi" in result.output and "1 iş tamamlandı" in result.output
    statuses = sorted(j["status"] for j in client.get("/api/archive/jobs").json())
    assert statuses == ["manual_done", "manual_pending"]


def test_export_manifest_verify_exit_codes(run, client, settings, tmp_path):
    capture(client)
    ok = run("export", "manifest", "--verify", "-o", str(tmp_path / "m.json"))
    assert ok.exit_code == 0 and json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))["all_ok"]
    victim = settings.data_dir / "evidence" / f"VK1-{AUTHOR_ID}" / f"{AUTHOR_ID}-0001.png"
    victim.write_bytes(victim.read_bytes() + b"\x00")
    bad = run("export", "manifest", "--verify")
    assert bad.exit_code == 1 and "MISMATCH" in bad.output


def test_errors_are_readable(run):
    result = run("pending", "archive-only", "999", "--yes")
    assert result.exit_code == 1 and "Hata (404)" in result.output
