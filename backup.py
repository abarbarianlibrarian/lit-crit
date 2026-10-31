#!/usr/bin/env python3
"""
Weekly backup of the Literary Criticism Airtable base into the backup/ folder.

For each table it writes:
  backup/<table>.json   every record with every field, exactly as Airtable returns it
                        (linked records as record IDs) — the complete copy for restoring
  backup/<table>.csv    the same data as a spreadsheet, with linked records shown by name,
                        ready to open in Excel/Google Sheets or import into another tool
  backup/schema.json    table and field definitions (field types, select options, links)
                        when the token has schema.bases:read access
  backup/images/        author portraits and book covers (resized), so they survive
                        Airtable's expiring image links

The Members and Requests tables are never backed up.
Files attached in Reading Resources are not copied (only their file names are kept).
"""

import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_ID = "appIwriYb9qeDgwst"

# Table ID -> (file name, primary field name used if the schema can't be read)
TABLES = {
    "tblcPkKHdlXKFszGP": ("terms", "Term"),
    "tblv2LTIvL1vj36zt": ("authors", "Name"),
    "tblOom8qyFC4XhuTI": ("works", "Title"),
    "tblQJKN35eT7tHHDg": ("prizes", "Name"),
    "tblU6sGz2WIW2IG14": ("tags", "Name"),
    "tbleQuxeILnTHy6gM": ("historical-periods", "Name"),
    "tblfrvM5B3HwYgqh3": ("reading-resources", "Name"),
}
EXCLUDED_TABLES = {"tblFgeeAKfU1O0uSq", "tblxFktNANJE3CEq5"}  # Members, Requests
IMAGE_TABLES = {"tblv2LTIvL1vj36zt", "tblOom8qyFC4XhuTI"}     # portraits and covers

OUT = Path("backup")
TOKEN = os.environ.get("AIRTABLE_TOKEN") or sys.exit("AIRTABLE_TOKEN is not set.")


def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise


def fetch_records(table_id):
    records, offset = [], None
    while True:
        params = {"pageSize": "100"}
        if offset:
            params["offset"] = offset
        data = get(f"https://api.airtable.com/v0/{BASE_ID}/{table_id}?" + urllib.parse.urlencode(params))
        records += data.get("records", [])
        offset = data.get("offset")
        time.sleep(0.22)  # Airtable allows 5 requests per second
        if not offset:
            return records


def fetch_schema():
    try:
        data = get(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables")
    except urllib.error.HTTPError as e:
        print(f"Schema not saved (token needs schema.bases:read): HTTP {e.code}")
        return None
    data["tables"] = [t for t in data["tables"] if t["id"] in TABLES and t["id"] not in EXCLUDED_TABLES]
    return data


def cell_to_text(v, names):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    if isinstance(v, str):
        return names.get(v, v) if re.fullmatch(r"rec[A-Za-z0-9]{14}", v) else v
    if isinstance(v, dict):
        if "error" in v or "specialValue" in v:
            return ""
        if "filename" in v:
            return v["filename"]
        if "url" in v:
            return v["url"]
        return v.get("name") or v.get("label") or json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "; ".join(cell_to_text(x, names) for x in v if cell_to_text(x, names) != "")
    return str(v)


IMAGE_TIME_BUDGET = 20 * 60  # seconds per run; images not reached are saved next week
_started = time.monotonic()


def _save_one(att, path):
    from PIL import Image
    if time.monotonic() - _started > IMAGE_TIME_BUDGET:
        return "late"
    thumbs = att.get("thumbnails") or {}
    src = (thumbs.get("full") or {}).get("url") or att["url"]
    try:
        with urllib.request.urlopen(src, timeout=60) as r:
            im = Image.open(io.BytesIO(r.read()))
        im = im.convert("RGB")
        im.thumbnail((900, 1800))
        im.save(path, "WEBP", quality=82)
        return "ok"
    except Exception as e:
        print(f"  image skipped ({att.get('filename')}): {e}", flush=True)
        return "error"


def save_images(table_id, records):
    import concurrent.futures
    folder = OUT / "images" / TABLES[table_id][0]
    folder.mkdir(parents=True, exist_ok=True)
    jobs = []
    for rec in records:
        for v in rec["fields"].values():
            if not (isinstance(v, list) and v and isinstance(v[0], dict) and "filename" in v[0]):
                continue
            for att in v:
                if not str(att.get("type", "")).startswith("image/"):
                    continue
                if (att.get("width") or 99) < 8 or (att.get("height") or 99) < 8:
                    continue
                path = folder / f"{rec['id']}-{att['id']}.webp"
                if not path.exists():
                    jobs.append((att, path))
    print(f"  {len(jobs)} new images to save", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(lambda j: _save_one(*j), jobs))
    late = results.count("late")
    if late:
        print(f"  {late} images left for the next backup (time limit)", flush=True)
    return results.count("ok")


def main():
    OUT.mkdir(exist_ok=True)
    schema = fetch_schema()
    primary = {}
    if schema:
        (OUT / "schema.json").write_text(json.dumps(schema, indent=1, ensure_ascii=False), encoding="utf-8")
        for t in schema["tables"]:
            primary[t["id"]] = next(f["name"] for f in t["fields"] if f["id"] == t["primaryFieldId"])

    data = {}
    for table_id, (name, primary_fallback) in TABLES.items():
        print(f"Backing up {name}…", flush=True)
        data[table_id] = fetch_records(table_id)
        print(f"  {len(data[table_id])} records", flush=True)

    # Record ID -> display name across all backed-up tables, for readable CSVs.
    names = {}
    for table_id, recs in data.items():
        pf = primary.get(table_id, TABLES[table_id][1])
        for r in recs:
            names[r["id"]] = cell_to_text(r["fields"].get(pf), {}) or r["id"]

    summary = []
    for table_id, recs in data.items():
        name = TABLES[table_id][0]
        recs.sort(key=lambda r: r["id"])  # stable order keeps weekly changes small
        (OUT / f"{name}.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")

        if schema:
            table = next(t for t in schema["tables"] if t["id"] == table_id)
            columns = [f["name"] for f in table["fields"]]
        else:
            columns = []
            for r in recs:
                columns += [c for c in r["fields"] if c not in columns]
        pf = primary.get(table_id, TABLES[table_id][1])
        if pf in columns:
            columns.remove(pf)
        columns = [pf] + columns

        with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["Record ID"] + columns)
            for r in recs:
                w.writerow([r["id"]] + [cell_to_text(r["fields"].get(c), names) for c in columns])

        added = save_images(table_id, recs) if table_id in IMAGE_TABLES else 0
        summary.append(f"| {name} | {len(recs):,} |" + (f" {added:,} new images |" if table_id in IMAGE_TABLES else " |"))

    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (OUT / "README.md").write_text(
        f"# Airtable backup\n\nLast backup: {stamp}\n\n"
        "Each table is saved as `.json` (complete, for restoring) and `.csv` (open in any spreadsheet).\n"
        "Images are in `images/`. Earlier versions of every file are in this repository's history.\n"
        "Members and Requests are not backed up. Files attached in Reading Resources are not copied.\n\n"
        "| Table | Records | |\n|---|---|---|\n" + "\n".join(summary) + "\n",
        encoding="utf-8")
    print("Backup written.")


if __name__ == "__main__":
    main()
