---
name: evidence-integrity
description: >-
  Enforce the evidence-integrity invariants of News Integrity TR whenever you
  write or modify backend code that touches evidence files, hashes, the DB
  schema/migrations, or any write path (capture, CLI bulk-archive, merge,
  archive worker, exports). Covers write-once files, atomic write + SHA-256
  read-back verify, rest_id as TEXT, append-only tables, status-transition-only
  lifecycles, and server-side phase + taxonomy_version stamping. Load this
  before writing any code under backend/.
---

# evidence-integrity

Evidence integrity is the top design principle (ARCHITECTURE §1). It outranks
developer convenience and cleverness. **If a shortcut weakens the evidence
trail, it is not taken.** When a rule here conflicts with a "simpler" approach,
the rule wins — or you stop and raise a new ADR.

## The invariants (never negotiate these silently)

1. **rest_id is `TEXT` everywhere — never a JS/JSON number, never a float column.**
   - `accounts.account_id` (the X numeric user id, digits only) is the primary
     key and the foreign key in every table. Handles are display data, never keys.
   - Every layer keeps it a string: SQLAlchemy `String`, Pydantic `str` (add a
     `pattern=r"^\d+$"` validator), TS `string`. A rest_id must never pass
     through `int`, `float`, `number`, or `JSON.parse` into a JS number.
   - Same discipline for `post_id`, `in_reply_to_user_id_str`, and any other X
     snowflake id.

2. **Write-once files.** Evidence PNGs and the `.json` sidecar are never edited,
   renamed, moved, or deleted after creation. Corrections happen as **new
   captures** (new `seq`, new row), never as edits. The canonical name
   `{account_id}-{seq:04d}.png` always holds the *primary* evidence (the crop;
   or the viewport when `crop_failed=1`). Report tooling must never branch on
   crop success — it always references the canonical name.

3. **Atomic write + hash + read-back verify** (every image and sidecar write):
   compute SHA-256 from the in-memory bytes → write to `*.tmp` → `os.replace`
   → read the file back from disk → recompute SHA-256 → assert equal. Mismatch
   ⇒ fail the request **loudly (5xx)**, clean up the temp/partial files, and
   commit nothing to the DB. Never store a hash you did not re-verify from disk.

4. **Append-only tables; nothing is ever deleted.**
   - `handle_history` is **complete from birth** (ADR-020): account creation
     inserts the initial handle (`detected_at = first_seen_at`, `evidence_id`
     when created via a capture); on change detection the **newly observed**
     handle is appended. Never `UPDATE`/`DELETE` a history row. `current_handle`
     is denormalized convenience only — never a key.
   - `archive_jobs` rows are never deleted; every terminal state except
     `done`/`manual_done` stays visible in the queue.
   - `taxonomy_codes` labels may upsert; codes are **never deleted** (evidence
     references them).

5. **Status transitions only — enumerate and enforce the legal set.**
   - Evidence: `pending_completion → complete` (merge) and
     `pending_completion → archive_only` (user-confirmed deletion). `complete`
     is terminal and never downgraded.
   - Archive jobs: only the transitions in the ARCHITECTURE §3.4 state diagram.
   - Guard transitions in code (reject illegal ones with 409/422); never mutate
     a status field with a bare assignment that skips the check.

6. **Server-side stamping — the client never supplies provenance.**
   - `phase` (`VK1`/`VK2`) is read from `NIT_PHASE` and stamped on every
     `evidence` **and** `edge` row at creation, and it derives the folder prefix
     `{phase}-{account_id}/`.
   - `taxonomy_version` is stamped from the currently seeded taxonomy version at
     the moment codes are attached (extension capture, or CLI-row completion).
     It is `NULL` only while `pending_completion`.
   - Reject any request that tries to set `phase` or `taxonomy_version` itself.

7. **Sidecar is written exactly once**, at capture completion (or at the
   merge-upgrade for CLI rows). Archive links are **not** in the sidecar — they
   arrive later and the sidecar is immutable. They live in `archive_jobs` and
   surface only in exports.

8. **Single writer.** All writes go through the backend HTTP API (ADR-004). The
   CLI and worker never touch the DB or filesystem directly. Wrap the DB work of
   a capture in one transaction; enqueue archive jobs in that same transaction.

## Reference: the only correct write shape

```python
import hashlib, os

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def atomic_write_verified(path: str, data: bytes) -> str:
    """Write bytes write-once, return the disk-verified sha256. Raises on any
    integrity failure; caller must abort the whole capture and clean up."""
    if os.path.exists(path):
        raise FileExistsError(f"write-once violation: {path} already exists")
    expected = sha256(data)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)              # atomic on same filesystem
    with open(path, "rb") as f:        # read BACK from disk
        got = sha256(f.read())
    if got != expected:
        raise IOError(f"hash mismatch after write: {path} ({got} != {expected})")
    return expected
```

## Checklist before you commit backend code

- [ ] No rest_id / snowflake id anywhere as `int`/`float`/JS `number`.
- [ ] Every file write goes through atomic-write + read-back verify; failure is 5xx + cleanup + no DB commit.
- [ ] No path edits/deletes/renames of existing evidence or sidecars.
- [ ] Every new evidence/edge row is stamped with `phase`; coded rows stamped with `taxonomy_version`; both server-side.
- [ ] Status changes go through a transition guard, not a bare assignment.
- [ ] Account creation seeds `handle_history`; change detection appends (never updates) it.
- [ ] Archive jobs enqueued in the same transaction as the evidence insert; jobs never deleted.
- [ ] Sidecar written once, contains no archive links.

**When in doubt, preserve the evidence trail and stop.** A missing feature is
recoverable; a corrupted or unverifiable evidence chain is not. If a required
change appears to conflict with these invariants, raise it as a new ADR
(ADR-024+) and wait — do not work around the invariant.
