#!/usr/bin/env python3
"""
News Integrity TR - Spike S2: archive service submission probe (THROWAWAY).

YOU run this, not the tool. It submits a SMALL, hand-picked list of real public
X post URLs to Wayback (SPN2 anonymous) and archive.today, with polite spacing
and a real browser User-Agent, and logs every response verbosely so we can
finalize the two archive adapters (ARCHITECTURE section 3.4).

    pip install httpx
    python archive_probe.py --dry-run                    # print the plan, hit nothing
    python archive_probe.py --urls-file urls.txt         # real run, URLs from file
    python archive_probe.py --urls https://x.com/a/status/1 https://x.com/b/status/2
    python archive_probe.py --urls-file urls.txt --only archive_today

Politeness by construction: one external call at a time, --interval seconds
between calls (default 60), realistic UA, auto-redirects NOT followed (so we can
observe Location/Refresh). Keep the list to 2-3 URLs. Point this only at public
post URLs you are already looking at - never at bulk lists or discovery.

Go/no-go (S2): GO for an automated archive.today adapter if >=2 of 3 submissions
succeed WITHOUT a challenge. Otherwise the adapter routes jobs straight to
manual_pending at first challenge and the manual-assist loop becomes the normal
archive.today path (the queue design absorbs this with zero rework).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    sys.exit("Missing dependency. Run:  pip install httpx")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
BASE_HEADERS = {"User-Agent": UA, "Accept-Language": "tr,en;q=0.8"}
ARCHIVE_TODAY_HOST = "https://archive.md"
CHALLENGE_MARKERS = [
    "captcha", "recaptcha", "hcaptcha", "challenge-platform", "cf-chl",
    "just a moment", "attention required", "please verify",
    "verify you are human", "enable javascript and cookies",
]
X_POST_RE = re.compile(r"^https?://(x\.com|twitter\.com)/[^/]+/status/\d+", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def detect_challenge(text: str) -> list[str]:
    low = (text or "").lower()
    return [m for m in CHALLENGE_MARKERS if m in low]


def log_response(tag: str, resp: "httpx.Response", body_excerpt: int = 600) -> list[str]:
    print(f"\n--- [{tag}] {now_iso()} ---")
    print(f"  request : {resp.request.method} {resp.request.url}")
    print(f"  status  : {resp.status_code} {resp.reason_phrase}")
    print(f"  final   : {resp.url}")
    try:
        print(f"  elapsed : {resp.elapsed.total_seconds():.2f}s")
    except Exception:
        pass
    interesting = [
        "location", "refresh", "content-type", "content-length", "server",
        "cf-ray", "cf-mitigated", "retry-after", "link",
        "x-archive-orig-date", "x-archive-wayback-runtime-error",
    ]
    for h in interesting:
        if h in resp.headers:
            print(f"  header  : {h}: {resp.headers[h]}")
    cookies = resp.headers.get_list("set-cookie")
    if cookies:
        print(f"  cookies : set-cookie x{len(cookies)}")
    body = resp.text or ""
    ch = detect_challenge(body)
    if ch:
        print(f"  !! challenge markers: {ch}")
    print(f"  body_len: {len(body)}")
    print(f"  excerpt : {' '.join(body.split())[:body_excerpt]}")
    return ch


def probe_wayback(client: "httpx.Client", url: str, poll_times: int = 6,
                  poll_interval: float = 6.0, auth: dict | None = None) -> dict:
    mode = "authenticated S3" if auth else "anonymous"
    print(f"\n========== WAYBACK SPN2 ({mode}) :: {url} ==========")
    auth = auth or {}
    result = {"service": "wayback", "url": url, "archive_url": None,
              "status": "unknown", "challenge": [], "notes": []}
    try:
        r = client.post(
            "https://web.archive.org/save/",
            data={"url": url},
            headers={**BASE_HEADERS, "Accept": "application/json", **auth},
        )
    except Exception as e:
        result["status"] = "error"
        result["notes"].append(f"submit failed: {e}")
        print("  ERROR:", e)
        return result

    result["challenge"] += log_response("wayback submit", r)
    job_id = None
    try:
        j = r.json()
        print("  json    :", j)
        job_id = j.get("job_id")
        if not job_id and j.get("message"):
            result["notes"].append(f"message: {j['message']}")
    except Exception:
        result["notes"].append("submit response was not JSON (anonymous throttle / challenge / HTML?)")

    if not job_id:
        result["status"] = "no_job_id"
        return result

    print(f"  job_id  : {job_id} -- polling status/{job_id}")
    for i in range(poll_times):
        time.sleep(poll_interval)
        try:
            s = client.get(
                f"https://web.archive.org/save/status/{job_id}",
                headers={**BASE_HEADERS, "Accept": "application/json", **auth},
            )
            js = s.json()
        except Exception as e:
            print(f"  poll {i}: non-JSON / error ({e})")
            continue
        st = js.get("status")
        print(f"  poll {i}: status={st} {js.get('message', '')}")
        if st == "success":
            ts, orig = js.get("timestamp"), js.get("original_url", url)
            result["archive_url"] = f"https://web.archive.org/web/{ts}/{orig}"
            result["status"] = "done"
            print("  archive_url:", result["archive_url"])
            return result
        if st == "error":
            result["status"] = "error"
            result["notes"].append(js.get("message", "error"))
            return result
    result["status"] = "still_pending"
    return result


def probe_archive_today(client: "httpx.Client", url: str) -> dict:
    print(f"\n========== ARCHIVE.TODAY :: {url} ==========")
    result = {"service": "archive_today", "url": url, "archive_url": None,
              "status": "unknown", "challenge": [], "notes": []}

    # Warm-up GET (some deployments set a cookie needed by /submit/).
    try:
        g = client.get(ARCHIVE_TODAY_HOST + "/", headers=BASE_HEADERS)
        result["challenge"] += log_response("archive.today homepage GET", g)
    except Exception as e:
        print("  warm-up GET failed:", e)
        result["notes"].append(f"warmup failed: {e}")

    try:
        r = client.post(
            ARCHIVE_TODAY_HOST + "/submit/",
            data={"url": url, "anyway": "1"},
            headers={
                **BASE_HEADERS,
                "Referer": ARCHIVE_TODAY_HOST + "/",
                "Origin": ARCHIVE_TODAY_HOST,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
    except Exception as e:
        print("  submit failed:", e)
        result["status"] = "error"
        result["notes"].append(str(e))
        return result

    result["challenge"] += log_response("archive.today submit", r)
    loc = r.headers.get("location")
    refresh = r.headers.get("refresh")
    if loc:
        result["archive_url"] = loc if loc.startswith("http") else ARCHIVE_TODAY_HOST + loc
        result["status"] = "wip" if "/wip/" in loc else "redirect"
    elif refresh and "url=" in refresh.lower():
        result["archive_url"] = refresh.split("url=", 1)[1].strip()
        result["status"] = "refresh"
    elif result["challenge"]:
        result["status"] = "challenge"
    else:
        result["status"] = "no_redirect"
    print("  -> status:", result["status"], " archive_url:", result["archive_url"])
    return result


def politeness_sleep(sec: float) -> None:
    print(f"\n... politeness sleep {sec:.0f}s ...")
    time.sleep(sec)


def main() -> None:
    ap = argparse.ArgumentParser(description="S2 archive submission probe (throwaway).")
    ap.add_argument("--urls", nargs="*", default=[], help="inline X post URLs")
    ap.add_argument("--urls-file", help="file with one X post URL per line (# comments ok)")
    ap.add_argument("--interval", type=float, default=60.0,
                    help="seconds between external calls (default 60)")
    ap.add_argument("--only", choices=["wayback", "archive_today", "both"], default="both")
    ap.add_argument("--auth", action="store_true",
                    help="authenticated SPN2: send Authorization: LOW <access>:<secret> "
                         "from NIT_WAYBACK_S3_ACCESSKEY / NIT_WAYBACK_S3_SECRET env vars")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, make no network calls")
    args = ap.parse_args()

    wayback_auth = None
    if args.auth:
        access = os.environ.get("NIT_WAYBACK_S3_ACCESSKEY")
        secret = os.environ.get("NIT_WAYBACK_S3_SECRET")
        if not access or not secret:
            sys.exit("--auth requires NIT_WAYBACK_S3_ACCESSKEY and NIT_WAYBACK_S3_SECRET in env.")
        wayback_auth = {"Authorization": f"LOW {access}:{secret}"}

    urls = list(args.urls)
    if args.urls_file:
        with open(args.urls_file, encoding="utf-8") as f:
            urls += [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    urls = [u for u in urls if u]
    if not urls:
        sys.exit("No URLs given. Use --urls or --urls-file. Keep it to 2-3 posts.")
    if len(urls) > 4:
        print(f"WARNING: {len(urls)} URLs - S2 only needs 2-3. Be polite.\n")

    bad = [u for u in urls if not X_POST_RE.match(u)]
    if bad:
        print("WARNING: these do not look like X post URLs (…/status/<id>):")
        for u in bad:
            print("   ", u)
        print()

    print("PLAN")
    print(f"  urls     : {len(urls)}")
    for u in urls:
        print("    -", u)
    print(f"  services : {args.only}")
    print(f"  wayback  : {'AUTHENTICATED (S3 keys)' if wayback_auth else 'anonymous'}")
    print(f"  interval : {args.interval:.0f}s between external calls")
    print(f"  UA       : {UA}")
    print("  redirects: NOT auto-followed (Location/Refresh observed directly)")
    if args.dry_run:
        print("\nDRY RUN - no network calls made.")
        return

    results = []
    with httpx.Client(follow_redirects=False, timeout=30.0) as client:
        first = True
        for u in urls:
            if args.only in ("wayback", "both"):
                if not first:
                    politeness_sleep(args.interval)
                first = False
                results.append(probe_wayback(client, u, auth=wayback_auth))
            if args.only in ("archive_today", "both"):
                if not first:
                    politeness_sleep(args.interval)
                first = False
                results.append(probe_archive_today(client, u))

    print("\n\n================= PASTE THIS BACK =================")
    for r in results:
        print(f"- {r['service']:<14} {str(r.get('status')):<14} {r['url']}")
        if r.get("archive_url"):
            print(f"    archive_url : {r['archive_url']}")
        if r.get("challenge"):
            print(f"    challenge   : {sorted(set(r['challenge']))}")
        if r.get("notes"):
            print(f"    notes       : {r['notes']}")
    print("\nAlso tell me:")
    print("  * how many archive.today submits succeeded WITHOUT a challenge (X of N)")
    print("  * any CAPTCHA / Cloudflare 'Just a moment' page you saw")
    print("  * whether 60s spacing felt sufficient or you got throttled/429")


if __name__ == "__main__":
    main()
