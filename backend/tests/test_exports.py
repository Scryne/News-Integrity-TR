"""Phase 5: exports and the tamper test."""

from __future__ import annotations

import csv
import io

from .conftest import AUTHOR, AUTHOR_ID, capture, meta


def test_manifest_lists_every_file_with_hashes(client):
    capture(client)
    capture(client, meta(crop_failed=True, post_id="1811111111111111112"))
    manifest = client.get("/api/exports/manifest").json()
    roles = [(e["evidence_id"], e["role"]) for e in manifest["entries"]]
    assert roles == [(1, "primary"), (1, "viewport"), (1, "sidecar"), (2, "primary"), (2, "sidecar")]
    assert manifest["verified"] is False and "mismatches" not in manifest


def test_tamper_one_byte_flags_exactly_that_file(client, settings):
    capture(client)
    capture(client, meta(post_id="1811111111111111112"))
    clean = client.get("/api/exports/manifest", params={"verify": "true"}).json()
    assert clean["all_ok"] is True and clean["mismatches"] == [] and clean["untracked"] == []

    victim = settings.data_dir / "evidence" / f"VK1-{AUTHOR_ID}" / f"{AUTHOR_ID}-0002-viewport.png"
    data = bytearray(victim.read_bytes())
    data[-1] ^= 0x01
    victim.write_bytes(bytes(data))

    report = client.get("/api/exports/manifest", params={"verify": "true"}).json()
    assert report["all_ok"] is False
    assert [m["path"] for m in report["mismatches"]] == [victim.relative_to(settings.data_dir).as_posix()]
    assert report["mismatches"][0]["verify"] == "mismatch"
    assert sum(1 for e in report["entries"] if e["verify"] == "ok") == len(report["entries"]) - 1


def test_manifest_reports_missing_and_untracked(client, settings):
    capture(client)
    folder = settings.data_dir / "evidence" / f"VK1-{AUTHOR_ID}"
    (folder / f"{AUTHOR_ID}-0001.json").unlink()
    (folder / "planted.png").write_bytes(b"x")
    report = client.get("/api/exports/manifest", params={"verify": "true"}).json()
    assert [(m["role"], m["verify"]) for m in report["mismatches"]] == [("sidecar", "missing")]
    assert report["untracked"] == [f"evidence/VK1-{AUTHOR_ID}/planted.png"]


def test_case_file_labels_tiers_phase_and_version(client):
    capture(client, meta(edge={"target_handle": "kaynak", "edge_type": "quote"}))
    client.post(
        "/api/cli/bulk-archive",
        json={"account": {"handle": AUTHOR}, "urls": [f"https://x.com/{AUTHOR}/status/1820000000000000001",
                                                       f"https://x.com/{AUTHOR}/status/1820000000000000002"]},
    )
    pending_id = client.get("/api/pending").json()[0]["evidence_id"]
    client.post(f"/api/evidence/{pending_id}/archive-only")

    case = client.get(f"/api/exports/accounts/{AUTHOR_ID}/case-file.json").json()
    assert case["account"]["account_id"] == AUTHOR_ID
    assert case["tiers"] == {"complete": 1, "archive_only": 1, "pending_completion": 1}
    tiers = {e["tier"]: e for e in case["evidence"]}
    assert tiers["complete"]["taxonomy_version"] == "1.1" and tiers["complete"]["phase"] == "VK1"
    assert "DEGRADED" in tiers["archive_only"]["tier_label"]
    assert tiers["archive_only"]["files"]["primary"]["sha256"] is None
    assert len(tiers["complete"]["archives"]) == 2
    assert case["edges"][0]["direction"] == "outgoing"
    assert [h["handle"] for h in case["handle_history"]] == [AUTHOR]
    assert client.get("/api/exports/accounts/42/case-file.json").status_code == 404


def test_edges_csv_columns(client):
    capture(client, meta(edge={"target_rest_id": "44196397", "target_handle": "kaynak", "edge_type": "quote"}))
    rows = list(csv.reader(io.StringIO(client.get("/api/exports/edges.csv").text)))
    assert rows[0] == [
        "source_account_id", "source_handle", "target_account_id", "target_handle",
        "edge_type", "phase", "post_url", "observed_at", "evidence_id",
    ]
    assert rows[1][:6] == [AUTHOR_ID, AUTHOR, "44196397", "kaynak", "quote", "VK1"]
