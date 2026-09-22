#!/usr/bin/env python3
"""
Admission Radar automated source monitor.

The public site is self-contained: DATA lives inside index.html.
This script checks official source URLs and conservatively upgrades
2027 WATCH entries to OPEN only when the page contains a 2027/application
context plus an explicit opening signal.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

INDEX = Path("index.html")
MAX_BYTES = 1_500_000
TIMEOUT = 25
SLEEP_BETWEEN_REQUESTS = 0.25

YEAR_PATTERNS = [
    r"\b2027\b",
    r"\b2027[-–/ ]?(?:28|29)\b",
    r"\b(?:academic|admission|admissions|application|registration)[^<]{0,80}\b2027\b",
]

OPEN_PATTERNS = [
    r"\bapplications?\s+(?:for\s+)?2027\s+(?:are\s+)?(?:now\s+)?open\b",
    r"\b2027\s+(?:applications?|registration|admissions?)\s+(?:are|is|have been|has been)?\s*(?:now\s+)?open\b",
    r"\bregistration\s+(?:for\s+)?2027\s+(?:is\s+)?(?:now\s+)?open\b",
    r"\badmissions?\s+2027\s+(?:is|are)?\s*(?:now\s+)?open\b",
    r"\b2027\b.{0,180}\b(?:apply|application|applications|register|registration|registrations|admission|admissions)\b.{0,180}\b(?:open|apply now|register now)\b",
    r"\b(?:apply now|register now)\b.{0,180}\b2027\b",
]


PROCESS_PATTERNS = [
    r"\bapplication\b",
    r"\bregistration\b",
    r"\badmission\b",
    r"\bapply\b",
    r"\bregister\b",
]

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def fetch(url: str) -> tuple[int, str]:
    req = Request(
        url,
        headers={
            "User-Agent": "AdmissionRadar/2.0 (+https://github.com/khushvoid/Admission-Radar)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(req, timeout=TIMEOUT) as response:
        raw = response.read(MAX_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, raw.decode(charset, errors="ignore")


def clean_text(page: str) -> str:
    page = re.sub(r"<script\b[^>]*>.*?</script>", " ", page, flags=re.I | re.S)
    page = re.sub(r"<style\b[^>]*>.*?</style>", " ", page, flags=re.I | re.S)
    page = html.unescape(TAG_RE.sub(" ", page))
    return SPACE_RE.sub(" ", page).strip().lower()


def has_2027_signal(text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in YEAR_PATTERNS)


def has_process_signal(text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in PROCESS_PATTERNS)


def has_open_signal(text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in OPEN_PATTERNS)


def has_explicit_2027_open(text: str) -> bool:
    # Require a tight, explicit 2027 opening statement. This intentionally
    # ignores generic "apply/open" language on pages that are still showing
    # the 2026 cycle.
    strong_patterns = [
        r"\b2027\b.{0,80}\b(?:applications?|registration|registrations|admissions?)\b.{0,80}\b(?:now\s+)?open\b",
        r"\b(?:applications?|registration|registrations|admissions?)\b.{0,80}\b2027\b.{0,80}\b(?:now\s+)?open\b",
        r"\b(?:apply|register)\s+now\b.{0,100}\b2027\b",
        r"\b2027\b.{0,100}\b(?:apply|register)\s+now\b",
    ]
    return any(re.search(p, text, flags=re.I | re.S) for p in strong_patterns)


def should_open(row: dict, text: str) -> bool:
    return (
        row.get("cycle") == "2027"
        and row.get("status") == "WATCH"
        and has_explicit_2027_open(text)
    )


def should_keep_open(row: dict, text: str) -> bool:
    if row.get("cycle") != "2027" or row.get("status") != "OPEN":
        return True

    # Existing OPEN rows are re-verified on every run. If the official source
    # no longer contains an explicit 2027 opening statement, downgrade it to
    # WATCH instead of trusting stale/manual data.
    return has_explicit_2027_open(text)


def send_push(app_id: str, api_key: str, row: dict) -> None:
    payload = {
        "app_id": app_id,
        "target_channel": "push",
        "name": f"Admission Radar — {row['name']}",
        "headings": {"en": f"🔔 {row['name']} — 2027 is OPEN"},
        "contents": {
            "en": "Official-source monitoring detected an open 2027 application/registration."
        },
        "url": row["apply"],
        "included_segments": ["Subscribed Users"],
        "web_buttons": [
            {"id": "apply", "text": "Apply now", "url": row["apply"]},
            {
                "id": "radar",
                "text": "Open Admission Radar",
                "url": "https://khushvoid.github.io/Admission-Radar/"
            }
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        "https://api.onesignal.com/notifications",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urlopen(req, timeout=20) as response:
        response.read(100_000)


def extract_data(source: str) -> tuple[list[dict], tuple[int, int]]:
    match = re.search(r"\bconst\s+DATA\s*=\s*", source)
    if not match:
        raise RuntimeError("Could not find const DATA = in index.html")

    start = match.end()
    remainder = source[start:]
    stripped = remainder.lstrip()
    decoder = json.JSONDecoder()
    data, consumed = decoder.raw_decode(stripped)
    offset = start + (len(remainder) - len(stripped))
    end = offset + consumed

    if not isinstance(data, list):
        raise RuntimeError("Embedded DATA is not a JSON array")
    return data, (offset, end)


def write_data(source: str, data: list[dict], span: tuple[int, int]) -> str:
    start, end = span
    replacement = json.dumps(data, ensure_ascii=False, indent=2)
    return source[:start] + replacement + source[end:]


def validate_rows(rows: list[dict]) -> None:
    allowed_status = {"OPEN", "WATCH"}
    allowed_cycles = {"2027", "2028"}
    required = {
        "name", "city", "category", "cycle", "status", "streams",
        "programs", "exam", "apply", "source", "notes", "lastVerified"
    }

    for i, row in enumerate(rows):
        missing = required - set(row)
        if missing:
            raise RuntimeError(f"Row {i} ({row.get('name')}) missing: {sorted(missing)}")
        if row["status"] not in allowed_status:
            raise RuntimeError(f"Invalid status in row {i}: {row['status']}")
        if row["cycle"] not in allowed_cycles:
            raise RuntimeError(f"Invalid cycle in row {i}: {row['cycle']}")
        for key in ("apply", "source"):
            if not str(row[key]).startswith(("https://", "http://")):
                raise RuntimeError(f"Invalid URL in row {i}: {key}={row[key]}")


def main() -> int:
    if not INDEX.exists():
        raise SystemExit("index.html not found")

    source = INDEX.read_text(encoding="utf-8")
    rows, span = extract_data(source)
    validate_rows(rows)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    changes: list[dict] = []
    checked = 0
    failures = 0
    push_app_id = os.getenv("ONESIGNAL_APP_ID", "").strip()
    push_api_key = os.getenv("ONESIGNAL_API_KEY", "").strip()
    push_enabled = bool(push_app_id and push_api_key)

    for row in rows:
        # 2028 remains WATCH until its official cycle is actually published.
        if row.get("cycle") != "2027":
            continue

        try:
            status_code, page = fetch(row["source"])
            text = clean_text(page)
            old = row["status"]

            row["lastChecked"] = now
            row["httpStatus"] = status_code
            row.pop("monitorError", None)

            if row.get("status") == "OPEN" and not should_keep_open(row, text):
                row["status"] = "WATCH"
                print("VERIFY:", row["name"], "OPEN -> WATCH (2027 opening not explicitly verified)")
            elif should_open(row, text):
                row["status"] = "OPEN"
                changes.append({
                    "name": row["name"],
                    "apply": row["apply"],
                    "source": row["source"],
                })

            checked += 1
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeError) as exc:
            failures += 1
            row["lastChecked"] = now
            row["monitorError"] = str(exc)[:240]
        except Exception as exc:
            failures += 1
            row["lastChecked"] = now
            row["monitorError"] = f"{type(exc).__name__}: {str(exc)[:200]}"

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    updated = write_data(source, rows, span)
    if updated != source:
        INDEX.write_text(updated, encoding="utf-8")

    print(f"Admission Radar monitor: checked={checked}, failures={failures}, changes={len(changes)}")
    for change in changes:
        print("CHANGE:", change["name"], "-> OPEN")

    if changes and push_enabled:
        for change in changes:
            try:
                send_push(push_app_id, push_api_key, change)
                print("PUSH:", change["name"])
            except Exception as exc:
                # A notification failure must never make the admissions monitor fail.
                print("PUSH ERROR:", change["name"], str(exc)[:240])
    elif changes:
        print("PUSH: skipped (ONESIGNAL_APP_ID / ONESIGNAL_API_KEY not configured)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
