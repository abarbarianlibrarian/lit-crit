#!/usr/bin/env python3
"""
Builds the Literary Criticism website from the Airtable base.

Usage:
  AIRTABLE_TOKEN=pat... python build.py            # fetch live data, build into ./site
  python build.py --fixtures fixtures/              # build from saved JSON (for testing)
  python build.py --save-data data/                 # also save the fetched JSON

Environment (all optional except the token):
  AIRTABLE_TOKEN   Airtable personal access token (read access to the base)
  SITE_TITLE       Name shown in the header (default "Literary Criticism")
  BASE_PATH        URL path the site lives under, e.g. "/lit-crit/" (default "/")
  SITE_URL         Full public address, e.g. "https://name.github.io/lit-crit/" (for sitemap)
"""

import argparse
import concurrent.futures
import datetime
import html
import io
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE_ID = "appIwriYb9qeDgwst"

# Tables and the fields the site uses (Airtable field IDs, so renaming a field in
# Airtable won't break the site).
TABLES = {
    "terms": ("tblcPkKHdlXKFszGP", {
        "name": "fldaPMxNZYkY7p84x", "short": "fldGMKdtfyu03CK6B", "definition": "fldEWol0G9ksi5tGC",
        "mentioned": "fldJhXfzL9A99oyos", "related": "fldXvNAT4jPJaR3E7", "tags": "fld0t6v2AZqeWicCI",
        "authors": "fld7yDp5hGXqHPeFG", "date": "fld6XeHIEPN4OjisU", "today": "fldHS2sW665ELiWYo",
        "appearances": "flda3zLGAsqOWUu2Y",
    }),
    "authors": ("tblv2LTIvL1vj36zt", {
        "name": "fldir5h8wsLHZmNkd", "nationality": "fldNiSyQVIr0teads", "birth": "fldf97H8m30BZfQuE",
        "death": "fldCDFWFnZJKY3mqm", "groups": "fldx28iQe6cYRk0pa", "prizes": "fldf8HBg9txnPnabO",
        "picture": "fldluSS0389Zj68Zl", "picture_url": "fldzmCf0XXpX4c5Tb", "wikipedia": "fldAAuog6Fwr9drOP",
        "youtube": "fldCqLxv0I0o7sIwJ", "periods": "fldOoPpnA2yNHkANz", "medium": "fldEGUGQHuKJxaxiR",
        "first": "fldSm5ftkHEn0C596", "last": "fld3cDnR7vH49g28M", "alternate": "fld83eZxzidKWyNUC",
        "terms": "fldJhoUfxqtEGQHwi", "works": "fldvgfsTJz4vMzRxj",
        "date": "fldWBIqAW0L1a9VDl", "today": "fldt7E7Wqjn2tjVeA", "appearances": "fldYwAcza9A8qNjFN",
    }),
    "works": ("tblOom8qyFC4XhuTI", {
        "name": "fldu0qLBaWaNcb8h2", "authors": "fldsMj4EbbCQnngB4", "quoted": "fldqR6C6tqa2Xm6Zl",
        "notable": "flds3WJ6k8wuJnzKY", "terms_text": "fldLCXwyb6RW68WgM", "cover": "fldKYCRLep2hovNU3",
        "alt_cover": "fld4DY1vNagsGnu9f", "isbn": "fldOu2uKdFLTtPL52", "synopsis": "fldQe8T7dpNeMNreD",
        "published": "fldyKjrbbQFgN0t9I", "cover_url": "fld8ntIkt4xV5B12W", "pages": "fld0VLBgFqYpkHlj2",
        "reading_list": "fldLlvDw9OSMcJgp7", "year_written": "fld0VavM96rXTHOv5", "tags_text": "fldG0V7sxNDpUpkIf",
        "prizes": "fldyJHS3MAmC9Y3xB", "type": "fldpr9qhkWAbYr4kS", "language": "fldQVWc56BcCOZMLs",
    }),
    "prizes": ("tblQJKN35eT7tHHDg", {
        "name": "fldiTxVCQkVAvDFS3", "type": "fldUwkLHNeGfMnI2e", "year": "fldEsWcFc23sEt6JR",
        "works": "fldClKg0P0azExAzQ", "authors": "fldmF7hQhYRAxwwkk", "citation": "fldWKRCZrRiexXXwC",
        "tested": "fld0F6ICj2hM81imA",
    }),
    "tags": ("tblU6sGz2WIW2IG14", {
        "name": "fldvOH4ijvCSZVJxZ", "quizlet": "fldBkxmhuqoC6YGmN", "gimkit": "fldScrugcf1FeJul3",
        "blooket": "fldhw7lQl2EnxAWhv", "sporcle": "fldxE93XJKltnxDad", "terms": "fldIji0wvpgvCdiS7",
    }),
    "periods": ("tbleQuxeILnTHy6gM", {
        "name": "fldDzTb5g2hEHja3u", "start": "fldCfyUiRMr5wnrNi", "end": "fldfRzdL6btKIbe1M",
        "region": "fldyRjkfKVuCqoi8E", "type": "fld9sIAqYvlrJxPr6", "parent": "fldH7t7R5MoxLTHkx",
        "subs": "fld1B4YPME8C0zhvG", "term_text": "fldBJ9BCvzlDdoln6", "description": "fldRXBfOEy41LZikz",
        "before": "fldcZhoaB2Q1L90M9", "after": "fldzPxGFR9EVyeZkb", "authors_text": "fldIUl2gIB7M8e3tR",
    }),
    "resources": ("tblfrvM5B3HwYgqh3", {
        "name": "fldL0NeGFsHTtCuTY", "year": "fldYjH6DrMMW8cyst", "type": "fldZFmUiDfw7dt2UV",
        "work": "fldpIadf3Zq41nZKo", "link": "fld94UO33vHDZzs7N", "access": "fldM8Y98hILZsxrqI",
    }),
    "reading-lists": ("tblS8WrrRcpF6hhMq", {
        "name": "fldWDcj2iJT5Q0gXp", "year": "flduoiWbyolCViqal", "novel": "fldEmmFZ4je9LxAH8",
        "play": "fldoJMW8hA1cqts1O", "poet": "fldrAZxOHkIUojfgv",
    }),
    "poems": ("tblQ2KWCeyNrWshMF", {
        "name": "fldheIjKBCv88NxiU", "text": "fldJLtOZ8fZi1FEGB", "authors": "fldycqc8GJHDMnJot",
        "essays": "fldWFdsdA7r3ydtAR", "questions": "fld2W4ywICtx1aslc",
    }),
    "questions": ("tblOCo90Gz36SYv10", {
        "name": "fldRhddsjYnpVrK71", "test": "fldilaCNMHb6EYsJn", "prompt": "fld5RLsrVQAr8fhfo",
        "a": "fldvEEBT7MUTJKMaj", "b": "fldQRHXDdoaqBo36c", "c": "fldacm4HCaA4qtINy",
        "d": "fldH8tlQAXyYmJ2tr", "e": "fldygihYAICaoblm9", "correct": "fldkWHxQ1rCEW06g7",
        "number": "fldwadHhF7fbzuedS", "part": "fldJrtGYQyU2sq55x", "poems": "fldxo5vOdLp63ohVZ",
        "rl_works": "fld8BtUvVz4VEyl6w", "terms": "fldHfOfZ0ImhwX5V7", "authors": "fldXuzM3SSDbXZoPi",
        "works": "fldWpu4MAkgQe8Mvv",
    }),
    "tests": ("tblDASF9lXxJby0kz", {
        "name": "fldkWtaAfrRmC1lpK", "year": "fld1PomM202MScaic", "type": "fldYZkncJfj653B49",
        "questions": "fldZknvWA4ThMzBT9", "passage": "fldCF9oIUfqnGLmDe",
    }),
    "essays": ("tbloXypOYQ086Pf5o", {
        "name": "fld98QHXSPFVXQVao", "prompt": "fldWhCvgV8NURzqKA", "poems": "fld51bwq2H8BR2STU",
    }),
    # Examples of terms (titles, lines, phrases, words, excerpts): shown with the term of the day
    # and on term pages.
    "examples": ("tbl2mnqFYsmEbZLNI", {
        "name": "fldMuFpEEdQXCJFxV", "terms": "flddn4E1MBLKKMbFN", "authors": "fldSUnsDOMgQhVHWB",
        "type": "fldAtL3CTouqYymWz", "source": "fldWq5bC5kj3W4AQG",
    }),
    # Shown only on the Periods timeline, beside the period each event falls in.
    "events": ("tblzOtL2DxbE7LloC", {
        "name": "fldpJz4MhYPahF6c8", "start": "fldyxtQkzXzmNakxP", "end": "flduwh0Y6SgQTaSMd",
        "approximate": "fldR1rV5hM81oPnlM", "region": "fldNx7tvpqqRZ9wf7", "category": "fldJ2rfQdHa28YqDs",
        "description": "fldNEt626OuUJaq0E", "periods": "fldLjD9C2paQ4XtvD", "us": "fldsazlxfF81QP4NE",
    }),
}

# Tables shown inside other pages rather than with pages of their own.
NO_PAGES = {"resources", "questions", "reading-lists", "events", "examples"}

SECTIONS = [  # url folder, nav label, singular label
    ("terms", "Terms", "Term"),
    ("authors", "Authors", "Author"),
    ("works", "Works", "Work"),
    ("poems", "Poems", "Poem"),
    ("tests", "Tests", "Test"),
    ("essays", "Essay Prompts", "Essay prompt"),
    ("reading-lists", "Reading Lists", "Reading list"),
    ("prizes", "Prizes", "Prize"),
    ("periods", "Periods", "Period"),
    ("tags", "Sets", "Set"),
    ("resources", "Resources", "Resource"),
    ("flashcards", "Flashcards", "Deck"),
]

# Web-address folder for a section when it differs from its key: the Tags table is shown as "Sets".
FOLDERS = {"tags": "sets"}


def folder(key):
    return FOLDERS.get(key, key)


# Sections left out of the menu at the top of every page (their pages still exist and are linked elsewhere).
NAV_HIDDEN = {"works", "tags"}

SITE_TITLE = os.environ.get("SITE_TITLE", "Literary Criticism")
GA_ID = os.environ.get("GA_ID", "G-CRQBFM26RK")  # Google Analytics measurement ID
# Accounts (Supabase). The project URL and its publishable (anon) key are public by design: what each
# visitor can read or write is enforced by the database's row-level security. Leave both blank to hide sign-in.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://dxyfxmacwdbbkeirvsdx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_PHMTnFf2AOIbVbFGTcBuRw_eFY2WLu4")
SUPABASE_LIB = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"
BASE = "/" + os.environ.get("BASE_PATH", "/").strip("/") + "/"
BASE = "/" if BASE == "//" else BASE
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/") + "/" if os.environ.get("SITE_URL") else ""

OUT = Path("site")
MEDIA_CACHE = Path(".media-cache")


# ---------------------------------------------------------------- fetching

def fetch_table(token, table_id, field_ids, base_id=None):
    base_id = base_id or BASE_ID
    records, offset = [], None
    while True:
        params = [("pageSize", "100"), ("returnFieldsByFieldId", "true")]
        params += [("fields[]", f) for f in field_ids]
        if offset:
            params.append(("offset", offset))
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise SystemExit(f"Airtable error {e.code} on table {table_id}: {e.read()[:300]!r}")
        records += data.get("records", [])
        offset = data.get("offset")
        time.sleep(0.22)  # stay under Airtable's 5 requests/second
        if not offset:
            return records


def load_data(args):
    raw = {}
    if args.fixtures:
        for key in TABLES:
            p = Path(args.fixtures) / f"{key}.json"
            raw[key] = json.loads(p.read_text()) if p.exists() else []
        return raw
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        raise SystemExit("AIRTABLE_TOKEN is not set.")
    for key, (table_id, fields) in TABLES.items():
        print(f"Fetching {key}…", flush=True)
        raw[key] = fetch_table(token, table_id, list(fields.values()))
        print(f"  {len(raw[key])} records", flush=True)
        if args.save_data:
            Path(args.save_data).mkdir(parents=True, exist_ok=True)
            (Path(args.save_data) / f"{key}.json").write_text(json.dumps(raw[key]))
    return raw


# UIL schools for the Account page's school picker: the Schools Master table in the Master Tab Room
# base. The AIRTABLE_TOKEN needs read access to that base too; without it the picker falls back to
# a free-text school field.
SCHOOLS_BASE = "appHrIvllzeW3qy1N"
SCHOOLS_TABLE = "tblJsPynFPK8hsMJ9"
SCHOOLS_FIELDS = {"name": "fldlZwlGP5vLaT700", "city": "fld15uwKgLHMymFaC", "class": "flduVvPYSGAsqqjYH"}


def load_schools(args):
    """[[record id, name, city, classification], …] sorted by name, or None if unavailable."""
    try:
        if args.fixtures:
            p = Path(args.fixtures) / "schools.json"
            recs = json.loads(p.read_text()) if p.exists() else None
        else:
            token = os.environ.get("AIRTABLE_TOKEN")
            print("Fetching UIL schools…", flush=True)
            recs = fetch_table(token, SCHOOLS_TABLE, list(SCHOOLS_FIELDS.values()), SCHOOLS_BASE)
    except (SystemExit, Exception) as err:
        print(f"  note: UIL school list not available ({err}); the school field will be free text", flush=True)
        return None
    if recs is None:
        return None
    out = []
    for r in recs:
        f = r.get("fields", {})
        name = as_text(f.get(SCHOOLS_FIELDS["name"])).strip()
        if name:
            out.append([r["id"], name, as_text(f.get(SCHOOLS_FIELDS["city"])).strip(),
                        as_text(f.get(SCHOOLS_FIELDS["class"])).strip()])
    out.sort(key=lambda x: (fold(x[1]), fold(x[2])))
    print(f"  {len(out)} schools", flush=True)
    return out


# ---------------------------------------------------------------- normalizing cell values

def as_text(v):
    if v is None:
        return ""
    if isinstance(v, dict):
        if "error" in v or v.get("specialValue"):
            return ""
        if "name" in v:
            return str(v["name"])
        if "url" in v:
            return str(v["url"])
        if "valuesByLinkedRecordId" in v:
            return ", ".join(as_list(v))
        return ""
    if isinstance(v, list):
        return ", ".join(as_text(x) for x in v if as_text(x))
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def as_list(v):
    """Multiple-select, lookup and rollup values -> list of strings."""
    if v is None:
        return []
    if isinstance(v, dict):
        if "valuesByLinkedRecordId" in v:
            out = []
            for rid in v.get("linkedRecordIds", []):
                out += [as_text(x) for x in v["valuesByLinkedRecordId"].get(rid, [])]
            return [x for x in out if x]
        t = as_text(v)
        return [t] if t else []
    if isinstance(v, list):
        return [t for t in (as_text(x) for x in v) if t]
    t = as_text(v)
    return [t] if t else []


def as_links(v):
    if not v:
        return []
    out = []
    for x in v:
        if isinstance(x, str) and x.startswith("rec"):
            out.append(x)
        elif isinstance(x, dict) and str(x.get("id", "")).startswith("rec"):
            out.append(x["id"])
    return out


def as_attachments(v):
    return [a for a in (v or []) if isinstance(a, dict) and a.get("url")]


LINK_FIELDS = {
    "terms": {"mentioned": "terms", "related": "terms", "tags": "tags", "authors": "authors"},
    "authors": {"prizes": "prizes", "terms": "terms", "works": "works"},
    "works": {"authors": "authors", "prizes": "prizes"},
    "prizes": {"works": "works", "authors": "authors"},
    "tags": {"terms": "terms"},
    "periods": {"parent": "periods", "subs": "periods", "before": "periods", "after": "periods"},
    "events": {"periods": "periods"},
    "resources": {},
    "reading-lists": {"novel": "works", "play": "works", "poet": "authors"},
    "poems": {"authors": "authors", "essays": "essays", "questions": "questions"},
    "questions": {"test": "tests", "poems": "poems", "rl_works": "works", "terms": "terms",
                  "authors": "authors", "works": "works"},
    "tests": {"questions": "questions"},
    "essays": {"poems": "poems"},
    "examples": {"terms": "terms", "authors": "authors"},
}
LIST_FIELDS = {
    "authors": {"groups", "periods", "medium"},
    "works": {"reading_list", "type", "language"},
    "resources": {"work"},
    "questions": {"correct"},
    "prizes": {"tested"},
}
ATTACH_FIELDS = {"picture", "cover", "alt_cover"}


def normalize(raw):
    db = {}
    for key, (_, fields) in TABLES.items():
        db[key] = {}
        for rec in raw[key]:
            cells = rec.get("fields") or rec.get("cellValuesByFieldId") or {}
            r = {"id": rec["id"]}
            for name, fid in fields.items():
                v = cells.get(fid)
                if name in LINK_FIELDS[key]:
                    r[name] = as_links(v)
                elif name in ATTACH_FIELDS:
                    r[name] = as_attachments(v)
                elif name in LIST_FIELDS.get(key, ()):
                    r[name] = as_list(v)
                else:
                    r[name] = as_text(v)
            db[key][rec["id"]] = r
    # Drop links that point at records that aren't on the site.
    for key, links in LINK_FIELDS.items():
        for r in db[key].values():
            for field, target in links.items():
                r[field] = [x for x in dict.fromkeys(r[field]) if x in db[target] and x != r["id"]]
    return db


# ---------------------------------------------------------------- names, slugs, sorting

def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def slugify(s):
    s = fold(s)
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80].strip("-") or "untitled"


def sort_key(s):
    s = fold(s).strip(" \"'“‘(")
    s = re.sub(r"^(the|a|an)\s+", "", s)
    return s


def letter_of(s):
    k = sort_key(s)
    return k[0].upper() if k and k[0].isalpha() else "#"


def display_name(key, r):
    if key == "prizes":
        name = re.sub(r"\s*-\s*$", "", r["name"]).strip()
        return name or f'{r["year"]} {r["type"]}'.strip() or "Prize"
    if key == "resources":
        return r["name"] or "Resource"
    if key == "questions":
        return (r["prompt"] or r["name"] or "Question").strip()
    if key == "reading-lists":
        return r["year"] or r["name"] or "Reading list"
    return r["name"] or "Untitled"


def assign_urls(db):
    for key in db:
        taken = {}
        for r in sorted(db[key].values(), key=lambda r: r["id"]):
            r["title"] = display_name(key, r)
            slug = slugify(r["title"])
            if slug in taken or slug in ("browse", "media", "assets"):
                slug = f"{slug}-{r['id'][3:9].lower()}"
            taken[slug] = r["id"]
            r["slug"] = slug
            r["url"] = None if key in NO_PAGES else f"{BASE}{folder(key)}/{slug}/"
    for r in db["reading-lists"].values():
        r["url"] = f"{BASE}reading-lists/#{r['slug']}"
    for q in db["questions"].values():
        test = db["tests"].get(q["test"][0]) if q["test"] else None
        q["url"] = f"{test['url']}#q-{q['id']}" if test else None


def author_sort(r):
    last, first = r.get("last", ""), r.get("first", "")
    if last:
        return sort_key(f"{last} {first}")
    return sort_key(r["title"])


# ---------------------------------------------------------------- relationships

def build_relations(db):
    rel = defaultdict(lambda: defaultdict(list))

    def add(a_key, a_id, b_key, b_id):
        if b_id not in rel[(a_key, a_id)][b_key]:
            rel[(a_key, a_id)][b_key].append(b_id)

    # Reverse links for every link field.
    for key, links in LINK_FIELDS.items():
        for r in db[key].values():
            for field, target in links.items():
                for other in r[field]:
                    rel[(target, other)][f"rev:{key}:{field}"].append(r["id"])

    # Merge both directions for the main pairs.
    for t in db["terms"].values():
        for a in t["authors"]:
            add("terms", t["id"], "authors", a); add("authors", a, "terms", t["id"])
        for g in t["tags"]:
            add("terms", t["id"], "tags", g); add("tags", g, "terms", t["id"])
    for a in db["authors"].values():
        for x in a["terms"]:
            add("authors", a["id"], "terms", x); add("terms", x, "authors", a["id"])
        for w in a["works"]:
            add("authors", a["id"], "works", w); add("works", w, "authors", a["id"])
        for p in a["prizes"]:
            add("authors", a["id"], "prizes", p); add("prizes", p, "authors", a["id"])
    for w in db["works"].values():
        for a in w["authors"]:
            add("works", w["id"], "authors", a); add("authors", a, "works", w["id"])
        for p in w["prizes"]:
            add("works", w["id"], "prizes", p); add("prizes", p, "works", w["id"])
    for p in db["prizes"].values():
        for w in p["works"]:
            add("prizes", p["id"], "works", w); add("works", w, "prizes", p["id"])
        for a in p["authors"]:
            add("prizes", p["id"], "authors", a); add("authors", a, "prizes", p["id"])
    for g in db["tags"].values():
        for t in g["terms"]:
            add("tags", g["id"], "terms", t); add("terms", t, "tags", g["id"])
    # Practice tests, poems and reading lists.
    for t in db["tests"].values():
        for q in t["questions"]:
            add("tests", t["id"], "questions", q); add("questions", q, "tests", t["id"])
    for q in db["questions"].values():
        for t in q["test"]:
            add("tests", t, "questions", q["id"]); add("questions", q["id"], "tests", t)
        for p in q["poems"]:
            add("poems", p, "questions", q["id"]); add("questions", q["id"], "poems", p)
        for k in ("terms", "authors", "works"):
            for x in q[k]:
                add(k, x, "questions", q["id"])
        for w in q["rl_works"]:
            add("works", w, "questions", q["id"])
    for p in db["poems"].values():
        for q in p["questions"]:
            add("poems", p["id"], "questions", q); add("questions", q, "poems", p["id"])
        for a in p["authors"]:
            add("poems", p["id"], "authors", a); add("authors", a, "poems", p["id"])
        for x in p["essays"]:
            add("poems", p["id"], "essays", x)
    for x in db["essays"].values():
        for p in x["poems"]:
            add("poems", p, "essays", x["id"])
    for rl in db["reading-lists"].values():
        for w in rl["novel"] + rl["play"]:
            add("works", w, "reading-lists", rl["id"])
        for a in rl["poet"]:
            add("authors", a, "reading-lists", rl["id"])
    # Every test a poem appeared on.
    for p in db["poems"].values():
        for q in rel[("poems", p["id"])].get("questions", []):
            for t in rel[("questions", q)].get("tests", []):
                add("poems", p["id"], "tests", t)
    return rel


DATE_SUFFIX = re.compile(r",?\s*\d{3,4}\s*[-–—]\s*(?:\d{3,4})?\s*$")
QUOTES = "“”\"‘’'"

# Cross-references whose wording differs from the term's name: adjective forms, alternate names,
# and period names. Values are term names; when several are listed, the one linked from the
# definition (Mentioned/Related Terms) wins, then one sharing "American"/"English" with the page.
XREF_ALIASES = {
    "iambic": ["Iamb (or Iambus)"], "trochaic": ["Trochee"], "spondaic": ["Spondee"], "dactylic": ["Dactyl"],
    "anapestic": ["Anapest"], "chiastic": ["Chiasmus"], "choriambic": ["Choriambus"], "choriambs": ["Choriambus"],
    "choliamb": ["Choliambus"], "allegorical": ["Allegory"], "alliterative": ["Alliteration"],
    "apocryphal": ["Apocrypha"], "autobiographical": ["Autobiography"], "boustrophedonic": ["Boustrophedon"],
    "chorographic": ["Chorography"], "deductive": ["Deduction"], "inductive": ["Induction"],
    "didactic": ["Didacticism"], "epicurean": ["Epicureanism"], "mimetic": ["Mimesis"], "parodic": ["Parody"],
    "pluralistic": ["Pluralism"], "puritan": ["Puritanism"], "realistic": ["Realism"], "romantic": ["Romanticism"],
    "satiric": ["Satire"], "satirical": ["Satire"], "sentimental": ["Sentimentalism"], "melodramatic": ["Melodrama"],
    "figurative": ["Figurative Language"], "octosyllabic": ["Octosyllabic Verse"],
    "hendecasyllabic": ["Hendecasyllabic Verse"], "hendecasyllabics": ["Hendecasyllabic Verse"],
    "metrical": ["Meter"], "metrics": ["Meter"], "quantitative": ["Quantitative Versification"],
    "quantitative verse": ["Quantitative Versification"], "quantitative scansion": ["Quantitative Versification"],
    "qualitative": ["Qualitative Versification"], "accentual-syllabic": ["Accentual-Syllabic Verse"],
    "picaresque": ["Picaresque Novel"], "menippean": ["Menippean Satire"], "petrarchan": ["Petrarchan Sonnet"],
    "shakespearean": ["Shakespearean Sonnet"], "elizabethan": ["Elizabethan Age"], "jacobean": ["Jacobean Age"],
    "senecan": ["Senecan Tragedy"], "horatian": ["Horatian Ode"], "irregular": ["Irregular Ode"],
    "pindaric": ["Pindarism"], "omniscient": ["Omniscient Point of View"], "panoramic": ["Panoramic Method"],
    "occasional": ["Occasional Verse"], "demotic": ["Demotic Style"], "headless": ["Headless Line"],
    "headless iambic": ["Headless Line"], "antirealistic": ["Antirealistic Novel"], "heroic": ["Heroic Verse"],
    "feminine": ["Feminine Ending"], "masculine": ["Masculine Rhyme"], "neoclassic": ["Neoclassicism"],
    "naturalistic": ["Naturalism"], "postmodernist": ["Postmodernism"], "modernist": ["Modernism"],
    "symbolistic": ["Symbolism"], "symbolists": ["Symbolism"], "surrealists": ["Surrealism"], "dada": ["Dadaism"],
    "pre-raphaelites": ["Pre-Raphaelitism"], "formalists": ["Formalism (Russian)"],
    "russian formalism": ["Formalism (Russian)"], "cyclic": ["Cyclic Drama"], "cyclic plays": ["Cyclic Drama"],
    "miracle": ["Miracle Play"], "saints’ plays": ["Miracle Play"], "saints’": ["Saints’ Lives"],
    "kabuki plays": ["Kabuki"], "metaphysical poets": ["Metaphysical Poetry"],
    "confidante": ["Confidant (feminine, Confidante)"], "kabbalism": ["Kabbalah (also Cabala, Caballa, Kaballa)"],
    "jn memoriam stanza": ["In Memoriam Stanza"], "iv medias res": ["In Medias Res"],
    "commedia dell’ arte": ["Commedia dell’Arte"], "girt books": ["Gift Books"], "poets laureate": ["Poet Laureate"],
    "new critics": ["New Criticism"], "household poets": ["Fireside Poets"], "half": ["Half Rhyme"],
    "slant": ["Slant Rhyme"], "editorial page": ["Editorial"], "roman policier": ["Policier"],
    "popular etymology": ["Folk Etymology"], "long cross": ["Dagger"], "consonance rhyme": ["Consonance"],
    "distributed stress": ["Hovering Stress (or Accent)"], "seven liberal arts": ["Liberal Arts"],
    "local color": ["Local Color Writing"], "standard habbie": ["Habbie"], "agrarianism": ["Agrarians"],
    "restoration": ["Restoration Age"], "dramatic propriety": ["Decorum"],
    "end-stopped": ["End-Stopped Lines"], "one-act": ["One-Act Play"], "feet": ["Foot"],
    "choral": ["Chorus"], "choric": ["Chorus"], "amphisbaenic": ["Amphisbaenic Rhyme"],
    "femmes fatales": ["Femme Fatale"], "horn-book": ["Hornbook"], "fleshly school": ["Fleshly School of Poetry, The"],
    "age of the romantic movement": ["Age of the Romantic Movement in England, 1798-1832"],
    "romantic movement": ["Age of the Romantic Movement in England, 1798-1832"],
    "topographical": ["Topographical Poetry"], "topographical poems": ["Topographical Poetry"],
    "detective novel": ["Detective Story"], "play on words": ["Pun"], "old english language": ["Old English (Language)"],
    "tail rhyme stanza": ["Tail-Rhyme Stanza"], "tail-rhyme": ["Tail-Rhyme Stanza"],
    "english": ["English Sonnet"], "italian": ["Italian Sonnet"], "sleight of": ["Sleight of “and”"],
    "successive": ["Successive Patterning"], "alternating": ["Alternating Patterning"],
    "fabliaux": ["Fabliau (plural, Fabliaux)"], "nonsense": ["Nonsense Verse"], "scholia": ["Scholium (plural Scholia)"],
    "self-effacing": ["Self-Effacing Author"], "tableaux": ["Tableau"], "primitive": ["Primitivism"],
    "catalectic": ["Catalexis"], "pyramid": ["Freytag’s Pyramid"], "sinking": ["Dip"],
    "apocalypse": ["Apocalyptic"], "prose-rhythm": ["Prose Rhythm"], "prose-rhythms": ["Prose Rhythm"],
    "schlusselroman": ["Roman à Clef"], "motion pictures": ["Motion Picture"],
    # periods
    "romantic period": ["Romantic Period in English Literature, 1798-1870", "Romantic Period in American Literature, 1830-1865"],
    "realistic period": ["Realistic Period in English Literature, 1870-1914", "Realistic Period in American Literature, 1865-1900"],
    "victorian age": ["Victorian"], "caroline age": ["Caroline"], "augustan age": ["Augustan"],
    "renaissance period": ["Renaissance"], "modernist period": ["Modernist Period in English Literature"],
    "present postmodernist": ["Postmodernist Period in English Literature, 1965—"],
    "contemporary period": ["Postmodernist Period in English Literature, 1965—"],
    "federalist age": ["Federalist Age in American Literature"],
    "colonial period": ["Colonial Period in American Literature, 1607-1765"],
    "revolutionary and early national period": ["Revolutionary and Early National Period in American Literature, 1765-1830"],
    "naturalistic and symbolistic period": ["Naturalistic and Symbolistic Period in American Literature"],
    "period of conformity and criticism": ["Period of Modernism and Consolidation in American Literature, 1930-1960"],
    "period of the confessional self": ["Period of Confession and Postmodernism in American Literature, 1960—"],
    "postmodern period": ["Period of Confession and Postmodernism in American Literature, 1960—"],
}


# Aliases used only on pages whose title contains one of these words (or that link the term),
# so "ITALIAN writers" in another entry stays plain text.
ALIAS_CONTEXT = {"english": ("sonnet", "stanza", "quatrain"), "italian": ("sonnet", "stanza", "quatrain")}


class Resolver:
    """Finds records by name, for text fields that hold names instead of links."""

    def __init__(self, db):
        self.by_name = {k: {} for k in db}
        self.secondary = {k: {} for k in db}
        for key, recs in db.items():
            for r in sorted(recs.values(), key=lambda r: r["id"], reverse=True):
                for n in self.name_variants(r["title"]):
                    self.by_name[key][n] = r["id"]
                for n in self.secondary_variants(r["title"]):
                    self.secondary[key].setdefault(n, r["id"])
                if key == "authors" and r.get("alternate"):
                    for alt in re.split(r"[;,]", r["alternate"]):
                        for n in self.name_variants(alt):
                            self.secondary[key].setdefault(n, r["id"])
        self.aliases = {}
        self.term_titles = {i: r["title"] for i, r in db.get("terms", {}).items()}
        if "terms" in db:
            for phrase, names in XREF_ALIASES.items():
                ids = [self.by_name["terms"].get(fold(n)) for n in names]
                ids = [i for i in ids if i]
                if ids:
                    self.aliases[fold(phrase)] = ids

    @staticmethod
    def clean(name):
        name = DATE_SUFFIX.sub("", name.strip()).strip()
        return name.strip(QUOTES).strip()

    @staticmethod
    def name_variants(name):
        name = name.strip()
        if not name:
            return []
        out = {fold(name)}
        for nm in {name, Resolver.clean(name)}:
            out.add(fold(nm))
            m = re.match(r"^(.*?)\s*\((?:or|also|also called|sometimes)\s+(.*?)\)\s*$", nm, re.I)
            if m:
                out.add(fold(m.group(1)))
                for alt in re.split(r",|\bor\b", m.group(2)):
                    if alt.strip():
                        out.add(fold(alt.strip()))
            base = re.sub(r"\s*\(.*?\)\s*", " ", nm).strip()
            for b in {nm, base}:
                if b:
                    out.add(fold(b))
                m = re.match(r"^(.*),\s*(the|a|an)$", b, re.I)
                if m:
                    out.add(fold(f"{m.group(2)} {m.group(1)}"))
                    out.add(fold(m.group(1)))
        return [o.strip() for o in out if o.strip()]

    @staticmethod
    def secondary_variants(name):
        """Weaker matches: each name in "Skald, Scald" or "Lake Poets and Lake School",
        and inverted names such as "Forgeries, Literary" read as "Literary Forgeries"."""
        nm = re.sub(r"\s*\(.*?\)\s*", " ", Resolver.clean(name)).strip()
        out = set()
        if "," in nm:
            first, rest = nm.split(",", 1)
            rest = rest.strip()
            out.add(fold(f"{rest} {first}"))
            for part in [first] + rest.split(","):
                if part.strip():
                    out.add(fold(part.strip()))
        elif re.search(r"\band\b", nm):
            parts = re.split(r"\s+and\s+", nm)
            if len(parts) == 2 and all(1 <= len(x.split()) <= 3 for x in parts):
                out.update(fold(x) for x in parts)
        out.discard(fold(nm))
        return [o for o in out if o]

    def find(self, key, name):
        k = fold(name.strip())
        return self.by_name[key].get(k) or self.secondary[key].get(k)

    def find_term(self, name, prefer=(), title=""):
        """Term for a cross-reference: exact or alternate name first, then the curated aliases."""
        hit = self.find("terms", name)
        if hit:
            return hit
        ids = self.aliases.get(fold(name.strip()))
        if not ids:
            return None
        for i in ids:
            if i in prefer:
                return i
        need = ALIAS_CONTEXT.get(fold(name.strip()))
        if need and not any(w in fold(title) for w in need):
            return None
        for word in ("american", "english"):
            if word in fold(title):
                for i in ids:
                    if word in fold(self.term_titles.get(i, "")):
                        return i
        return ids[0]


# ---------------------------------------------------------------- rich text

def number_forms(word):
    """Singular and plural spellings of a capitalized word, for matching cross-references."""
    out = []
    for suffix, rep in (("'S", ""), ("’S", ""), ("IES", "Y"), ("ES", ""), ("S", "")):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            out.append(word[: -len(suffix)] + rep)
    if word.endswith("Y") and len(word) > 2 and word[-2] not in "AEIOU":
        out.append(word[:-1] + "IES")
    elif word.endswith(("S", "X", "Z", "CH", "SH")):
        out.append(word + "ES")
    else:
        out.append(word + "S")
    return out


CAP = r"[A-ZÀ-Þ][A-ZÀ-Þ’'\-]+"
CAPS_PHRASE = CAP + r"(?:\s+(?:OF|AND|THE|IN|A|" + CAP + r"))*"
XREF_PHRASE = re.compile(r"(?<![\w/#&])(?:A\s+)?" + CAPS_PHRASE + r"(?![\w])")
XREF_JOIN = re.compile(r"\s*,\s*|\s*[(\[]\s*|\s*[~—]\s*")
CONNECTORS = {"OF", "AND", "THE", "IN", "A"}


def autolink_caps(text_html, ctx):
    """In definitions, words set in CAPITALS are cross-references to other terms."""
    if not ctx:
        return text_html
    db, resolver, prefer = ctx[:3]
    title = ctx[3] if len(ctx) > 3 else ""

    def lookup(text):
        """Term id for a reference, trying singular/plural forms and dropping a leading THE/A/AND/OF."""
        words = html.unescape(text).split()
        forms = [words]
        while len(words) > 1 and words[0] in CONNECTORS:
            words = words[1:]
            forms.append(words)
        if not words or len(re.sub(r"[^A-ZÀ-Þ]", "", "".join(words))) < 3:
            return None
        candidates = []
        for ws in forms:
            candidates.append(" ".join(ws))
            heads = [len(ws) - 1] + [i - 1 for i, w in enumerate(ws) if w == "OF" and i > 0]
            for i in heads:
                for form in number_forms(ws[i]):
                    c = " ".join(ws[:i] + [form] + ws[i + 1:])
                    if c not in candidates:
                        candidates.append(c)
        for c in candidates:
            key = fold(c)
            hits = [x for x in prefer if x in db["terms"] and key in Resolver.name_variants(db["terms"][x]["title"])]
            tid = hits[0] if hits else resolver.find_term(c, prefer, title)
            if tid:
                return tid
        return None

    def link(text, tid):
        return f'<a class="xref" href="{db["terms"][tid]["url"]}">{text.lower()}</a>'

    def single(phrase):
        tid = lookup(phrase)
        if tid:
            return link(phrase, tid)
        # No term for the whole phrase: link it in pieces ("IAMBIC PENTAMETER", "TENOR AND VEHICLE"),
        # but only when every word other than AND/OF/THE belongs to a linked piece.
        parts = re.split(r"(\s+)", phrase)
        words, gaps = parts[0::2], parts[1::2] + [""]
        out, i, missed = "", 0, False
        while i < len(words):
            for j in range(len(words), i, -1):
                if words[i] in CONNECTORS or words[j - 1] in CONNECTORS:
                    continue
                piece = "".join(w + g for w, g in zip(words[i:j], gaps[i:j - 1] + [""]))
                tid = lookup(piece)
                if tid:
                    out += link(piece, tid) + gaps[j - 1]
                    i = j
                    break
            else:
                missed = missed or words[i] not in CONNECTORS
                out += words[i] + gaps[i]
                i += 1
        return phrase if missed else out

    sleight = resolver.find_term("Sleight of “and”")
    if sleight:
        text_html = re.sub(r"SLEIGHT OF ‘AND,?’",
                           lambda m: link(m.group(0), sleight), text_html)
    matches = [m for m in XREF_PHRASE.finditer(text_html)
               if not re.search(r'class="xref"[^>]*>[^<]*$', text_html[:m.start()])]
    out, pos, k = [], 0, 0
    while k < len(matches):
        m = matches[k]
        out.append(text_html[pos:m.start()])
        # A reference split in two: "ABSURD, THEATER OF THE", "FORMALISM (RUSSIAN)", "TAIL~RHYME STANZA".
        if k + 1 < len(matches):
            n = matches[k + 1]
            sep = text_html[m.end():n.start()]
            if XREF_JOIN.fullmatch(sep):
                a_, b_ = m.group(0), n.group(0)
                bracket = "(" in sep or "[" in sep
                close = text_html[n.end():n.end() + 1] if bracket and text_html[n.end():n.end() + 1] in ")]" else ""
                combos = ([f"{a_} ({b_})"] if bracket else []) + \
                         ([f"{a_}-{b_}"] if "~" in sep or "—" in sep else []) + [f"{b_} {a_}", f"{a_}, {b_}", f"{a_} {b_}"]
                tid = next((x for x in (lookup(c) for c in combos) if x), None)
                if tid:
                    out.append(link(a_, tid) + sep + link(b_, tid) + close)
                    pos = n.end() + len(close)
                    k += 2
                    continue
        out.append(single(m.group(0)))
        pos = m.end()
        k += 1
    out.append(text_html[pos:])
    return "".join(out)


def inline_md(s, ctx=None):
    parts = re.split(r"(\[[^\]]+\]\([^)\s]+\)|https?://[^\s<)]+)", s)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            m = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", part)
            if m:
                label, href = m.group(1), m.group(2)
            else:
                label, href = part, part
            out.append(f'<a href="{html.escape(href, quote=True)}" rel="nofollow noopener" target="_blank">'
                       f"{inline_fmt(html.escape(label))}</a>")
        else:
            out.append(autolink_caps(inline_fmt(html.escape(part)), ctx))
    return "".join(out)


def inline_fmt(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", s)
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def md_to_html(text, ctx=None):
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\\", "")
    blocks, out = re.split(r"\n\s*\n", text.strip()), []
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        if all(re.match(r"^\s*[-*+]\s+", l) for l in lines):
            items = "".join(f"<li>{inline_md(re.sub(r'^\s*[-*+]\s+', '', l), ctx)}</li>" for l in lines)
            out.append(f"<ul>{items}</ul>")
        elif all(re.match(r"^\s*\d+[.)]\s+", l) for l in lines):
            items = "".join(f"<li>{inline_md(re.sub(r'^\s*\d+[.)]\s+', '', l), ctx)}</li>" for l in lines)
            out.append(f"<ol>{items}</ol>")
        elif all(l.startswith(">") for l in lines):
            out.append(f"<blockquote><p>{'<br>'.join(inline_md(l.lstrip('> '), ctx) for l in lines)}</p></blockquote>")
        elif re.match(r"^#{1,6}\s", lines[0]) and len(lines) == 1:
            out.append(f"<h3>{inline_md(lines[0].lstrip('# '), ctx)}</h3>")
        else:
            body = "<br>".join(inline_md(l, ctx) for l in lines)
            cls = ' class="refs"' if re.match(r"^\[?References?:", lines[0]) else ""
            out.append(f"<p{cls}>{body}</p>")
    return "\n".join(out)


# ---------------------------------------------------------------- images

def media_path(att, size=480):
    """Downloads an attachment (fresh link from this build), shrinks it, returns its site URL."""
    if not att:
        return None
    if (att.get("width") or 99) < 8 or (att.get("height") or 99) < 8:
        return None  # 1×1 placeholder images
    if not str(att.get("type", "image/")).startswith("image/"):
        return None
    name = f"{att['id']}.webp"
    cached = MEDIA_CACHE / name
    if not cached.exists():
        thumbs = att.get("thumbnails") or {}
        src = (thumbs.get("large") or {}).get("url") or att["url"]
        try:
            from PIL import Image
            with urllib.request.urlopen(src, timeout=60) as r:
                data = r.read()
            im = Image.open(io.BytesIO(data))
            if im.width < 8 or im.height < 8:
                return None
            im = im.convert("RGB")
            im.thumbnail((size, size * 2))
            MEDIA_CACHE.mkdir(exist_ok=True)
            im.save(cached, "WEBP", quality=80)
        except Exception as e:  # a broken image shouldn't stop the build
            print(f"  image skipped ({att.get('filename')}): {e}", file=sys.stderr)
            return None
    return f"{BASE}media/{name}"


def prepare_media(db):
    jobs = []
    for a in db["authors"].values():
        if a["picture"]:
            jobs.append(("authors", a["id"], a["picture"][0]))
    for w in db["works"].values():
        att = next((x for x in w["cover"] + w["alt_cover"] if (x.get("width") or 99) >= 8), None)
        if att:
            jobs.append(("works", w["id"], att))
    results = {}
    print(f"Preparing {len(jobs)} images…", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(media_path, att): (k, rid) for k, rid, att in jobs}
        for f in concurrent.futures.as_completed(futs):
            results[futs[f]] = f.result()
    for (k, rid), url in results.items():
        db[k][rid]["image"] = url
    (OUT / "media").mkdir(parents=True, exist_ok=True)
    used = {Path(u).name for u in results.values() if u}
    for name in used:
        shutil.copyfile(MEDIA_CACHE / name, OUT / "media" / name)


# ---------------------------------------------------------------- HTML helpers

e = html.escape


# Short forms take quotation marks; books, plays, long poems, films and periodicals take italics.
QUOTED_TYPES = {"poem", "short story", "essay", "song", "speech", "sermon"}


def work_title_html(w):
    t = e(w["title"])
    types = {x.strip().lower() for x in w.get("type", [])}
    return f"“{t}”" if types and types <= QUOTED_TYPES else f"<i>{t}</i>"


def rec_link(db, key, rid, cls="chip"):
    r = db[key][rid]
    label = work_title_html(r) if key == "works" else e(r["title"])
    return f'<a class="{cls}" href="{r["url"]}">{label}</a>'


def chips(db, key, ids, sort=True, limit=None):
    ids = list(dict.fromkeys(ids))
    if not ids:
        return ""
    if sort:
        ids.sort(key=lambda i: author_sort(db[key][i]) if key == "authors" else sort_key(db[key][i]["title"]))
    shown = ids if limit is None else ids[:limit]
    html_ = "".join(rec_link(db, key, i) for i in shown)
    if limit is not None and len(ids) > limit:
        rest = "".join(rec_link(db, key, i) for i in ids[limit:])
        html_ += f'<details class="more"><summary>{len(ids) - limit} more</summary>{rest}</details>'
    return f'<div class="chips">{html_}</div>'


def section(title, body, count=None):
    if not body:
        return ""
    c = f' <span class="count">{count}</span>' if count else ""
    return f'<section class="block"><h2>{e(title)}{c}</h2>{body}</section>'


def facts(rows):
    rows = [(k, v) for k, v in rows if v]
    if not rows:
        return ""
    return '<dl class="facts">' + "".join(f"<dt>{e(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>"


def ext_link(url, label):
    if not url or not re.match(r"^https?://", url):
        return ""
    return f'<a class="ext" href="{e(url, quote=True)}" target="_blank" rel="noopener">{e(label)} ↗</a>'


def page(title, body, active=None, description="", path="", extra_head=""):
    mode = "home" if active == "home" else "study" if active in STUDY_KEYS else "ref" if active else ""
    nav = (f'<a class="navlink" href="{BASE}"{" aria-current=page" if mode == "home" else ""}>Home</a>'
           + nav_menu("ref", "Reference", "reference/", mode == "ref", NAV_MENUS.get("ref", ""))
           + nav_menu("study", "Study", "study/", mode == "study", NAV_MENUS.get("study", "")))
    full_title = f"{title} · {SITE_TITLE}" if title != SITE_TITLE else SITE_TITLE
    desc = e(re.sub(r"\s+", " ", description).strip()[:300], quote=True)
    canon = f'<link rel="canonical" href="{SITE_URL}{path}">' if SITE_URL else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{e(full_title, quote=True)}">
<meta property="og:description" content="{desc}">
{canon}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{BASE}assets/style.css?v={BUILD_ID}">
<link rel="icon" href="{BASE}assets/icon.svg" type="image/svg+xml">
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer = window.dataLayer || []; function gtag(){{dataLayer.push(arguments);}} gtag('js', new Date()); gtag('config', '{GA_ID}');</script>
{extra_head}
</head>
<body class="mode-{mode or 'none'}">
<header class="top">
  <div class="wrap top-inner">
    <a class="brand" href="{BASE}"><span class="mark">¶</span>{e(SITE_TITLE)}</a>
    <form class="search" action="{BASE}search/" role="search" autocomplete="off">
      <input type="search" name="q" placeholder="Search terms, authors, works…" aria-label="Search" data-search>
      <div class="results" hidden data-results></div>
    </form>
    <a class="acct-link" href="{BASE}account/" data-acct hidden>Sign in</a>
  </div>
  <nav class="wrap nav" aria-label="Main">{nav}</nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap">Updated {BUILD_DATE} · <a href="{BASE}">{e(SITE_TITLE)}</a></div></footer>
<script>window.SITE_BASE = "{BASE}"; window.LITCRIT_AUTH = {json.dumps({"url": SUPABASE_URL, "key": SUPABASE_KEY, "lib": SUPABASE_LIB})};</script>
<script src="{BASE}assets/auth.js?v={BUILD_ID}"></script>
<script src="{BASE}assets/nav.js?v={BUILD_ID}" defer></script>
<script src="{BASE}assets/search.js?v={BUILD_ID}" defer></script>
<script src="{BASE}assets/quiz.js?v={BUILD_ID}" defer></script>
<script src="{BASE}assets/flag.js?v={BUILD_ID}" defer></script>
</body>
</html>
"""


def write(path, content):
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def crumbs(key, label):
    return f'<p class="crumbs"><a href="{BASE}{folder(key)}/">{label}</a></p>'


# ---------------------------------------------------------------- record pages

def term_page(db, rel, resolver, t, periods_by_term):
    tid = t["id"]
    related = list(dict.fromkeys(t["related"]))
    mentioned = [x for x in t["mentioned"] if x not in related]
    mentioned_in = rel[("terms", tid)].get("rev:terms:mentioned", [])
    related_by = [x for x in rel[("terms", tid)].get("rev:terms:related", []) if x not in related and x not in mentioned_in]
    ctx = (db, resolver, t["mentioned"] + t["related"], t["title"])
    tq = rel[('terms', tid)].get('questions', [])
    exs = term_examples(db, rel, tid)
    apps = int(float(t["appearances"] or 0))
    stats = facts([("Test appearances", f"{apps:,}" if apps else ""), ("Practice questions", f"{len(tq):,}" if tq else "")])
    body = f"""{crumbs('terms', 'Terms')}
<div class="with-aside">
<article class="record">
<h1 data-record="{t['id']}">{e(t['title'])}</h1>
{f'<p class="lede">{e(t["short"])}</p>' if t['short'] else ''}
<div class="prose">{md_to_html(t['definition'], ctx)}</div>
</article>
<div class="aside">
{study_box("term", "term", tid, len(tq), add_card_slot('t', t))}
{f'<div class="statbox">{stats}</div>' if stats else ''}
</div>
</div>
{f'<div id="examples">{section("Examples", examples_list(db, exs), len(exs))}</div>' if exs else ''}
{section('Related terms', chips(db, 'terms', related), len(related))}
{section('Terms mentioned', chips(db, 'terms', mentioned), len(mentioned))}
{section('Mentioned in', chips(db, 'terms', mentioned_in, limit=40), len(mentioned_in))}
{section('Also see', chips(db, 'terms', related_by, limit=40), len(related_by))}
{section('Periods', chips(db, 'periods', periods_by_term.get(tid, [])))}
{section('Authors', chips(db, 'authors', rel[('terms', tid)].get('authors', []), limit=40), len(rel[('terms', tid)].get('authors', [])))}
{section('Sets', chips(db, 'tags', rel[('terms', tid)].get('tags', [])))}
{questions_section(db, tq, 'term', 'term', tid)}
"""
    write(f"terms/{t['slug']}/index.html",
          page(t["title"], body, "terms", t["short"] or t["definition"][:200], f"terms/{t['slug']}/", extra_head=FC_SCRIPT))


def author_page(db, rel, resolver, a):
    aid = a["id"]
    years = " – ".join(x for x in (a["birth"], a["death"]) if x)
    img = a.get("image") or (a["picture_url"] if re.match(r"^https?://", a["picture_url"]) else None)
    portrait = f'<img class="portrait" src="{e(img, quote=True)}" alt="Portrait of {e(a["title"], quote=True)}" loading="lazy" onerror="this.remove()">' if img else ""
    group_ids = [x for x in (resolver.find("terms", g) for g in a["groups"]) if x]
    period_term_ids = [x for x in (resolver.find("terms", p) for p in a["periods"]) if x]
    links = " ".join(x for x in (ext_link(a["wikipedia"], "Wikipedia"), ext_link(a["youtube"], "Video")) if x)
    meta = facts([
        ("Nationality", e(a["nationality"])),
        ("Known as", e(", ".join(a["medium"]))),
        ("Also known as", e(a["alternate"])),
    ])
    works = rel[("authors", aid)].get("works", [])
    prizes = rel[("authors", aid)].get("prizes", [])
    terms = rel[("authors", aid)].get("terms", [])
    prizes.sort(key=lambda p: db["prizes"][p]["year"] or "0")
    prize_list = "".join(f'<li><a href="{db["prizes"][p]["url"]}">{e(db["prizes"][p]["title"])}</a></li>' for p in prizes)
    body = f"""{crumbs('authors', 'Authors')}
<article class="record person">
{portrait}
<div>
<h1 data-record="{a['id']}">{e(a['title'])}</h1>
{f'<p class="lede">{e(years)}</p>' if years else ''}
{meta}
{f'<p class="links">{links}</p>' if links else ''}
{study_box("author", "author", aid, len(rel[('authors', aid)].get('questions', [])), add_card_slot('a', a))}
</div>
</article>
{section('Works', work_list(db, works), len(works))}
{section('Prizes', f'<ul class="plain">{prize_list}</ul>' if prize_list else '', len(prizes))}
{section('Movements and groups', chips(db, 'terms', group_ids))}
{section('Periods', chips(db, 'terms', period_term_ids))}
{section('Appears in these terms', chips(db, 'terms', terms, limit=60), len(terms))}
{section('Poems and passages', chips(db, 'poems', rel[('authors', aid)].get('poems', [])), len(rel[('authors', aid)].get('poems', [])))}
{section('Reading lists', reading_list_links(db, rel[('authors', aid)].get('reading-lists', [])))}
{questions_section(db, rel[('authors', aid)].get('questions', []), 'author', 'author', aid)}
"""
    desc = f"{a['title']} ({years}). " + (f"{a['nationality']} {', '.join(a['medium']).lower()}." if a["nationality"] else "")
    write(f"authors/{a['slug']}/index.html", page(a["title"], body, "authors", desc, f"authors/{a['slug']}/", extra_head=FC_SCRIPT))


def work_list(db, ids):
    if not ids:
        return ""
    ids = sorted(ids, key=lambda w: (db["works"][w]["year_written"] or "9999", sort_key(db["works"][w]["title"])))
    items = []
    for w in ids:
        r = db["works"][w]
        year = r["year_written"] or r["published"]
        star = '<span class="star" title="Notable">★</span>' if r["notable"] else ""
        items.append(f'<li><a href="{r["url"]}">{work_title_html(r)}</a>{star}'
                     f'{f" <span class=muted>{e(year)}</span>" if year else ""}</li>')
    return f'<ul class="plain cols">{"".join(items)}</ul>'


def cover_html(w):
    if w.get("image"):
        return f'<img class="cover" src="{w["image"]}" alt="Cover of {e(w["title"], quote=True)}" loading="lazy">'
    url = w["cover_url"]
    if url and re.search(r"/isbn/\d{10,13}-", url):
        url = url + ("&" if "?" in url else "?") + "default=false"
        return f'<img class="cover" src="{e(url, quote=True)}" alt="Cover of {e(w["title"], quote=True)}" loading="lazy" onerror="this.remove()">'
    return ""


def work_page(db, rel, resolver, w):
    wid = w["id"]
    authors = rel[("works", wid)].get("authors", [])
    by = ", ".join(f'<a href="{db["authors"][a]["url"]}">{e(db["authors"][a]["title"])}</a>' for a in authors)
    term_ids = [x for x in (resolver.find("terms", s) for s in re.split(r"[;,]", w["terms_text"])) if x]
    prizes = rel[("works", wid)].get("prizes", [])
    prize_list = "".join(f'<li><a href="{db["prizes"][p]["url"]}">{e(db["prizes"][p]["title"])}</a></li>' for p in prizes)
    isbn = w["isbn"] if re.fullmatch(r"\d{13}", w["isbn"] or "") else ""
    meta = facts([
        ("Written", e(w["year_written"])),
        ("Published", e(w["published"])),
        ("Form", e(", ".join(w["type"]))),
        ("Language", e(", ".join(w["language"]))),
        ("Pages", e(w["pages"])),
        ("ISBN", e(isbn)),
        ("Reading list", e(", ".join(w["reading_list"]))),
        ("Tags", e(w["tags_text"])),
    ])
    resources = [r for r in db["resources"].values() if resolver.find("works", ", ".join(r["work"])) == wid
                 or any(resolver.find("works", x) == wid for x in r["work"])]
    res_list = ""
    for r in resources:
        yr = f' <span class="muted">{e(r["year"])}</span>' if r["year"] else ""
        res_list += f'<li>{ext_link(r["link"], r["title"]) or e(r["title"])}{yr}</li>'
    star = ' <span class="star" title="Notable">★</span>' if w["notable"] else ""
    body = f"""{crumbs('works', 'Works')}
<article class="record work">
{cover_html(w)}
<div>
<h1 data-record="{w['id']}">{work_title_html(w)}{star}</h1>
{f'<p class="lede">by {by}</p>' if by else ''}
{meta}
{study_box("work", "work", wid, len(rel[('works', wid)].get('questions', [])), add_card_slot('w', w))}
</div>
</article>
{section('Synopsis', f'<div class="prose">{md_to_html(w["synopsis"])}</div>' if w['synopsis'] else '')}
{section('Prizes', f'<ul class="plain">{prize_list}</ul>' if prize_list else '')}
{section('Terms', chips(db, 'terms', term_ids))}
{section('Reading resources', f'<ul class="plain">{res_list}</ul>' if res_list else '')}
{section('Reading lists', reading_list_links(db, rel[('works', wid)].get('reading-lists', [])))}
{questions_section(db, rel[('works', wid)].get('questions', []), 'work', 'work', wid)}
"""
    author_names = ", ".join(db["authors"][a]["title"] for a in authors)
    desc = (w["synopsis"] or f"{w['title']}" + (f" by {author_names}" if author_names else ""))[:250]
    write(f"works/{w['slug']}/index.html", page(w["title"], body, "works", desc, f"works/{w['slug']}/", extra_head=FC_SCRIPT))


# ---------------------------------------------------------------- practice tests, poems, reading lists

def test_label(db, q):
    t = db["tests"].get(q["test"][0]) if q["test"] else None
    num = f" · #{q['number']}" if q["number"] else ""
    return (t["title"] if t else "") + num


def test_sort(t):
    try:
        year = int(re.match(r"\d{4}", t["year"] or t["title"]).group(0))
    except Exception:
        year = 0
    return (-year, sort_key(t["type"] or t["title"]))


def questions_section(db, qids, about="term", quiz_param="", rid="", limit=10, skip_poem=None):
    """Practice questions on a reference page, folded into one box that opens on request."""
    qids = [q for q in dict.fromkeys(qids) if db["questions"][q]["url"]]
    if not qids:
        return ""
    qids.sort(key=lambda q: (test_sort(db["tests"][db["questions"][q]["test"][0]]),
                             int(db["questions"][q]["number"] or 0)))
    # A question that depends on a passage carries it: open the first time it appears on the page,
    # folded on later questions that share it. A poem's own page already shows its text, so it is skipped.
    shown = {("skip", skip_poem)} if skip_poem else set()

    def one(q):
        return question_html(db, db["questions"][q], in_test=False, shown_passages=shown)
    items = "".join(one(q) for q in qids[:limit])
    more = ""
    if len(qids) > limit:
        more = (f'<details class="more more-q"><summary>{len(qids) - limit} more questions</summary>'
                f'<ol class="plain questions compact">'
                + "".join(one(q) for q in qids[limit:])
                + "</ol></details>")
    n = len(qids)
    heading = "Questions about this text" if about == "text" else f"Practice questions that mention this {about}"
    quiz = (f'<p class="qfold-quiz"><a href="{BASE}study/quiz/?{quiz_param}={rid}">Or take a {min(n, 10)}-question quiz instead →</a></p>'
            if quiz_param and n > 1 else "")
    # Outside practice tests, each question is marked as soon as a choice is clicked, and nothing is saved.
    return (f'<details class="qfold" id="practice"><summary><span class="qfold-text"><b>{heading}</b>'
            f'<span>{n} question{"s" if n != 1 else ""} from released tests</span></span>'
            f'<span class="qfold-cta" aria-hidden="true"></span></summary>'
            f'<div class="qfold-body">{quiz}<div class="quiz" data-instant>'
            f'<ol class="plain questions compact">{items}</ol>{more}</div></div></details>')


def question_passages(db, q, shown):
    """The passage(s) a question is about, for questions shown outside their practice test.
    `shown` holds passages already printed on the page; ("skip", id) marks one the page itself shows."""
    out = ""
    for pid in q["poems"]:
        p = db["poems"].get(pid)
        if not p or ("skip", pid) in shown:
            continue
        first = pid not in shown
        shown.add(pid)
        text = (f'<div class="poem">{multiline(p["text"])}</div>' if p["text"]
                else '<p class="muted">The text of this passage isn’t in the database yet.</p>')
        label = "Passage" if first else "Passage (also above)"
        out += (f'<details class="qpassage"{" open" if first else ""}><summary><span class="passage-label">{label}</span> '
                f'<span class="qpassage-title">{e(p["title"])}</span></summary>'
                f'{text}<p class="qpassage-link"><a href="{p["url"]}">Open {e(p["title"])}</a></p></details>')
    return out


def reading_list_links(db, ids):
    ids = sorted(dict.fromkeys(ids), key=lambda i: db["reading-lists"][i]["title"], reverse=True)
    if not ids:
        return ""
    links = "".join(f'<a class="chip" href="{db["reading-lists"][i]["url"]}">{e(db["reading-lists"][i]["title"])}</a>'
                    for i in ids)
    return f'<div class="chips">{links}</div>'


def multiline(text):
    return "<br>".join(e(line) for line in text.strip().split("\n"))


def question_part(q):
    m = re.search(r"\d+", q["part"] or "")
    return m.group(0) if m else ""


def part2_section(db, rel, q):
    """Part 2 covers the reading list: the novel, the play, and the poet's poems."""
    for w in q["rl_works"]:
        lists = rel[("works", w)].get("reading-lists", [])
        if any(w in db["reading-lists"][x]["novel"] for x in lists):
            return "Novel"
        if any(w in db["reading-lists"][x]["play"] for x in lists):
            return "Play"
        types = {x.lower() for x in db["works"][w]["type"]}
        if types & {"play", "musical"}:
            return "Play"
        if types & {"novel", "novella"}:
            return "Novel"
    if q["poems"] or not q["rl_works"]:
        return "Poetry"
    return ""


def question_points(q):
    """Part 1 questions are worth 1 point; Parts 2 and 3 are worth 2."""
    return 1 if q["part"].strip().lower() in ("part 1", "part i", "1") else 2


def is_redacted(q):
    text = (q["prompt"] or q["name"]).lower()
    return "redacted" in text or "omitted" in text


def question_html(db, q, in_test=True, rel=None, shown_passages=None):
    """One practice question. Choices are buttons; picking one marks every choice right or wrong
    and reveals the links (assets/quiz.js). Without JavaScript the answer sits behind "Show answer"."""
    letters = [l for l in "abcde" if q[l]]
    correct = [c.strip().upper() for c in q["correct"] if c.strip()]
    answer = ", ".join(
        f"{c}. {e(q[c.lower()])}" if c.lower() in "abcde" and q.get(c.lower()) else e(c) for c in correct)
    choices = "".join(
        f'<li><button type="button" class="choice" data-letter="{l.upper()}" aria-pressed="false">'
        f'<span class="cletter">{l.upper()}</span><span class="ctext">{e(q[l])}</span>'
        f'<span class="cmark" aria-hidden="true"></span></button></li>'
        for l in letters)
    links = []
    for p in q["poems"]:
        links.append(f'<a href="{db["poems"][p]["url"]}">{e(db["poems"][p]["title"])}</a>')
    for k in ("works", "authors"):
        for x in q[k]:
            r = db[k][x]
            links.append(f'<a href="{r["url"]}">{work_title_html(r) if k == "works" else e(r["title"])}</a>')
    terms = sorted(q["terms"], key=lambda t: sort_key(db["terms"][t]["title"]))
    term_links = ", ".join(f'<a href="{db["terms"][t]["url"]}">{e(db["terms"][t]["title"])}</a>' for t in terms)
    source = ""
    if not in_test and q["url"]:
        source = f'<p class="qsource"><a href="{q["url"]}">{e(test_label(db, q))}</a></p>'
    num = e(q["number"]) if in_test else ""
    anchor = f' id="q-{q["id"]}"' if in_test else ""
    pts = question_points(q)
    auto = is_redacted(q) or not correct or not choices
    if auto:
        why = ("This item was left out of the released test" if is_redacted(q) or not choices
               else "No answer is recorded for this question")
        choices = ""
        answer = ""
        note = f'<p class="qauto">{why}, so its {pts} point{"s" if pts != 1 else ""} {"are" if pts != 1 else "is"} given automatically.</p>'
    else:
        note = ""
    part = question_part(q)
    section = part2_section(db, rel, q) if rel is not None and part == "2" else ""
    meta = f' data-part="{part}"' + (f' data-section="{section}"' if section else "")
    return f"""<li class="q{' auto' if auto else ''}"{anchor}{meta} data-qid="{q['id']}" data-correct="{e(''.join(correct), quote=True)}" data-points="{pts}"{' data-auto="1"' if auto else ''}>
<div class="qnum">{num}</div>
<div class="qbody">
{source}
{question_passages(db, q, shown_passages) if shown_passages is not None else ''}
<p class="prompt">{multiline(q['prompt'] or q['name'])}</p>
{f'<ol class="plain choices">{choices}</ol>' if choices else ''}
{note}
<p class="qresult" aria-live="polite"></p>
{f'<details class="answer"><summary>Show answer</summary><p>{answer}</p></details>' if answer else ''}
<div class="qlinks">
{f'<p class="qmeta">About: {" · ".join(links)}</p>' if links else ''}
{f'<p class="qmeta">Terms: {term_links}</p>' if term_links else ''}
</div>
</div>
</li>"""


def score_bar(total_points, n_questions, test=True):
    label = "Score" if test else "Points"
    return f"""<div class="scorebar" data-scorebar data-test="{'1' if test else '0'}" hidden>
  <div class="sb-main"><span class="sb-label">{label}</span> <strong data-sb-score>0</strong><span class="sb-of"> / {total_points}</span></div>
  <div class="sb-stats"><span data-sb-answered>0 of {n_questions} answered</span><span data-sb-acc></span></div>
  <button type="button" class="sb-clear" data-sb-clear hidden>Clear my answers</button>
  <div class="sb-track" aria-hidden="true"><span class="sb-fill-right" data-sb-right></span><span class="sb-fill-wrong" data-sb-wrong></span></div>
</div>"""


def passage_html(db, rel, pid, first):
    """A poem or passage printed ahead of the questions about it."""
    p = db["poems"][pid]
    authors = rel[("poems", pid)].get("authors", [])
    by = ", ".join(f'<a href="{db["authors"][a]["url"]}">{e(db["authors"][a]["title"])}</a>' for a in authors)
    head = (f'<p class="passage-label">Passage</p><h3 class="passage-title"><a href="{p["url"]}">{e(p["title"])}</a></h3>'
            + (f'<p class="passage-by">by {by}</p>' if by else ""))
    if not first:
        return (f'<div class="passage again">{head}<p class="muted"><a href="#passage-{pid}">See the text above</a></p></div>')
    text = f'<div class="poem">{multiline(p["text"])}</div>' if p["text"] else \
        '<p class="muted">The text of this passage isn’t in the database yet.</p>'
    return f'<div class="passage" id="passage-{pid}">{head}{text}</div>'


def test_part_html(db, rel, qids, shown):
    """Questions in order, with each passage printed before the first question in its set."""
    out, group, current = "", [], None

    def flush():
        nonlocal out, group
        if group:
            out += '<ol class="plain questions">' + "".join(question_html(db, db["questions"][q], rel=rel) for q in group) + "</ol>"
            group = []

    for q in qids:
        poems = tuple(db["questions"][q]["poems"])
        if poems and poems != current:
            flush()
            for pid in poems:
                out += passage_html(db, rel, pid, pid not in shown)
                shown.add(pid)
        current = poems or current
        group.append(q)
    flush()
    return out


def test_page(db, rel, t):
    qids = [q for q in rel[("tests", t["id"])].get("questions", []) if q in db["questions"]]
    qids.sort(key=lambda q: (int(db["questions"][q]["number"] or 0), db["questions"][q]["id"]))
    parts = defaultdict(list)
    for q in qids:
        parts[db["questions"][q]["part"] or ""].append(q)
    poems = []
    for q in qids:
        poems += [p for p in db["questions"][q]["poems"] if p not in poems]
    body = f"""{crumbs('tests', 'Tests')}
<article class="record">
<h1 data-record="{t['id']}">{e(t['title'])}</h1>
<p class="lede">{len(qids)} question{'s' if len(qids) != 1 else ''}. Choose an answer for each one, then press “Score test” in the score bar.</p>
{facts([('Year', e(t['year'])), ('Contest', e(t['type'])), ('Passage', e(t['passage']))])}
</article>
{section('Poems and passages on this test', chips(db, 'poems', poems, sort=False))}
{section('Essay prompt', ''.join(f'<p><a class="chip" href="{x["url"]}">{e(x["title"])} essay prompt</a></p>' for x in db["essays"].values() if essay_test(db, x) is t))}
"""
    total = sum(question_points(db["questions"][q]) for q in qids)
    body += f'<div class="quiz">{score_bar(total, len(qids))}<section class="report" data-report hidden></section>'
    shown_passages = set()
    for part in sorted(parts, key=lambda p: (p == "", p)):
        pts = question_points(db["questions"][parts[part][0]]) if part else 0
        note = f' <span class="count">{pts} point{"s" if pts != 1 else ""} each</span>' if part else ""
        heading = f'<h2 class="letter">{e(part)}{note}</h2>' if part else ""
        body += heading + test_part_html(db, rel, parts[part], shown_passages)
    body += "</div>"
    if total != 100 and qids:
        print(f"  note: {t['title']} totals {total} points ({len(qids)} questions)", flush=True)
    write(f"tests/{t['slug']}/index.html", page(t["title"], body, "tests", f"{len(qids)} practice questions from the {t['title']} test", f"tests/{t['slug']}/"))


def poem_page(db, rel, p):
    pid = p["id"]
    authors = rel[("poems", pid)].get("authors", [])
    by = ", ".join(f'<a href="{db["authors"][a]["url"]}">{e(db["authors"][a]["title"])}</a>' for a in authors)
    tests = sorted(rel[("poems", pid)].get("tests", []), key=lambda x: test_sort(db["tests"][x]))
    essays = [x for x in rel[("poems", pid)].get("essays", []) if x in db["essays"]]
    essay_html = "".join(
        f'<div class="essay"><h3>{e(db["essays"][x]["title"])}</h3><p>{multiline(db["essays"][x]["prompt"])}</p></div>'
        for x in essays)
    body = f"""{crumbs('poems', 'Poems and passages')}
<article class="record">
<h1 data-record="{p['id']}">{e(p['title'])}</h1>
{f'<p class="lede">by {by}</p>' if by else ''}
{study_box("text", "poem", pid, len(rel[('poems', pid)].get('questions', [])), '')}
{f'<div class="poem">{multiline(p["text"])}</div>' if p['text'] else ''}
</article>
{section('Appeared on', chips(db, 'tests', tests, sort=False), len(tests))}
{section('Essay prompts', essay_html, len(essays))}
{questions_section(db, rel[('poems', pid)].get('questions', []), 'text', 'poem', pid, limit=30, skip_poem=pid)}
"""
    names = ", ".join(db["authors"][a]["title"] for a in authors)
    write(f"poems/{p['slug']}/index.html", page(p["title"], body, "poems", f"{p['title']}" + (f" by {names}" if names else ""), f"poems/{p['slug']}/"))


def prize_page(db, rel, p):
    pid = p["id"]
    works = rel[("prizes", pid)].get("works", [])
    authors = rel[("prizes", pid)].get("authors", [])
    body = f"""{crumbs('prizes', 'Prizes')}
<article class="record">
<h1 data-record="{p['id']}">{e(p['title'])}</h1>
{add_card_slot('p', p)}
{facts([('Prize', e(p['type'])), ('Year', e(p['year'])), ('Nationality', e(', '.join(dict.fromkeys(db['authors'][a]['nationality'] for a in authors if db['authors'][a]['nationality']))) if 'nobel' in p['type'].lower() else '')])}
{f'<blockquote class="citation">{e(p["citation"])}</blockquote>' if p['citation'] else ''}
</article>
{section('Winner', chips(db, 'authors', authors))}
{section('Winning work', chips(db, 'works', works))}
"""
    write(f"prizes/{p['slug']}/index.html", page(p["title"], body, "prizes", p["citation"] or p["title"], f"prizes/{p['slug']}/", extra_head=FC_SCRIPT))


def period_page(db, resolver, p):
    years = " – ".join(x for x in (p["start"], p["end"]) if x)
    term_id = resolver.find("terms", p["term_text"]) if p["term_text"] else None
    author_ids, author_plain = [], []
    for n in re.split(r"[;,]", p["authors_text"]):
        n = n.strip()
        if n:
            aid = resolver.find("authors", n)
            (author_ids.append(aid) if aid else author_plain.append(n))
    nav = ""
    if p["before"] or p["after"]:
        prev = "".join(f'<a href="{db["periods"][x]["url"]}">← {e(db["periods"][x]["title"])}</a>' for x in p["before"])
        nxt = "".join(f'<a href="{db["periods"][x]["url"]}">{e(db["periods"][x]["title"])} →</a>' for x in p["after"])
        nav = f'<nav class="seq"><div>{prev}</div><div>{nxt}</div></nav>'
    body = f"""{crumbs('periods', 'Periods')}
<article class="record">
<h1 data-record="{p['id']}">{e(p['title'])}</h1>
{f'<p class="lede">{e(years)}</p>' if years else ''}
{facts([('Region', e(p['region'])), ('Kind', e(p['type']) if p['type'] != 'Period' else '')])}
{f'<div class="prose"><p>{e(p["description"])}</p></div>' if p['description'] else ''}
{f'<p><a class="chip" href="{db["terms"][term_id]["url"]}">Read the full entry: {e(db["terms"][term_id]["title"])}</a></p>' if term_id else ''}
</article>
{nav}
{section('Part of', chips(db, 'periods', p['parent'], sort=False))}
{section('Sub-periods', chips(db, 'periods', sorted(p['subs'], key=lambda x: db['periods'][x]['start'] or '0'), sort=False))}
{section('Authors', chips(db, 'authors', author_ids) + (f'<p class="muted">{e(", ".join(author_plain))}</p>' if author_plain else ''))}
"""
    write(f"periods/{p['slug']}/index.html", page(p["title"], body, "periods", p["description"] or p["title"], f"periods/{p['slug']}/"))


def tag_page(db, rel, g):
    terms = sorted(rel[("tags", g["id"])].get("terms", []), key=lambda t: sort_key(db["terms"][t]["title"]))
    study = " ".join(x for x in (ext_link(g["quizlet"], "Quizlet"), ext_link(g["gimkit"], "Gimkit"),
                                 ext_link(g["blooket"], "Blooket"), ext_link(g["sporcle"], "Sporcle")) if x)
    rows = "".join(list_item(db, "terms", db["terms"][t]) for t in terms)
    body = f"""{crumbs('tags', 'Sets')}
<article class="record">
<h1 data-record="{g['id']}">{e(g['title'])}</h1>
<p class="lede">{len(terms)} term{'s' if len(terms) != 1 else ''}</p>
{f'<p class="links">Study this set: <a href="{BASE}flashcards/tag-{g["slug"]}/">Flashcards</a> {study}</p>' if terms else ''}
</article>
{f'<ul class="plain defs">{rows}</ul>' if rows else ''}
"""
    write(f"sets/{g['slug']}/index.html", page(g["title"], body, "tags", f"{len(terms)} literary terms in the set {g['title']}", f"sets/{g['slug']}/"))


# ---------------------------------------------------------------- flashcards
#
# Card data: assets/cards/{t,a,w,p}.json = {record id: [front, back html, page path, reverse front?]}
#   t = terms (term -> short definition), a = authors (author -> works),
#   w = works (title -> author), p = prizes (prize -> winner).
# A card's id is "<letter>:<record id>", so a term studied in two decks shares one schedule.
# Deck pages list card ids (or "all of a letter"); assets/flashcards.js does the studying,
# the spaced-repetition schedule and custom decks.

CARD_IDS = {"t": set(), "a": set(), "w": set(), "p": set()}
FC_SCRIPT = ""          # set once BASE/BUILD_ID are known (see card_data)
CARD_KINDS = {"t": "terms", "a": "authors", "w": "works", "p": "prizes"}


def add_card_slot(letter, r):
    """Placeholder on a record page; flashcards.js turns it into the "Add to flashcards" button."""
    if r["id"] not in CARD_IDS[letter]:
        return ""
    return f'<div class="fc-add" data-add-card="{letter}:{r["id"]}" data-title="{e(r["title"], quote=True)}" hidden></div>'


def cap_first(s):
    s = (s or "").strip()
    return s[:1].upper() + s[1:]


def year_of(*vals):
    for v in vals:
        m = re.search(r"\b(1\d{3}|20\d{2}|\d{3})\b", v or "")
        if m:
            return m.group(1)
    return ""


def card_data(db, rel):
    global FC_SCRIPT
    FC_SCRIPT = f'<script>window.FC_V = "{BUILD_ID}";</script><script src="{BASE}assets/flashcards.js?v={BUILD_ID}" defer></script>'
    path = lambda r: r["url"][len(BASE):]
    out = {k: {} for k in CARD_KINDS}

    def by_line(author_ids):
        return ", ".join(db["authors"][a]["title"] for a in author_ids)

    for t in db["terms"].values():
        short = cap_first(t["short"] or re.sub(r"\s+", " ", t["definition"])[:240])
        if not short:
            continue
        out["t"][t["id"]] = [t["title"], f'<p class="fc-def">{e(short)}</p>', path(t), short]

    tested_w = {w for w in db["works"] if rel[("works", w)].get("questions")}
    for a in db["authors"].values():
        works = [w for w in rel[("authors", a["id"])].get("works", []) if db["works"][w]["title"].strip().lower() != "no award"]
        if not works or a["title"].strip().lower() == "no award":
            continue
        works.sort(key=lambda w: (w not in tested_w, not db["works"][w]["notable"],
                                  year_of(db["works"][w]["year_written"], db["works"][w]["published"]) or "9999",
                                  sort_key(db["works"][w]["title"])))
        shown = works[:8]
        items = "".join(f"<li>{work_title_html(db['works'][w])}"
                        + (f' <span class="muted">{year_of(db["works"][w]["year_written"], db["works"][w]["published"])}</span>'
                           if year_of(db["works"][w]["year_written"], db["works"][w]["published"]) else "")
                        + "</li>" for w in shown)
        more = f'<p class="muted fc-more">and {len(works) - 8} more</p>' if len(works) > 8 else ""
        years = " – ".join(x for x in (a["birth"], a["death"]) if x)
        sub = " · ".join(x for x in (a["nationality"], years) if x)
        out["a"][a["id"]] = [a["title"], (f'<p class="fc-sub">{e(sub)}</p>' if sub else "") + f'<ul class="fc-list">{items}</ul>{more}', path(a)]

    for w in db["works"].values():
        authors = rel[("works", w["id"])].get("authors", [])
        if not authors or w["title"].strip().lower() == "no award":
            continue
        yr = year_of(w["year_written"], w["published"])
        sub = " · ".join(x for x in (yr, ", ".join(w["type"])) if x)
        out["w"][w["id"]] = [w["title"], f'<p class="fc-big">{e(by_line(authors))}</p>' + (f'<p class="fc-sub">{e(sub)}</p>' if sub else ""), path(w)]

    for p in db["prizes"].values():
        authors = rel[("prizes", p["id"])].get("authors", [])
        works = rel[("prizes", p["id"])].get("works", [])
        if is_no_award(db, p, authors, works) or not (authors or works):
            continue
        lines = []
        for w in works:
            wa = [a for a in rel[("works", w)].get("authors", [])]
            lines.append(f"{work_title_html(db['works'][w])}" + (f" <span class=\"muted\">by {e(by_line(wa))}</span>" if wa else ""))
        listed_authors = {a for w in works for a in rel[("works", w)].get("authors", [])}
        lines += [e(db["authors"][a]["title"]) for a in authors if a not in listed_authors]
        out["p"][p["id"]] = [p["title"], '<ul class="fc-list">' + "".join(f"<li>{x}</li>" for x in lines) + "</ul>", path(p)]

    (OUT / "assets" / "cards").mkdir(parents=True, exist_ok=True)
    for k, cards in out.items():
        CARD_IDS[k] = set(cards)
        (OUT / "assets" / "cards" / f"{k}.json").write_text(json.dumps(cards, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Flashcards: " + ", ".join(f"{len(v)} {CARD_KINDS[k]}" for k, v in out.items()), flush=True)


def deck_page(slug, title, lede, letters, ids=None, crumb=True, flip_label=None):
    """A study page. ids=None means every card of the given letters."""
    spec = {"title": title, "letters": letters, "ids": ids, "flip": flip_label}
    body = f"""{f'<p class="crumbs"><a href="{BASE}flashcards/">Flashcards</a></p>' if crumb else ''}
<h1>{e(title)}</h1>
<p class="lede">{e(lede)}</p>
<div class="fc" data-deck="{e(json.dumps(spec, ensure_ascii=False), quote=True)}">
  <noscript><p>Flashcards need JavaScript turned on.</p></noscript>
</div>"""
    write(f"flashcards/{slug}/index.html", page(title, body, "flashcards", lede, f"flashcards/{slug}/", extra_head=FC_SCRIPT))


def flashcard_pages(db, rel):
    n = {k: len(v) for k, v in CARD_IDS.items()}
    tiles = []      # (group, slug, title, count, blurb)

    def deck(group, slug, title, lede, letters, ids=None, blurb="", flip=None):
        count = len(ids) if ids is not None else sum(n[l] for l in letters)
        if not count:
            return
        deck_page(slug, title, lede, letters, ids, flip_label=flip)
        tiles.append((group, slug, title, count, blurb))

    term_flip = "Definition first"
    deck("Terms", "terms", "All terms", "Every term on the site: name the definition.", ["t"], blurb="Term → definition", flip=term_flip)
    tagged = []
    for g in db["tags"].values():
        ids = [f"t:{t}" for t in rel[("tags", g["id"])].get("terms", []) if t in CARD_IDS["t"]]
        ids.sort(key=lambda c: sort_key(db["terms"][c[2:]]["title"]))
        if ids:
            deck_page(f"tag-{g['slug']}", g["title"], f"{len(ids)} terms tagged {g['title']}.", ["t"], ids, flip_label=term_flip)
            tagged.append((g, len(ids)))

    tested_a = sorted((a for a in CARD_IDS["a"] if rel[("authors", a)].get("questions")), key=lambda a: author_sort(db["authors"][a]))
    tested_w = sorted((w for w in CARD_IDS["w"] if rel[("works", w)].get("questions")), key=lambda w: sort_key(db["works"][w]["title"]))
    deck("Authors and works", "authors-tested", "Authors on past tests", "Authors named in released UIL questions: name their works.",
         ["a"], [f"a:{a}" for a in tested_a], "Author → works")
    deck("Authors and works", "works-tested", "Works on past tests", "Works named in released UIL questions: who wrote them?",
         ["w"], [f"w:{w}" for w in tested_w], "Work → author")
    deck("Authors and works", "authors", "All authors", "Every author with works on the site: name their works.", ["a"], blurb="Author → works")
    deck("Authors and works", "works", "All works", "Every work on the site: who wrote it?", ["w"], blurb="Work → author")

    by_type = defaultdict(list)
    for p in CARD_IDS["p"]:
        by_type[db["prizes"][p]["type"] or "Other"].append(p)
    psort = lambda p: (-(int(db["prizes"][p]["year"]) if str(db["prizes"][p]["year"]).isdigit() else 0), sort_key(db["prizes"][p]["title"]))
    deck("Prizes", "prizes", "All prize winners", "Every prize on the site: who won?", ["p"], blurb="Prize → winner")
    for ptype, ids in sorted(by_type.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(ids) >= 5:
            deck("Prizes", f"prizes-{slugify(ptype)}", ptype, f"{ptype} winners: who won?", ["p"],
                 [f"p:{p}" for p in sorted(ids, key=psort)], "Prize → winner")

    # My decks and the review-everything page are filled in by flashcards.js.
    deck_page("my", "My deck", "A deck you made.", ["t", "a", "w", "p"], [], flip_label=term_flip)
    deck_page("review", "Everything due", "Every card you've studied that is due today, from all decks.", ["t", "a", "w", "p"], "due", flip_label=term_flip)

    def tile(slug, title, count, blurb):
        return (f'<a class="fc-tile" href="{BASE}flashcards/{slug}/" data-deck-link="{slug}">'
                f'<span class="fc-tile-t">{e(title)}</span>'
                f'<span class="fc-tile-m">{count:,} card{"s" if count != 1 else ""}{" · " + e(blurb) if blurb else ""}</span></a>')

    groups = ""
    for group in dict.fromkeys(g for g, *_ in tiles):
        items = "".join(tile(s, t, c, b) for g, s, t, c, b in tiles if g == group)
        if group == "Terms" and tagged:
            tag_items = "".join(f'<li><a href="{BASE}flashcards/tag-{g["slug"]}/">{e(g["title"])}</a> <span class="muted">{c}</span></li>'
                                for g, c in sorted(tagged, key=lambda x: sort_key(x[0]["title"])))
            items += f'</div><h3 class="fc-subhead">By tag</h3><ul class="plain cols fc-tags">{tag_items}</ul><div class="fc-tiles">'
        groups += section(group, f'<div class="fc-tiles">{items}</div>')
    body = f"""<h1>Flashcards</h1>
<p class="lede">Cards come back just before you'd forget them: grade each one and the ones you know show up less and less often.</p>
<div class="fc-home" data-fc-home>
  <a class="fc-due" href="{BASE}flashcards/review/" data-fc-due hidden></a>
  <section class="block"><h2>My decks</h2>
    <p class="muted" data-fc-mine-empty>Make your own deck, then add cards from any term, author, work or prize page with the <strong>Add to flashcards</strong> button.</p>
    <div class="fc-tiles" data-fc-mine></div>
    <p><button type="button" class="fc-btn" data-fc-new>New deck</button></p>
  </section>
</div>
{groups}
<p class="muted fc-sync" data-fc-sync></p>"""
    write("flashcards/index.html", page("Flashcards", body, "flashcards",
                                        "Spaced-repetition flashcards for literary terms, authors, works and prizes.",
                                        "flashcards/", extra_head=FC_SCRIPT))


# ---------------------------------------------------------------- index pages

def letter_bar(letters, current, key, split):
    out = []
    for L in letters:
        href = f"{BASE}{key}/browse/{L.lower() if L != '#' else 'other'}/" if split else f"#letter-{L}"
        cur = ' aria-current="page"' if L == current else ""
        out.append(f'<a href="{href}"{cur}>{L}</a>')
    return f'<nav class="letters" aria-label="Jump to letter">{"".join(out)}</nav>'


def list_item(db, key, r):
    if key == "terms":
        d = f' <span class="def">— {e(r["short"])}</span>' if r["short"] else ""
        return f'<li><a href="{r["url"]}">{e(r["title"])}</a>{d}</li>'
    if key == "authors":
        years = " – ".join(x for x in (r["birth"], r["death"]) if x)
        name = e(f'{r["last"]}, {r["first"]}') if r["last"] and r["first"] else e(r["title"])
        return f'<li><a href="{r["url"]}">{name}</a>{f" <span class=muted>{e(years)}</span>" if years else ""}</li>'
    if key == "poems":
        by = ", ".join(db["authors"][a]["title"] for a in r["authors"])
        return f'<li><a href="{r["url"]}">{e(r["title"])}</a>{f" <span class=muted>{e(by)}</span>" if by else ""}</li>'
    if key == "works":
        by = ", ".join(db["authors"][a]["title"] for a in r["authors"])
        return f'<li><a href="{r["url"]}">{work_title_html(r)}</a>{f" <span class=muted>{e(by)}</span>" if by else ""}</li>'
    return f'<li><a href="{r["url"]}">{e(r["title"])}</a></li>'


BROWSE_FIRST = {}


def alpha_index(db, key, label, intro):
    recs = [r for r in db[key].values() if r["title"].strip().lower() != "no award"]
    sorter = author_sort if key == "authors" else (lambda r: sort_key(r["title"]))
    recs.sort(key=sorter)
    groups = defaultdict(list)
    for r in recs:
        groups[letter_of(r["last"] if key == "authors" and r["last"] else r["title"])].append(r)
    letters = sorted(groups, key=lambda L: (L == "#", L))
    split = True
    head = (f'<h1>{label}: A–Z</h1><p class="lede">{len(recs):,} {label.lower()}. {intro} '
            f'<a href="{BASE}{key}/">Search and filter instead</a>.</p>')
    if not split:
        body = head + letter_bar(letters, None, key, False)
        for L in letters:
            body += f'<h2 class="letter" id="letter-{L}">{L}</h2><ul class="plain idx {key}">' \
                    + "".join(list_item(db, key, r) for r in groups[L]) + "</ul>"
        write(f"{key}/index.html", page(label, body, key, f"{label} in {SITE_TITLE}", f"{key}/"))
        return
    for i, L in enumerate(letters):
        body = head + letter_bar(letters, L, key, True)
        body += f'<h2 class="letter">{L}</h2><ul class="plain idx {key}">' \
                + "".join(list_item(db, key, r) for r in groups[L]) + "</ul>"
        slug = L.lower() if L != "#" else "other"
        html_ = page(f"{label}: {L}", body, key, f"{label} beginning with {L}", f"{key}/browse/{slug}/")
        write(f"{key}/browse/{slug}/index.html", html_)
        BROWSE_FIRST.setdefault(key, slug)


PRIZE_CONTROLS = """<form class="filters" data-prize-filters hidden onsubmit="return false">
  <label class="f-search"><span>Search</span><input type="search" name="q" placeholder="Winner or title"></label>
  <label><span>Contest</span><select name="tested"><option value="">All contests</option></select></label>
  <label data-nat-wrap><span>Nationality</span><select name="nat"><option value="">All nationalities</option></select></label>
  <label class="f-year"><span>From</span><input type="number" name="from" inputmode="numeric" placeholder="1901"></label>
  <label class="f-year"><span>To</span><input type="number" name="to" inputmode="numeric" placeholder="2026"></label>
  <label><span>Sort</span><select name="sort">
    <option value="new">Newest first</option><option value="old">Oldest first</option>
    <option value="author">Winner A–Z</option><option value="work" data-pulitzer-only>Title A–Z</option>
  </select></label>
  <label class="f-check"><input type="checkbox" name="hidenone"> Hide “No Award” years</label>
  <p class="f-status"><span data-shown></span> <button type="button" data-reset>Clear filters</button></p>
</form>"""

PULITZER_HEAD = '<li class="head" aria-hidden="true"><span>Year</span><span>Work</span><span>Author</span></li>'


def is_no_award(db, p, authors, works):
    if "no award" in p["title"].lower():
        return True
    names = [db["authors"][a]["title"] for a in authors] + [db["works"][w]["title"] for w in works]
    return bool(names) and all(n.strip().lower() == "no award" for n in names)


def prizes_index(db, rel):
    by_type = defaultdict(list)
    for p in db["prizes"].values():
        by_type[p["type"] or "Other"].append(p)
    types = sorted(by_type, key=lambda t: (-len(by_type[t]), t))
    tabs, panels = "", ""
    for i, t in enumerate(types):
        slug = slugify(t)
        nobel = "nobel" in t.lower()
        rows = []
        for p in sorted(by_type[t], key=lambda p: (-int(p["year"] or 0), p["title"])):
            authors = rel[("prizes", p["id"])].get("authors", [])
            works = rel[("prizes", p["id"])].get("works", [])
            yr = f'<span class="yr">{e(p["year"])}</span>'
            none = is_no_award(db, p, authors, works)
            nats = [] if none else list(dict.fromkeys(
                db["authors"][a]["nationality"] for a in authors if db["authors"][a]["nationality"]))
            who = ", ".join(db["authors"][a]["title"] for a in authors) if not none else ""
            what = ", ".join(db["works"][w]["title"] for w in works) if not none else ""
            data = {
                "year": p["year"] or "0",
                "author": "|".join(author_sort(db["authors"][a]) for a in authors) if not none else "",
                "work": "|".join(sort_key(db["works"][w]["title"]) for w in works) if not none else "",
                "nat": "|".join(nats),
                "tested": "|".join(p["tested"]),
                "text": fold(f"{who} {what} {' '.join(nats)}"),
            }
            attrs = " ".join(f'data-{k}="{e(v, quote=True)}"' for k, v in data.items())
            if none:
                rows.append(f'<li class="none" {attrs} data-none="1">{yr}<span class="noaward">No Award</span></li>')
                continue
            if nobel:
                label = " — ".join(x for x in (who, what) if x) or p["title"]
                nat = f'<span class="nat">{e(", ".join(nats))}</span>'
                rows.append(f'<li {attrs}>{yr}<a href="{p["url"]}">{e(label)}</a>{nat}</li>')
            else:
                work_cell = ", ".join(f'<a href="{db["works"][w]["url"]}">{work_title_html(db["works"][w])}</a>' for w in works) \
                    or f'<a href="{p["url"]}">{e(p["title"])}</a>'
                author_cell = ", ".join(f'<a href="{db["authors"][a]["url"]}">{e(db["authors"][a]["title"])}</a>' for a in authors)
                rows.append(f'<li {attrs}>{yr}<span class="pw">{work_cell}</span><span class="pa">{author_cell}</span></li>')
        cls = "plain years nobel" if nobel else "plain years pulitzer"
        tabs += (f'<a role="tab" href="#{slug}" id="tab-{slug}" aria-controls="{slug}"'
                 f'{" aria-selected=true" if i == 0 else ""}>{e(t)} <span class="count">{len(by_type[t])}</span></a>')
        panels += (f'<section class="tabpanel" id="{slug}" role="tabpanel" aria-labelledby="tab-{slug}">'
                   f'<h2 class="letter">{e(t)} <span class="count">{len(by_type[t])}</span></h2>'
                   f'<ul class="{cls}" data-kind="{"nobel" if nobel else "pulitzer"}">{"" if nobel else PULITZER_HEAD}{"".join(rows)}</ul>'
                   f'<p class="empty muted" hidden>No prizes match these filters.</p></section>')
    body = (f'<h1>Prizes</h1><p class="lede">{len(db["prizes"]):,} awards.</p>'
            f'<nav class="tabs" role="tablist" aria-label="Prize">{tabs}</nav>{PRIZE_CONTROLS}{panels}')
    write("prizes/index.html", page("Prizes", body, "prizes", "Literary prizes and their winners", "prizes/",
                                    extra_head=f'<script src="{BASE}assets/tabs.js?v={BUILD_ID}" defer></script>'
                                               f'<script src="{BASE}assets/prizes.js?v={BUILD_ID}" defer></script>'))



# ---------------------------------------------------------------- searchable section listings

def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def years_of(*vals):
    for v in vals:
        m = re.search(r"-?\d{3,4}", v or "")
        if m:
            return int(m.group(0))
    return None


def catalog_page(key, label, lede, rows, cfg, browse=False, extra="", script=""):
    """A section's listing page: rows are searched, filtered and sorted in the browser."""
    rows = [r for r in rows if r["n"].strip().lower() != "no award"]
    (OUT / "assets" / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "data" / f"{key}.json").write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    browse_link = (f' <a href="{BASE}{key}/browse/{BROWSE_FIRST[key]}/">Browse A–Z</a>' if browse and key in BROWSE_FIRST else "")
    # Without JavaScript (and for search engines), the first rows are listed as plain links.
    fallback = ""
    for r in rows[:300]:
        if r.get("u"):
            sub = f' <span class="muted">{e(r["s"])}</span>' if r.get("s") else ""
            fallback += f'<li><a href="{e(r["u"], quote=True)}">{e(r["n"])}</a>{sub}</li>'
    body = f"""<h1>{e(label)}</h1>
<p class="lede">{e(lede)}{browse_link}</p>
{extra}
<div data-catalog data-src="{BASE}assets/data/{key}.json?v={BUILD_ID}" data-config="{e(json.dumps(cfg, ensure_ascii=False), quote=True)}">
  <ul class="plain catalog" data-fallback>{fallback}</ul>
</div>"""
    write(f"{folder(key)}/index.html", page(label, body, key, lede, f"{folder(key)}/",
                                   extra_head=f'<script src="{BASE}assets/catalog.js?v={BUILD_ID}" defer></script>'
                                              + (f'<script src="{BASE}assets/{script}?v={BUILD_ID}" defer></script>' if script else "")))


def listed(db, key):
    """Records shown in listings: everything except "No Award" placeholders."""
    return [r for r in db[key].values() if r["title"].strip().lower() != "no award"]


def style_of(w):
    return "q" if work_title_html(w).startswith("“") else "i"


def catalog_terms(db, rel):
    rows = []
    for t in listed(db, "terms"):
        tid = t["id"]
        nq = len(rel[("terms", tid)].get("questions", []))
        nm = len(rel[("terms", tid)].get("rev:terms:mentioned", []))
        tags = sorted(db["tags"][g]["title"] for g in rel[("terms", tid)].get("tags", []))
        rows.append({
            "n": t["title"], "u": t["url"], "s": t["short"],
            "m": (lambda n: f"{n} test appearance{'s' if n != 1 else ''}" if n else "")(int(float(t["appearances"] or 0))),
            "f": {"tag": tags, "hasq": ["yes"] if nq else [], "hasauth": ["yes"] if rel[("terms", tid)].get("authors") else []},
            "k": {"name": sort_key(t["title"]), "q": nq, "app": int(float(t["appearances"] or 0))},
            "x": fold(f'{t["title"]} {t["short"]}'),
        })
    rows.sort(key=lambda r: r["k"]["name"])
    cfg = {"placeholder": "Term or short definition",
           "filters": [{"key": "tag", "label": "Set", "all": "All sets"}],
           "checks": [{"key": "hasq", "label": "On practice tests"}, {"key": "hasauth", "label": "Linked to authors"}],
           "sorts": [{"label": "A–Z", "key": "name"}, {"label": "Z–A", "key": "-name"},
                     {"label": "Most practice questions", "keys": ["-q", "name"]},
                     {"label": "Most appearances", "keys": ["-app", "name"]}]}
    catalog_page("terms", "Terms", f"{len(rows):,} literary terms, cross-linked.", rows, cfg, browse=True)


def catalog_authors(db, rel):
    rows = []
    for a in listed(db, "authors"):
        aid = a["id"]
        born = years_of(a["birth"])
        works = rel[("authors", aid)].get("works", [])
        nq = len(rel[("authors", aid)].get("questions", []))
        prizes = sorted({db["prizes"][p]["type"] for p in rel[("authors", aid)].get("prizes", []) if db["prizes"][p]["type"]})
        years = " – ".join(x for x in (a["birth"], a["death"]) if x)
        sub = " · ".join(x for x in (years, a["nationality"], ", ".join(a["medium"])) if x)
        century = ordinal((born - 1) // 100 + 1) + " century" if born and born > 0 else ""
        rows.append({
            "n": a["title"], "u": a["url"], "s": sub,
            "m": f"{len(works)} work{'s' if len(works) != 1 else ''}" if works else "",
            "f": {"nat": [a["nationality"]] if a["nationality"] else [], "medium": a["medium"],
                  "period": a["periods"], "prize": prizes, "century": [century] if century else [],
                  "hasq": ["yes"] if nq else [], "rl": ["yes"] if rel[("authors", aid)].get("reading-lists") else []},
            "k": {"name": author_sort(a), "born": born, "works": len(works), "q": nq,
                  "app": int(float(a["appearances"] or 0))},
            "x": fold(f'{a["title"]} {a["alternate"]}'),
        })
    rows.sort(key=lambda r: r["k"]["name"])
    cfg = {"placeholder": "Name",
           "filters": [{"key": "nat", "label": "Nationality", "all": "All nationalities"},
                       {"key": "medium", "label": "Known as", "all": "Any"},
                       {"key": "century", "label": "Born", "all": "Any century"},
                       {"key": "period", "label": "Period", "all": "Any period"},
                       {"key": "prize", "label": "Prize", "all": "Any or none"}],
           "range": {"key": "born", "label": "Born"},
           "checks": [{"key": "hasq", "label": "On practice tests"}, {"key": "rl", "label": "On a reading list"}],
           "sorts": [{"label": "Last name A–Z", "key": "name"}, {"label": "Born, earliest first", "keys": ["born", "name"]},
                     {"label": "Born, latest first", "keys": ["-born", "name"]},
                     {"label": "Most works", "keys": ["-works", "name"]},
                     {"label": "Most test appearances", "keys": ["-app", "name"]},
                     {"label": "Most practice questions", "keys": ["-q", "name"]}]}
    catalog_page("authors", "Authors", f"{len(rows):,} authors.", rows, cfg, browse=True)


def catalog_works(db, rel):
    rows = []
    for w in listed(db, "works"):
        wid = w["id"]
        authors = rel[("works", wid)].get("authors", [])
        year = years_of(w["year_written"], w["published"])
        lists = sorted(set(w["reading_list"]) | {db["reading-lists"][x]["title"] for x in rel[("works", wid)].get("reading-lists", [])})
        prizes = sorted({db["prizes"][p]["type"] for p in rel[("works", wid)].get("prizes", []) if db["prizes"][p]["type"]})
        by = ", ".join(db["authors"][a]["title"] for a in authors)
        rows.append({
            "n": w["title"], "u": w["url"], "i": style_of(w), "s": by,
            "m": str(year) if year is not None else "",
            "f": {"type": w["type"], "lang": w["language"], "rl": lists, "prize": prizes,
                  "notable": ["yes"] if w["notable"] else [],
                  "hasq": ["yes"] if rel[("works", wid)].get("questions") else []},
            "k": {"name": sort_key(w["title"]),
                  "author": author_sort(db["authors"][authors[0]]) if authors else "",
                  "year": year},
            "x": fold(f'{w["title"]} {by}'),
        })
    rows.sort(key=lambda r: r["k"]["name"])
    cfg = {"placeholder": "Title or author",
           "filters": [{"key": "type", "label": "Form", "all": "All forms", "order": "count"},
                       {"key": "lang", "label": "Language", "all": "All languages", "order": "count"},
                       {"key": "rl", "label": "Reading list", "all": "Any or none", "order": "desc"},
                       {"key": "prize", "label": "Prize", "all": "Any or none"}],
           "range": {"key": "year", "label": "Year"},
           "checks": [{"key": "notable", "label": "Notable only"}, {"key": "hasq", "label": "On practice tests"}],
           "sorts": [{"label": "Title A–Z", "key": "name"}, {"label": "Author A–Z", "keys": ["author", "year"]},
                     {"label": "Oldest first", "keys": ["year", "name"]}, {"label": "Newest first", "keys": ["-year", "name"]}]}
    catalog_page("works", "Works", f"{len(rows):,} works.", rows, cfg, browse=True)


def catalog_poems(db, rel):
    rows = []
    for p in listed(db, "poems"):
        pid = p["id"]
        authors = rel[("poems", pid)].get("authors", [])
        tests = sorted(rel[("poems", pid)].get("tests", []), key=lambda x: test_sort(db["tests"][x]))
        latest = db["tests"][tests[0]] if tests else None
        by = ", ".join(db["authors"][a]["title"] for a in authors)
        rows.append({
            "n": p["title"], "u": p["url"], "s": by,
            "m": latest["title"] + (f" +{len(tests) - 1}" if len(tests) > 1 else "") if latest else "",
            "f": {"contest": sorted({db["tests"][x]["type"] for x in tests if db["tests"][x]["type"]}),
                  "year": sorted({db["tests"][x]["year"] for x in tests if db["tests"][x]["year"]}),
                  "text": ["yes"] if p["text"] else [], "essay": ["yes"] if rel[("poems", pid)].get("essays") else []},
            "k": {"name": sort_key(p["title"]),
                  "author": author_sort(db["authors"][authors[0]]) if authors else "",
                  "latest": years_of(latest["year"], latest["title"]) if latest else None},
            "x": fold(f'{p["title"]} {by}'),
        })
    rows.sort(key=lambda r: r["k"]["name"])
    cfg = {"placeholder": "Title or author",
           "filters": [{"key": "contest", "label": "Contest", "all": "All contests"},
                       {"key": "year", "label": "Test year", "all": "All years", "order": "desc"}],
           "checks": [{"key": "text", "label": "Has full text"}, {"key": "essay", "label": "Has essay prompts"}],
           "sorts": [{"label": "Title A–Z", "key": "name"}, {"label": "Author A–Z", "keys": ["author", "name"]},
                     {"label": "Most recent test", "keys": ["-latest", "name"]}]}
    catalog_page("poems", "Poems and passages", f"{len(rows):,} poems and passages from the tests.", rows, cfg, browse=True)


def tests_index(db, rel):
    rows = []
    for t in db["tests"].values():
        nq = len(rel[("tests", t["id"])].get("questions", []))
        year = years_of(t["year"], t["title"])
        rows.append({"n": t["title"], "u": t["url"], "m": f"{nq} questions",
                     "f": {"contest": [t["type"]] if t["type"] else [], "year": [t["year"]] if t["year"] else []},
                     "k": {"year": year, "contest": t["type"], "name": sort_key(t["title"])},
                     "x": fold(t["title"])})
    rows.sort(key=lambda r: (-(r["k"]["year"] or 0), r["k"]["contest"]))
    cfg = {"placeholder": "Test name",
           "filters": [{"key": "contest", "label": "Contest", "all": "All contests"},
                       {"key": "year", "label": "Year", "all": "All years", "order": "desc"}],
           "range": {"key": "year", "label": "Year"},
           "sorts": [{"label": "Newest first", "keys": ["-year", "contest"]}, {"label": "Oldest first", "keys": ["year", "contest"]},
                     {"label": "Contest", "keys": ["contest", "-year"]}]}
    catalog_page("tests", "Tests", f"{len(rows)} released tests with {len(db['questions']):,} practice questions.", rows, cfg,
                 extra='<div class="my-progress" data-my-progress hidden></div>', script="test-scores.js")



def essay_test(db, x):
    """The test an essay prompt belongs to (prompts are named after their test)."""
    want = fold(x["title"]).replace(" essay", "").strip()
    for t in db["tests"].values():
        if fold(t["title"]) == want:
            return t
    return None


def essay_page(db, rel, x):
    test = essay_test(db, x)
    poems = [p for p in x["poems"] if p in db["poems"]]
    body = f"""{crumbs('essays', 'Essay prompts')}
<article class="record">
<p class="daily-label">Essay prompt</p>
<h1 data-record="{x['id']}">{e(x['title'])}</h1>
{facts([('Test', f'<a href="{test["url"]}">{e(test["title"])}</a>' if test else ''),
        ('Text', ', '.join(f'<a href="{db["poems"][p]["url"]}">{e(db["poems"][p]["title"])}</a>' for p in poems))])}
<blockquote class="essay-prompt">{multiline(x['prompt'])}</blockquote>
</article>
"""
    for pid in poems:
        body += passage_html(db, rel, pid, True)
    desc = (x["prompt"] or x["title"])[:250]
    write(f"essays/{x['slug']}/index.html", page(f"{x['title']} essay prompt", body, "essays", desc, f"essays/{x['slug']}/"))


def essays_index(db, rel):
    rows = []
    for x in db["essays"].values():
        test = essay_test(db, x)
        poems = [p for p in x["poems"] if p in db["poems"]]
        authors = [a for p in poems for a in rel[("poems", p)].get("authors", [])]
        what = ", ".join(db["poems"][p]["title"] for p in poems)
        by = ", ".join(db["authors"][a]["title"] for a in dict.fromkeys(authors))
        year = years_of(test["year"] if test else "", x["title"])
        contest = (test["type"] if test else re.sub(r"^\d{4}\s*", "", x["title"])).strip()
        prompt = re.sub(r"\s+", " ", x["prompt"]).strip()
        rows.append({"n": x["title"], "u": x["url"], "s": " — ".join(v for v in (what, by) if v),
                     "m": "", "f": {"contest": [contest] if contest else [], "year": [str(year)] if year else []},
                     "k": {"year": year, "contest": contest, "name": sort_key(x["title"])},
                     "x": fold(f"{x['title']} {what} {by} {prompt}")})
    rows.sort(key=lambda r: (-(r["k"]["year"] or 0), r["k"]["contest"]))
    cfg = {"placeholder": "Test, poem, poet or words in the prompt",
           "filters": [{"key": "contest", "label": "Contest", "all": "All contests"},
                       {"key": "year", "label": "Year", "all": "All years", "order": "desc"}],
           "range": {"key": "year", "label": "Year"},
           "sorts": [{"label": "Newest first", "keys": ["-year", "contest"]}, {"label": "Oldest first", "keys": ["year", "contest"]},
                     {"label": "Contest", "keys": ["contest", "-year"]}]}
    catalog_page("essays", "Essay prompts", f"{len(rows)} essay prompts from the released tests, each with its text.", rows, cfg)


def reading_lists_index(db):
    rows = []
    for rl in db["reading-lists"].values():
        def group(label, key, ids):
            return [label, [[db[key][i]["title"], db[key][i]["url"], style_of(db[key][i]) if key == "works" else ""] for i in ids]]
        names = [db["works"][i]["title"] for i in rl["novel"] + rl["play"]] + [db["authors"][i]["title"] for i in rl["poet"]]
        rows.append({"n": rl["title"], "id": rl["slug"],
                     "l": [group("Novel", "works", rl["novel"]), group("Play", "works", rl["play"]), group("Poet", "authors", rl["poet"])],
                     "k": {"year": rl["title"]}, "x": fold(rl["title"] + " " + " ".join(names))})
    rows.sort(key=lambda r: r["k"]["year"], reverse=True)
    cfg = {"placeholder": "Year, title or poet", "layout": "rl-list",
           "sorts": [{"label": "Newest first", "key": "-year"}, {"label": "Oldest first", "key": "year"}]}
    catalog_page("reading-lists", "Reading lists", "The novel, play and poet for each school year.", rows, cfg)


def periods_index(db):
    """Periods page: a vertical timeline per region (American, British), major periods on the line
    with their sub-periods indented beneath; pills show one region or both side by side."""
    periods = db["periods"]

    def yr(v):
        y = years_of(v)
        return y if y is not None else 99999

    def years(p):
        a, b = p["start"], p["end"]
        return f"{a}–{b}" if a and b else f"{a}–present" if a else b

    def blurb(p):
        d = re.sub(r"\s+", " ", p["description"] or "").strip()
        m = re.match(r"(.{40,180}?[.!?])(\s|$)", d)
        return m.group(1) if m else (d[:160].rsplit(" ", 1)[0].rstrip(",;:—– ") + "…" if len(d) > 160 else d)

    def sub_html(c):
        return (f'<li class="tl-sub"><a href="{c["url"]}"><span class="tl-name">{e(c["title"])}</span>'
                f'<span class="tl-years">{e(years(c))}</span></a></li>')

    # Historical events, by the timeline they belong on. World events go on the British timeline, and on the
    # American one too when their "Involves America" box is checked.
    EVENT_REGION = {"united states": "American", "britain": "British"}

    def ev_num(v):
        v = (v or "").strip()
        return int(float(v)) if re.fullmatch(r"-?\d+(\.0+)?", v) else years_of(v)

    def event_year(y):
        n = ev_num(y)
        return None if n is None else (f"{-n} BCE" if n < 0 else str(n))

    def checked(v):
        return (v or "").strip().lower() in ("true", "1", "checked")

    def event_html(ev):
        a, b = event_year(ev["start"]), event_year(ev["end"])
        when = f"{a}–{b}" if a and b and b != a else a
        if checked(ev["approximate"]) and when:
            when = "c. " + when
        world = fold(ev["region"]) == "world"
        tip = f' title="{e(ev["description"], quote=True)}"' if ev["description"] else ""
        return (f'<li class="tl-event{" tl-world" if world else ""}"{tip}><span class="tl-ev-years">{e(when or "")}</span>'
                f'<span class="tl-ev-name">{e(ev["title"])}</span>'
                f'{"<span class=tl-ev-tag>World</span>" if world else ""}</li>')

    def events_for(region, majors):
        """{major id: [event html]} for one timeline; events before its first period are left out."""
        starts = [(yr(m["start"]), m) for m in majors if yr(m["start"]) != 99999]
        if not starts:
            return {}
        out = {m["id"]: [] for m in majors}
        major_ids = set(out)
        for ev in sorted(db.get("events", {}).values(), key=lambda v: (ev_num(v["start"]) if ev_num(v["start"]) is not None else 99999, sort_key(v["title"]))):
            y = ev_num(ev["start"])
            reg = fold(ev["region"])
            world_here = reg == "world" and (region != "American" or checked(ev["us"]))
            if y is None or not (EVENT_REGION.get(reg) == region or world_here):
                continue
            if y < starts[0][0]:
                continue  # before this timeline's periods begin
            linked = [p for p in ev["periods"] if p in major_ids]
            if linked and reg != "world":
                home = linked[0]
            else:
                home = [m for s0, m in starts if s0 <= y][-1]["id"]
            out[home].append(event_html(ev))
        return out

    def major_html(p, subs, evs):
        b = blurb(p)
        kids = (f'<ol class="tl-subs">{"".join(sub_html(c) for c in subs)}</ol>' if subs else "")
        events = f'<ol class="tl-events" aria-label="Historical events">{"".join(evs)}</ol>' if evs else '<div class="tl-events"></div>'
        return (f'<li class="tl-major">{events}<div class="tl-body"><a class="tl-head" href="{p["url"]}"><span class="tl-years">{e(years(p))}</span>'
                f'<span class="tl-name">{e(p["title"])}</span></a>'
                f'{f"<p class=tl-blurb>{e(b)}</p>" if b else ""}{kids}</div></li>')

    cols, placed = [], []
    regions = sorted({p["region"] for p in periods.values() if p["region"]}, key=lambda r: (r != "American", r))
    for ci, region in enumerate(regions):
        mine = [p for p in periods.values() if p["region"] == region]
        ids = {p["id"] for p in mine}
        majors = [p for p in mine if not (set(p["parent"]) & ids) or fold(p["type"] or "") == "period"]
        major_ids = {p["id"] for p in majors}
        majors.sort(key=lambda p: (yr(p["start"]), sort_key(p["title"])))
        evmap = events_for(region, majors)
        items = []
        for m in majors:
            subs = [periods[c] for c in mine_ids_children(m, mine, major_ids)]
            subs.sort(key=lambda c: (yr(c["start"]), sort_key(c["title"])))
            html_ = major_html(m, subs, evmap.get(m["id"], []))
            items.append(html_)
            placed.append((ci, yr(m["start"]), html_))
        key = slugify(region)
        cols.append(f'<section class="tl-col" data-region="{key}"><h2>{e(region)} literature</h2>'
                    f'<ol class="timeline">{"".join(items)}</ol></section>')

    # "Both": one grid whose rows are the years where any major period starts, so the two
    # timelines line up by year (a period spans the rows until the next period in its column).
    bounds = sorted({y for _, y, _ in placed})
    row_of = {y: i + 2 for i, y in enumerate(bounds)}
    last_row = len(bounds) + 2
    cells = [f'<h2 class="tl-grid-head" style="grid-column:{ci + 1};grid-row:1">{e(r)} literature</h2>'
             for ci, r in enumerate(regions)]
    for ci in range(len(regions)):
        mine = sorted([x for x in placed if x[0] == ci], key=lambda x: x[1])
        for k, (_, y, html_) in enumerate(mine):
            end = row_of[mine[k + 1][1]] if k + 1 < len(mine) else last_row
            first = " tl-first" if k == 0 else ""
            cells.append(f'<div class="tl-cell{first}" style="grid-column:{ci + 1};grid-row:{row_of[y]} / {end}">'
                         f'<ol class="timeline">{html_}</ol></div>')
        if mine and row_of[mine[0][1]] > 2:
            cells.append(f'<p class="tl-before" style="grid-column:{ci + 1};grid-row:2 / {row_of[mine[0][1]]}">'
                         f'{e(regions[ci])} literature begins in {mine[0][1]}.</p>')
    grid = f'<div class="tl-grid" style="grid-template-columns:repeat({len(regions)}, 1fr)">{"".join(cells)}</div>'
    pills = "".join(f'<button type="button" class="res-pill" data-region-pick="{slugify(r)}" aria-pressed="false">{e(r)}</button>'
                    for r in regions)
    pills += '<button type="button" class="res-pill" data-region-pick="both" aria-pressed="true">Both</button>'
    n_events = len(db.get("events", {}))
    toggle = ('<label class="res-free-toggle tl-ev-toggle"><input type="checkbox" data-events-toggle> Show historical events</label>'
              if n_events else "")
    body = f"""<h1>Periods</h1>
<p class="lede">The periods of American and British literature, in order. Major periods sit on the line; their sub-periods are listed beneath them.</p>
<div class="tl-controls"><div class="res-pills tl-pills" role="group" aria-label="Show a region">{pills}</div>{toggle}</div>
<div class="tl-wrap" data-showing="both">{grid}<div class="tl-cols">{"".join(cols)}</div></div>
<script>
(function () {{
  var wrap = document.querySelector(".tl-wrap");
  function show(r) {{
    if (!document.querySelector('[data-region-pick="' + r + '"]')) r = "both";
    wrap.setAttribute("data-showing", r);
    wrap.querySelectorAll("[data-region]").forEach(function (c) {{ c.hidden = r !== "both" && c.getAttribute("data-region") !== r; }});
    document.querySelectorAll("[data-region-pick]").forEach(function (b) {{ b.setAttribute("aria-pressed", String(b.getAttribute("data-region-pick") === r)); }});
  }}
  show(new URLSearchParams(location.search).get("region") || "both");
  var tog = document.querySelector("[data-events-toggle]");
  function events(on) {{
    if (on) wrap.setAttribute("data-events", ""); else wrap.removeAttribute("data-events");
    if (tog) tog.checked = on;
  }}
  events(new URLSearchParams(location.search).get("events") === "1");
  if (tog) tog.addEventListener("change", function () {{
    events(tog.checked);
    var u = new URL(location.href);
    if (tog.checked) u.searchParams.set("events", "1"); else u.searchParams.delete("events");
    history.replaceState(null, "", u);
  }});
  document.addEventListener("click", function (ev) {{
    var b = ev.target.closest("[data-region-pick]");
    if (!b) return;
    var r = b.getAttribute("data-region-pick"); show(r);
    var u = new URL(location.href);
    if (r === "both") u.searchParams.delete("region"); else u.searchParams.set("region", r);
    history.replaceState(null, "", u);
  }});
}})();
</script>"""
    write("periods/index.html", page("Periods", body, "periods", "The periods of American and British literature as a timeline.", "periods/"))


def mine_ids_children(major, mine, major_ids):
    """Sub-periods of a major period: those linked as its Sub Periods or naming it as their parent."""
    ids = {p["id"] for p in mine}
    kids = [c for c in major["subs"] if c in ids and c not in major_ids]
    kids += [p["id"] for p in mine if major["id"] in p["parent"] and p["id"] not in major_ids and p["id"] not in kids]
    return kids


def tags_index(db, rel):
    rows = []
    for g in db["tags"].values():
        n = len(rel[("tags", g["id"])].get("terms", []))
        sets = [name for name, url in (("Quizlet", g["quizlet"]), ("Gimkit", g["gimkit"]),
                                       ("Blooket", g["blooket"]), ("Sporcle", g["sporcle"])) if url]
        rows.append({"n": g["title"], "u": g["url"], "s": " · ".join(sets), "m": f"{n} terms",
                     "f": {"set": sets}, "k": {"name": sort_key(g["title"]), "n": n}, "x": fold(g["title"])})
    rows.sort(key=lambda r: r["k"]["name"])
    cfg = {"placeholder": "Set name",
           "filters": [{"key": "set", "label": "Study set", "all": "Any or none"}],
           "sorts": [{"label": "A–Z", "key": "name"}, {"label": "Most terms", "keys": ["-n", "name"]},
                     {"label": "Fewest terms", "keys": ["n", "name"]}]}
    catalog_page("tags", "Sets", "Terms grouped by topic, with links to Quizlet and other study sets.", rows, cfg)


def resources_index(db, resolver):
    """Resources page: pick a reading list, then see its resources grouped by novel (or short stories),
    play and poetry. A resource belongs to a list by its School Year, and to a group by its Work
    (matched against the list's novel, play and poet), with Poetry Guides falling back to poetry."""
    lists = sorted(db["reading-lists"].values(), key=lambda rl: rl["title"], reverse=True)

    def names_match(a, b):
        a, b = fold(a), fold(b)
        if not a or not b:
            return False
        return a == b or a in b or b in a or a.split()[-1] == b.split()[-1]

    def slot_of(r, rl):
        works = r["work"] or []
        for key, ids, table in (("novel", rl["novel"], "works"), ("play", rl["play"], "works"), ("poet", rl["poet"], "authors")):
            for i in ids:
                if any(names_match(w, db[table][i]["title"]) for w in works):
                    return key
        if fold(r["type"] or "").startswith("poetry"):
            return "poet"
        return "general"

    ACCESS_CLASS = {"free": "free", "free preview": "preview", "paid": "paid"}

    def item(r, label=None):
        link = r["link"] if re.match(r"^https?://", r["link"] or "") else ""
        text = e(label or r["title"])
        name = (f'<a class="ext" href="{e(link, quote=True)}" target="_blank" rel="noopener">{text} \u2197</a>'
                if link else text)
        kind = f'<span class="chip res-type">{e(r["type"])}</span>' if r["type"] else ""
        acc = (r.get("access") or "").strip()
        badge = (f'<span class="res-access res-{ACCESS_CLASS.get(fold(acc), "free")}">{e(acc)}</span>' if acc else "")
        return (f'<li class="res-item" data-access="{ACCESS_CLASS.get(fold(acc), "free") if acc else "free"}">'
                f'<span class="res-name">{name}</span><span class="res-tags">{badge}{kind}</span></li>')

    PART = re.compile(r"\s*\((part \d+)\)\s*$", re.I)

    def by_work(rs, general_words):
        """Split "Young Goodman Brown - Lit Charts" into the story or poem and the rest, so a group
        lists each story or poem under its own heading. Collections, purchases and anything naming
        the author go under "Collections and general"."""
        items = []
        for r in rs:
            title = r["title"] or ""
            if " - " in title:
                key, rest = title.split(" - ", 1)
            else:
                key, rest = "", title
            m = PART.search(key)
            if m:
                key, rest = key[:m.start()].strip(), f"{rest} ({m.group(1)})"
            k = fold(key)
            if (not key or fold(r["type"] or "") == "purchase" or any(w in k for w in general_words)
                    or re.search(r"audiobook|full text", fold(rest))):
                key, rest = "", title
            items.append([key, rest, r])
        # "In Reference to her Children, 23 June 1659" and "In Reference to her Children" are one poem.
        keys = sorted({x[0] for x in items if x[0]}, key=len)
        canon = {}
        for k in keys:
            short = next((c for c in canon.values() if fold(k).startswith(fold(c)) and
                          fold(k)[len(fold(c)):len(fold(c)) + 1] in (",", " ", "(", ":", ";")), None)
            canon[k] = short or k
        groups = defaultdict(list)
        for key, rest, r in items:
            groups[canon.get(key, "")].append((rest, r))
        out = []
        for key in sorted(groups, key=lambda k: (k != "", sort_key(k))):
            rows = sorted(groups[key], key=lambda x: (sort_key(x[1]["type"] or "~"), sort_key(x[0])))
            out.append((key or "Collections and general", rows))
        return out

    sections, options, default = [], [], None
    for rl in lists:
        mine = [r for r in db["resources"].values() if (r["year"] or "") == rl["year"]]
        groups = {"novel": [], "play": [], "poet": [], "general": []}
        for r in mine:
            groups[slot_of(r, rl)].append(r)
        novel_titles = [db["works"][i]["title"] for i in rl["novel"]]
        novel_label = "Short stories" if any("short stor" in fold(t) for t in novel_titles) else "Novel"
        heads = {
            "novel": (novel_label, ", ".join(f'<a href="{db["works"][i]["url"]}">{work_title_html(db["works"][i])}</a>' for i in rl["novel"])),
            "play": ("Play", ", ".join(f'<a href="{db["works"][i]["url"]}">{work_title_html(db["works"][i])}</a>' for i in rl["play"])),
            "poet": ("Poetry", ", ".join(f'<a href="{db["authors"][i]["url"]}">{e(db["authors"][i]["title"])}</a>' for i in rl["poet"])),
            "general": ("General", ""),
        }
        general_words = {fold(db["authors"][i]["title"]).split()[-1] for i in rl["poet"]}
        general_words |= {re.sub(r"[’']s$", "", w) for t in novel_titles for w in fold(t).split()
                          if len(w) > 5 and w not in ("short", "stories")}
        blocks = []
        pills = ['<button type="button" class="res-pill" data-sec-pick="all" aria-pressed="true">All</button>']
        for key in ("novel", "play", "poet", "general"):
            rs = groups[key]
            if key == "general" and not rs:
                continue
            label, what = heads[key]
            many = key == "poet" or (key == "novel" and novel_label == "Short stories")
            if not rs:
                body = '<p class="muted res-none">No resources yet.</p>'
            elif many:
                body = "".join(
                    f'<h3 class="res-sub">{e(sub)}</h3><ul class="res-list">'
                    f'{"".join(item(r, rest if sub != "Collections and general" else None) for rest, r in rows)}</ul>'
                    for sub, rows in by_work(rs, general_words))
            else:
                rs = sorted(rs, key=lambda r: (sort_key(r["type"] or "~"), sort_key(r["title"])))
                body = f'<ul class="res-list">{"".join(item(r) for r in rs)}</ul>'
            blocks.append(f'<section class="res-group" data-sec="{key}"><h2>{label}{": " + what if what else ""}'
                          f' <span class="count">{len(rs)}</span></h2>{body}</section>')
            pills.append(f'<button type="button" class="res-pill" data-sec-pick="{key}" aria-pressed="false">'
                         f'{label} <span class="count">{len(rs)}</span></button>')
        n = len(mine)
        if default is None and n:
            default = rl["slug"]
        note = "" if n else '<p class="lede res-empty">No resources have been added for this reading list yet.</p>'
        pill_bar = f'<div class="res-pills" role="group" aria-label="Show a section">{"".join(pills)}</div>' if n else ""
        sections.append(f'<div class="res-list-panel" data-rl="{rl["slug"]}" hidden>{note}{pill_bar}{"".join(blocks)}</div>')
        options.append(f'<option value="{rl["slug"]}">{e(rl["title"])} · '
                       f'{n} resource{"" if n == 1 else "s"}</option>')
    default = default or (lists[0]["slug"] if lists else "")
    body = f"""<h1>Reading resources</h1>
<p class="lede">Texts, audio and study materials for each year's reading list.</p>
<p class="res-key"><span class="res-access res-free">Free</span> free to use · <span class="res-access res-preview">Free preview</span> part of it is free; the rest needs a subscription · <span class="res-access res-paid">Paid</span> costs money</p>
<div class="res-controls"><label class="res-pick"><span>Reading list</span>
<select data-rl-pick>{"".join(options)}</select></label>
<label class="res-free-toggle"><input type="checkbox" data-free-only> Free resources only</label></div>
{"".join(sections)}
<script>
(function () {{
  var pick = document.querySelector("[data-rl-pick]"), panels = document.querySelectorAll("[data-rl]");
  function show(slug) {{
    var found = false;
    panels.forEach(function (p) {{ var on = p.getAttribute("data-rl") === slug; p.hidden = !on; found = found || on; }});
    if (!found && panels.length) {{ slug = {json.dumps(default)}; return show(slug); }}
    pick.value = slug;
  }}
  var sec = new URLSearchParams(location.search).get("section") || "all";
  var freeBox = document.querySelector("[data-free-only]");
  freeBox.checked = new URLSearchParams(location.search).get("free") === "1";
  function applyFree() {{
    var only = freeBox.checked;
    document.querySelectorAll(".res-item").forEach(function (li) {{ li.hidden = only && li.getAttribute("data-access") !== "free"; }});
    document.querySelectorAll(".res-list").forEach(function (ul) {{
      var any = ul.querySelector(".res-item:not([hidden])");
      ul.hidden = !any;
      var h = ul.previousElementSibling;
      if (h && h.classList.contains("res-sub")) h.hidden = !any;
    }});
    document.querySelectorAll(".res-group").forEach(function (g) {{
      var shown = g.querySelectorAll(".res-item:not([hidden])").length, total = g.querySelectorAll(".res-item").length;
      var c = g.querySelector("h2 .count"); if (c) c.textContent = shown;
      var none = g.querySelector(".res-none-free");
      if (total && !shown) {{
        if (!none) {{ none = document.createElement("p"); none.className = "muted res-none res-none-free"; none.textContent = "No free resources here."; g.appendChild(none); }}
        none.hidden = false;
      }} else if (none) none.hidden = true;
    }});
    document.querySelectorAll("[data-sec-pick]").forEach(function (b) {{
      var name = b.getAttribute("data-sec-pick"), c = b.querySelector(".count");
      if (!c) return;
      var g = b.closest(".res-list-panel").querySelector('[data-sec="' + name + '"]');
      c.textContent = g ? g.querySelectorAll(".res-item:not([hidden])").length : 0;
    }});
  }}
  function showSection(name) {{
    panels.forEach(function (p) {{
      var has = name === "all" || p.querySelector('[data-sec="' + name + '"]');
      var want = has ? name : "all";
      p.querySelectorAll("[data-sec]").forEach(function (g) {{ g.hidden = want !== "all" && g.getAttribute("data-sec") !== want; }});
      p.querySelectorAll("[data-sec-pick]").forEach(function (b) {{ b.setAttribute("aria-pressed", String(b.getAttribute("data-sec-pick") === want)); }});
    }});
    sec = name;
  }}
  function remember() {{
    var u = new URL(location.href); u.searchParams.set("list", pick.value);
    if (sec === "all") u.searchParams.delete("section"); else u.searchParams.set("section", sec);
    if (freeBox.checked) u.searchParams.set("free", "1"); else u.searchParams.delete("free");
    history.replaceState(null, "", u);
  }}
  var q = new URLSearchParams(location.search).get("list");
  show(q || {json.dumps(default)});
  showSection(sec);
  applyFree();
  freeBox.addEventListener("change", function () {{ applyFree(); remember(); }});
  pick.addEventListener("change", function () {{ show(pick.value); showSection(sec); remember(); }});
  document.addEventListener("click", function (ev) {{
    var b = ev.target.closest("[data-sec-pick]");
    if (!b) return;
    showSection(b.getAttribute("data-sec-pick")); remember();
  }});
}})();
</script>
<noscript><style>.res-list-panel[hidden] {{ display: block; }}</style></noscript>"""
    write("resources/index.html", page("Reading resources", body, "resources",
                                       "Texts, audio and study materials for each year's reading list.", "resources/"))


EXAMPLE_ORDER = {"Title": 0, "Line": 1, "Phrase": 2, "Word": 3, "Poem": 4, "Excerpt": 5}


def term_examples(db, rel, tid):
    """A term's examples, shortest kinds first (titles, lines, phrases, words, then poems and excerpts)."""
    ids = rel[("terms", tid)].get("rev:examples:terms", [])
    exs = [db["examples"][x] for x in ids if db["examples"][x]["name"].strip()]
    return sorted(exs, key=lambda x: (EXAMPLE_ORDER.get(x["type"], 3), len(x["name"])))


def example_html(db, x):
    text = x["name"].strip()
    kind = x["type"]
    if kind in ("Excerpt", "Poem") or "\n" in text:
        body = f'<span class="ex-block">{multiline(text)}</span>'
    elif kind == "Title":
        body = f'<cite class="ex-title">{e(text)}</cite>'
    elif kind == "Word":
        body = f'<i class="ex-word">{e(text)}</i>'
    else:
        body = f'<span class="ex-quote">“{e(text.strip(QUOTES))}”</span>'
    who = []
    for a in x["authors"]:
        who.append(f'<a href="{db["authors"][a]["url"]}">{e(db["authors"][a]["title"])}</a>')
    if x["source"] and x["source"].strip() != text:
        who.append(f'<i>{e(x["source"].strip())}</i>')
    by = f' <span class="ex-by">{"by " if kind == "Title" and x["authors"] else "— "}{", ".join(who)}</span>' if who else ""
    return f'<li class="ex ex-{slugify(kind or "other")}">{body}{by}</li>'


def examples_list(db, exs, limit=None):
    shown = exs[:limit] if limit else exs
    return f'<ul class="plain examples">{"".join(example_html(db, x) for x in shown)}</ul>' if shown else ""


def daily_term_html(db, rel, resolver, tm):
    short = tm["short"]
    if not short:  # no Short Definition: fall back to the definition's first paragraph
        paras = [x for x in (tm["definition"] or "").strip().split("\n\n") if x.strip()]
        short = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", paras[0])).strip() if paras else ""
    exs = term_examples(db, rel, tm["id"])
    # Up to four examples, with at most one long excerpt.
    picked, long_ = [], 0
    for x in exs:
        is_long = x["type"] in ("Excerpt", "Poem") or "\n" in x["name"].strip()
        if is_long and long_:
            continue
        long_ += is_long
        picked.append(x)
        if len(picked) == 4:
            break
    more = len(exs) - len(picked)
    ex_html = ""
    if picked:
        more_link = f' <a class="ex-more" href="{tm["url"]}#examples">{more} more</a>' if more > 0 else ""
        ex_html = (f'<h3 class="daily-sub">Example{"s" if len(exs) != 1 else ""}{more_link}</h3>'
                   + examples_list(db, picked))
    return f"""<article class="daily-card">
  <p class="daily-label">Term of the day</p>
  <h2 class="daily-title"><a href="{tm['url']}">{e(tm['title'])}</a></h2>
  {f'<p class="daily-short">{e(cap_first(short))}</p>' if short else ''}
  {ex_html}
  <div class="daily-links"><a href="{tm['url']}">Read the full entry</a>{add_card_slot('t', tm)}</div>
</article>"""


def daily_author_html(db, rel, a):
    img = a.get("image") or (a["picture_url"] if re.match(r"^https?://", a["picture_url"]) else None)
    portrait = (f'<img class="portrait" src="{e(img, quote=True)}" alt="Portrait of {e(a["title"], quote=True)}" '
                f'loading="lazy" onerror="this.remove()">') if img else ""
    years = "–".join(x for x in (a["birth"], a["death"]) if x)
    about = " ".join(x for x in (a["nationality"], (a["medium"][0].lower() if a["medium"] else "")) if x)
    line = ", ".join(x for x in (cap_first(about), years) if x)
    if rel[("authors", a["id"])].get("reading-lists"):
        rl = current_list(db)
        if rl and rl["id"] in rel[("authors", a["id"])]["reading-lists"]:
            line += " · on this year’s reading list"
    works = list(rel[("authors", a["id"])].get("works", []))
    works.sort(key=lambda w: (not db["works"][w]["notable"], db["works"][w]["year_written"] or db["works"][w]["published"] or "9999",
                              sort_key(db["works"][w]["title"])))
    def wli(w):
        r = db["works"][w]
        year = year_of(r["year_written"], r["published"])
        return (f'<li><a href="{r["url"]}">{work_title_html(r)}</a>'
                f'{f"<span class=muted>{e(year)}</span>" if year else ""}</li>')
    shown = "".join(wli(w) for w in works[:6])
    nq = len(rel[("authors", a["id"])].get("questions", []))
    quiz = f'<a href="{BASE}study/quiz/?author={a["id"]}">Quiz on {e(a["last"] or a["title"])}</a>' if nq else ""
    return f"""<article class="daily-card daily-author">
  <p class="daily-label">Author of the day</p>
  <div class="daily-author-body">
    {portrait}
    <div>
      <h2 class="daily-title"><a href="{a['url']}">{e(a['title'])}</a></h2>
      {f'<p class="daily-about">{e(line)}</p>' if line else ''}
    </div>
  </div>
  {f'<h3 class="daily-sub">Notable works</h3><ul class="plain daily-works">{shown}</ul>' if shown else ''}
  <div class="daily-links"><a href="{a['url']}">Full author page</a>{quiz}{add_card_slot('a', a)}</div>
</article>"""


def daily_section(db, rel, resolver):
    """Term and author of the day. The page carries a few days' picks, so it switches at the
    visitor's local midnight; the record marked Today = 1 is the one shown without JavaScript."""
    def by_date(key):
        out = {}
        for r in db[key].values():
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("date", "")):
                out.setdefault(r["date"], r)
        return out
    terms, authors = by_date("terms"), by_date("authors")
    today_term = next((r for r in db["terms"].values() if r.get("today") == "1"), None)
    today_author = next((r for r in db["authors"].values() if r.get("today") == "1"), None)
    if not today_term and not today_author:
        return ""
    build_day = (today_term or today_author)["date"]
    try:
        center = datetime.date.fromisoformat(build_day)
    except ValueError:
        center = datetime.date.today()
    days = [(center + datetime.timedelta(days=d)).isoformat() for d in range(-1, 3)]
    blocks = ""
    for d in days:
        tm = today_term if d == build_day else terms.get(d)
        au = today_author if d == build_day else authors.get(d)
        if not tm and not au:
            continue
        cards = (daily_term_html(db, rel, resolver, tm) if tm else "") + (daily_author_html(db, rel, au) if au else "")
        hidden = "" if d == build_day else " hidden"
        blocks += f'<div class="daily" data-date="{d}"{hidden}>{cards}</div>'
    script = """<script>
(function () {
  var n = new Date(), p = function (x) { return (x < 10 ? "0" : "") + x; };
  var d = n.getFullYear() + "-" + p(n.getMonth() + 1) + "-" + p(n.getDate());
  var match = document.querySelector('.daily[data-date="' + d + '"]');
  if (!match) return;
  document.querySelectorAll(".daily").forEach(function (b) { b.hidden = b !== match; });
})();
</script>"""
    return f'<section class="today">{blocks}</section>{script}'


# ---------------------------------------------------------------- modes: menu, Reference and Study pages

# Pages that belong to Study in the menu; every other section belongs to Reference.
STUDY_KEYS = {"tests", "essays", "flashcards", "resources", "study"}
RESOLVER = None
NAV_MENUS = {}          # filled by build_nav_menus once the data is loaded

# Contest dates shown on the Study page countdown. Update every school year.
CONTEST_DATES = [
    ("Invitational A deadline", "2027-01-16"),
    ("Invitational B deadline", "2027-02-13"),
    ("District", "2027-04-03"),
    ("Region", "2027-04-24"),
    ("State", "2027-05-17"),
]

CHEVRON = ('<svg class="chev" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" '
           'stroke-width="1.6" aria-hidden="true"><path d="M3 4.5l3 3 3-3"/></svg>')


def nav_menu(key, label, href, on, menu):
    cur = ' aria-current="true"' if on else ""
    return (f'<div class="dd" data-dd><a class="ddbtn{" on" if on else ""}" href="{BASE}{href}"{cur} '
            f'aria-haspopup="true" aria-expanded="false" aria-controls="menu-{key}">{label}{CHEVRON}</a>'
            f'<div class="menu" id="menu-{key}">{menu}</div></div>')


def current_list(db):
    lists = [r for r in db["reading-lists"].values() if r["year"]]
    return max(lists, key=lambda r: r["year"]) if lists else None


def list_parts(db, rl):
    """(label, record, kind) for a reading list's novel, play and poet."""
    out = []
    for field, kind in (("novel", "works"), ("play", "works"), ("poet", "authors")):
        for x in rl[field]:
            r = db[kind].get(x)
            if r:
                label = {"novel": "Novel", "play": "Play", "poet": "Poet"}[field]
                if field == "novel" and re.search(r"short stor", r["title"], re.I):
                    label = "Short stories"
                out.append((label, r, kind))
    return out


def build_nav_menus(db):
    def mi(href, title, sub=""):
        return f'<a class="mi" href="{BASE}{href}"><b>{title}</b>{f"<small>{sub}</small>" if sub else ""}</a>'
    n = lambda k: f"{len(listed(db, k)):,}"
    NAV_MENUS["ref"] = (
        '<div>' + mi("terms/", "Terms", f"{n('terms')} definitions, cross-linked")
        + mi("sets/", "Sets", "Terms grouped by topic")
        + mi("periods/", "Periods", "American and British timelines")
        + mi("prizes/", "Prizes", "Nobel, Pulitzer and more") + '</div>'
        + '<div>' + mi("authors/", "Authors", f"{n('authors')} writers with works and dates")
        + mi("works/", "Works", f"{n('works')} novels, plays, poems and stories")
        + mi("poems/", "Poems and passages", "Full texts from past tests")
        + mi("reading-lists/", "Reading lists", "Every year’s novel, play and poet")
        + f'<a class="mi all" href="{BASE}reference/"><b>All of Reference →</b></a></div>')
    rl = current_list(db)
    this_year = ""
    if rl:
        names = " · ".join(work_title_html(r) if k == "works" else e(r["title"]) for _, r, k in list_parts(db, rl))
        this_year = (f'<div class="gl">This year · {e(rl["year"].replace("-", "–"))}</div>'
                     + mi("study/#this-year", "Reading list", names))
    NAV_MENUS["study"] = (
        '<div>' + mi("study/", "Study home", "Countdown, cards due, your scores")
        + mi("tests/", "Practice tests", f"{len(db['tests'])} released tests, scored out of 100")
        + mi("study/quiz/", "Quick quiz", "10 questions by part or topic")
        + mi("essays/", "Essay prompts", "Past prompts with the full poem") + '</div>'
        + '<div>' + mi("flashcards/", "Flashcards", "Terms, authors, works and prizes")
        + mi("flashcards/review/", "Cards due today", "Everything you’ve studied that’s due")
        + this_year + mi("resources/", "Resources", "Guides and texts, free ones marked") + '</div>')


def home(db, rel, resolver):
    door_ref = """<section class="door door-ref" aria-labelledby="door-ref">
  <div class="door-head"><span class="door-icon" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/></svg></span>
  <div><p class="eyebrow">Reference</p><h2 id="door-ref">Look something up</h2></div></div>
  <p class="door-sub">Everything in one cross-linked library.</p>
  <a class="btn btn-ref" href="{base}reference/">Open the reference →</a>
</section>"""
    door_study = """<section class="door door-study" aria-labelledby="door-study">
  <div class="door-head"><span class="door-icon" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"/></svg></span>
  <div><p class="eyebrow">Study</p><h2 id="door-study">Practice for the contest</h2></div></div>
  <p class="door-sub">Practice for the UIL contest and track your progress.</p>
  <a class="btn btn-study" href="{base}study/">Start studying →</a>
</section>"""
    lede = "Everything you need for the UIL Literary Criticism contest: a cross-referenced library to look things up, and a place to practice."
    body = f"""
<section class="hero">
  <h1>{e(SITE_TITLE)}</h1>
  <p class="lede">{lede}</p>
  <form class="search big" action="{BASE}search/" role="search" autocomplete="off">
    <input type="search" name="q" placeholder="Try “sonnet” or “The Scarlet Letter”" aria-label="Search" data-search>
    <div class="results" hidden data-results></div>
  </form>
</section>
<div class="doors">{door_ref.format(base=BASE)}{door_study.format(base=BASE)}</div>
{daily_section(db, rel, resolver)}
"""
    write("index.html", page(SITE_TITLE, body, "home", lede, "", extra_head=FC_SCRIPT))


def reference_page(db):
    rl_years = sorted(r["year"] for r in db["reading-lists"].values() if r["year"])
    rows = [
        ("terms", "Terms", f"{len(listed(db, 'terms')):,}", "Definitions with cross-links to related terms"),
        ("tags", "Sets", f"{len(db['tags']):,}", "Terms grouped by topic, like tropes, poetic feet and the Top 200"),
        ("authors", "Authors", f"{len(listed(db, 'authors')):,}", "Dates, nationality, works, prizes and periods"),
        ("works", "Works", f"{len(listed(db, 'works')):,}", "Novels, plays, poems and stories with synopses"),
        ("poems", "Poems and passages", f"{len(db['poems']):,}", "Full texts from released tests"),
        ("reading-lists", "Reading lists", f"Since {rl_years[0][:4]}" if rl_years else "", "Each school year’s novel, play and poet"),
        ("periods", "Periods", f"{len(db['periods']):,}", "American and British timelines, with historical events"),
        ("prizes", "Prizes", f"{len(db['prizes']):,}", "Nobel, Pulitzer and other major literary prizes"),
    ]
    items = "".join(
        f'<li><a class="refrow" href="{BASE}{folder(k)}/"><span class="refrow-text"><span class="refrow-top">'
        f'<b>{label}</b><span class="refrow-count">{count}</span></span>'
        f'<span class="refrow-sub">{sub}</span></span><span class="refrow-arrow" aria-hidden="true">→</span></a></li>'
        for k, label, count, sub in rows)
    lede = "Every entry links to related entries and to the released test questions that mention it."
    body = f"""<div class="narrow">
<p class="eyebrow">Reference</p>
<h1>Look something up</h1>
<p class="lede">{lede}</p>
<ul class="plain reflist">{items}</ul>
<a class="cta-study" href="{BASE}study/"><span><b>Ready to practice?</b><span>Tests, quick quizzes and flashcards are in Study.</span></span>
<span class="btn btn-study">Go to Study →</span></a>
</div>"""
    write("reference/index.html", page("Reference", body, "reference", lede, "reference/"))


def study_page(db, rel):
    rl = current_list(db)
    year_html = ""
    if rl:
        cards = ""
        for label, r, kind in list_parts(db, rl):
            title = work_title_html(r) if kind == "works" else e(r["title"])
            if kind == "works":
                by = ", ".join(db["authors"][a]["title"] for a in rel[("works", r["id"])].get("authors", []))
            else:
                by = ", ".join(x for x in (r["nationality"], "–".join(y for y in (r["birth"], r["death"]) if y)) if x)
            cards += (f'<div class="rlcard"><span class="eyebrow-sm">{label}</span>'
                      f'<a class="rlcard-title" href="{r["url"]}">{title}</a>'
                      f'{f"<span class=rlcard-by>{e(by)}</span>" if by else ""}'
                      f'<span class="rlcard-links"><a href="{BASE}resources/?list={e(rl["year"], quote=True)}">Resources</a>'
                      f'<a href="{BASE}study/quiz/?{"work" if kind == "works" else "author"}={r["id"]}">Quiz on it</a></span></div>')
        year_html = f"""<section class="block" id="this-year"><h2>This year’s reading list · {e(rl['year'].replace('-', '–'))}</h2>
<div class="rlcards">{cards}</div>
<p class="more-line"><a href="{BASE}study/quiz/?list={rl['id']}">Quiz on the whole list →</a> · <a href="{BASE}reading-lists/">Past reading lists</a></p></section>"""
    tests = [{"p": t["url"], "t": t["title"]} for t in sorted(db["tests"].values(), key=test_sort)]
    data = {"dates": CONTEST_DATES, "tests": len(tests)}
    tools = "".join(
        f'<a class="tool" href="{BASE}{href}"><b>{title}</b><span>{sub}</span></a>'
        for href, title, sub in (
            ("tests/", "Practice tests", "Full released tests, scored out of 100"),
            ("study/quiz/", "Quick quiz", "10 questions by part, set, period or reading list"),
            ("flashcards/", "Flashcards", "Terms by set, authors and works, prize winners"),
            ("essays/", "Essay prompts", f"{len(db['essays'])} prompts with the poem’s full text")))
    body = f"""<p class="eyebrow">Study</p>
<h1>Your study home</h1>
<p class="guest-note" data-guest hidden>You’re studying as a guest, so your progress is saved in this browser only.
<a href="{BASE}account/">Sign in or create an account</a> to keep it on any device.</p>
<div class="tiles" data-study="{e(json.dumps(data), quote=True)}">
  <section class="tile tile-dark" data-countdown>
    <h2>Next contest date</h2>
    <b class="tile-big" data-cd-big>&nbsp;</b>
    <span class="tile-sub" data-cd-sub></span>
    <ul class="plain cd-list" data-cd-list></ul>
  </section>
  <section class="tile">
    <h2>Flashcards due</h2>
    <b class="tile-big" data-fc-big>0 cards</b>
    <span class="tile-sub" data-fc-sub>Start with a deck, and cards you study come back here when they’re due.</span>
    <a class="btn btn-study btn-sm" href="{BASE}flashcards/" data-fc-go>Choose a deck</a>
  </section>
  <section class="tile">
    <h2>Practice tests</h2>
    <b class="tile-big" data-ts-big>0 of {len(tests)}</b>
    <span class="tile-sub" data-ts-sub>Take a released test and score it to see your progress here.</span>
    <a class="btn btn-study btn-sm" href="{BASE}tests/">See all tests</a>
  </section>
</div>
<a class="resume" href="#" data-resume hidden><span><span class="eyebrow-sm">Pick up where you left off</span>
<b data-resume-title></b><span class="resume-sub" data-resume-sub></span></span><span class="btn btn-soft">Resume →</span></a>
<section class="block"><h2>Ways to study</h2><div class="tools">{tools}</div></section>
{year_html}
"""
    write("study/index.html", page("Study", body, "study", "Practice tests, quick quizzes, flashcards and essay prompts for UIL Literary Criticism.",
                                   "study/", extra_head=f'<script src="{BASE}assets/study.js?v={BUILD_ID}" defer></script>'))


def period_core(name):
    """'Romantic Period in English Literature, 1798-1870' -> ('romantic', 'British')."""
    region = ("American" if re.search(r"american", name, re.I)
              else "British" if re.search(r"english|british|england", name, re.I) else "")
    name = re.sub(r"\(.*?\)", " ", name).replace("Post-", "Post")
    name = re.split(r",| in | 1\d{3}", name)[0]
    words = [w for w in re.findall(r"[a-z]+", name.lower()) if w not in {"the", "period", "age", "of", "and"}]
    return " ".join(words), region


def period_authors(db):
    """Authors by Historical Periods record, matched from each author's Historical Period names."""
    cores = [(period_core(p["title"])[0], p["region"], p["id"]) for p in db["periods"].values()]
    out = defaultdict(list)
    for a in db["authors"].values():
        for name in a["periods"]:
            core, region = period_core(name)
            if not core:
                continue
            ok = lambda reg: not region or not reg or reg == region
            match = [pid for c, reg, pid in cores if c == core and ok(reg)]
            if not match:
                match = [pid for c, reg, pid in cores if c and (c.startswith(core + " ") or core.startswith(c + " ")) and ok(reg)]
            if len(match) == 1:
                out[match[0]].append(a["id"])
    return out


def quiz_bank(db, rel):
    """Every answerable released question, for the Quick quiz page (assets/data/qbank.json)."""
    tests, test_ix = [], {}
    for t in sorted(db["tests"].values(), key=test_sort):
        test_ix[t["id"]] = len(tests)
        tests.append([t["title"], t["url"], int(years_of(t["year"], t["title"]) or 0)])
    qs, used = [], {"terms": set(), "authors": set(), "works": set(), "poems": set()}
    for q in db["questions"].values():
        letters = [l for l in "abcde" if q[l]]
        correct = "".join(c.strip().upper() for c in q["correct"] if c.strip())
        if not q["test"] or q["test"][0] not in test_ix or is_redacted(q) or not letters or not correct:
            continue
        works = list(dict.fromkeys(q["works"] + q["rl_works"]))
        qs.append({"i": q["id"], "p": int(question_part(q) or 0), "t": test_ix[q["test"][0]], "n": q["number"],
                   "q": (q["prompt"] or q["name"]).strip(), "c": [q[l] for l in letters], "l": "".join(letters).upper(),
                   "a": correct, "tm": q["terms"], "au": q["authors"], "w": works, "po": q["poems"]})
        used["terms"].update(q["terms"]); used["authors"].update(q["authors"])
        used["works"].update(works); used["poems"].update(q["poems"])
    qs.sort(key=lambda x: (x["t"], int(x["n"] or 0)))
    poems = {}
    for pid in used["poems"]:
        p = db["poems"].get(pid)
        if p:
            poems[pid] = [p["title"], p["url"], p["text"], rel[("poems", pid)].get("authors", [])]
            used["authors"].update(poems[pid][3])
    # Topics: sets (terms), reading lists (works and authors), periods (authors).
    sets = {g["id"]: [g["title"], rel[("tags", g["id"])].get("terms", [])] for g in db["tags"].values()}
    lists = {}
    for r in sorted(db["reading-lists"].values(), key=lambda r: r["year"], reverse=True):
        authors = list(r["poet"])
        for w in r["novel"] + r["play"]:
            authors += rel[("works", w)].get("authors", [])
        lists[r["id"]] = [r["year"].replace("-", "–"), r["novel"] + r["play"], authors]
    periods = {}
    by_period = period_authors(db)
    for p in sorted(db["periods"].values(), key=lambda p: (p["region"], int(p["start"] or 0))):
        ids = list(by_period.get(p["id"], []))
        for sub in p["subs"]:
            ids += by_period.get(sub, [])
        if ids:
            periods[p["id"]] = [f'{p["title"]} ({p["region"]})' if p["region"] and p["region"] not in p["title"] else p["title"],
                                list(dict.fromkeys(ids))]
    def names(kind, ids, html=False):
        return {x: [work_title_html(db[kind][x]) if html else db[kind][x]["title"], db[kind][x]["url"]]
                for x in ids if x in db[kind]}
    bank = {"tests": tests, "q": qs, "poems": poems, "sets": sets, "lists": lists, "periods": periods,
            "terms": names("terms", used["terms"]), "authors": names("authors", used["authors"]),
            "works": names("works", used["works"], html=True)}
    (OUT / "assets" / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "data" / "qbank.json").write_text(json.dumps(bank, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return bank


def quiz_page(db, rel):
    bank = quiz_bank(db, rel)
    lists = sorted(db["reading-lists"].values(), key=lambda r: r["year"], reverse=True)
    sets = sorted((g for g in db["tags"].values() if g["id"] in bank["sets"]), key=lambda g: sort_key(g["title"]))
    opt = lambda v, label: f'<option value="{v}">{e(label)}</option>'
    topics = opt("", "Any topic")
    if lists:
        topics += opt(f"list:{lists[0]['id']}", f"This year’s reading list ({lists[0]['year'].replace('-', '–')})")
    topics += '<optgroup label="Sets">' + "".join(opt(f"set:{g['id']}", g["title"]) for g in sets) + "</optgroup>"
    topics += '<optgroup label="Periods">' + "".join(opt(f"period:{k}", v[0]) for k, v in bank["periods"].items()) + "</optgroup>"
    topics += '<optgroup label="Reading lists">' + "".join(opt(f"list:{r['id']}", r["year"].replace("-", "–")) for r in lists) + "</optgroup>"
    body = f"""<p class="crumbs-study"><a href="{BASE}study/">Study</a> › Quick quiz</p>
<h1>Quick quiz</h1>
<div class="qq" data-qq data-src="{BASE}assets/data/qbank.json?v={BUILD_ID}">
<form class="qq-form" data-qq-form onsubmit="return false">
  <h2>Build a quiz</h2>
  <fieldset class="qq-parts"><legend>Part of the test</legend>
    <div class="pills">
      <label><input type="radio" name="part" value="" checked><span>Any</span></label>
      <label><input type="radio" name="part" value="1"><span>Part 1</span></label>
      <label><input type="radio" name="part" value="2"><span>Part 2</span></label>
      <label><input type="radio" name="part" value="3"><span>Part 3</span></label>
    </div>
  </fieldset>
  <label for="qq-topic">Topic</label>
  <select id="qq-topic" name="topic">{topics}</select>
  <label for="qq-years">Tests from</label>
  <select id="qq-years" name="years"><option value="">All years</option><option value="5">Last 5 years</option><option value="3">Last 3 years</option></select>
  <label for="qq-n">Questions</label>
  <select id="qq-n" name="n"><option>10</option><option>20</option><option>30</option></select>
  <label class="check"><input type="checkbox" name="missed"> Only ones I missed before</label>
  <p class="qq-count" data-qq-count aria-live="polite"></p>
  <button type="submit" class="btn btn-study qq-go" data-qq-go>New quiz</button>
</form>
<section class="qq-main" data-qq-main aria-live="polite">
  <noscript><p>The quick quiz needs JavaScript turned on. You can still take the <a href="{BASE}tests/">practice tests</a>.</p></noscript>
  <p class="qq-empty" data-qq-empty>Pick what to practice, then press <b>New quiz</b>. Questions come from the {len(bank['tests'])} released tests.</p>
</section>
</div>"""
    write("study/quiz/index.html", page("Quick quiz", body, "study", "Ten-question quizzes from released UIL Literary Criticism tests.",
                                        "study/quiz/", extra_head=f'<script src="{BASE}assets/quickquiz.js?v={BUILD_ID}" defer></script>'))


def study_box(kind_label, quiz_param, rid, nq, card_slot):
    """The "Study this" panel on term, author, work and poem pages."""
    quiz = (f'<a class="btn btn-study btn-sm" href="{BASE}study/quiz/?{quiz_param}={rid}">Quiz me: '
            f'{min(nq, 10)} question{"s" if min(nq, 10) != 1 else ""}</a>') if nq else ""
    if not quiz and not card_slot:
        return ""
    return f'<aside class="studybox"><p class="eyebrow-sm">Study this {kind_label}</p><div class="studybox-row">{card_slot}{quiz}</div></aside>'


def account_page():
    """Sign in / create account / password reset, and the signed-in account summary (assets/account.js)."""
    def field(name, label, kind="text", auto=""):
        return (f'<label class="acct-field"><span>{label}</span>'
                f'<input name="{name}" type="{kind}" autocomplete="{auto}" required></label>')
    email = field("email", "Email", "email", "email")
    today = datetime.date.today()
    first = today.year + (1 if today.month >= 8 else 0)          # this school year's seniors
    years = "".join(f'<option value="{y}">{y}</option>' for y in range(first, first + 4))

    def profile_fields(prefix):
        return f"""<div class="acct-field"><span>I'm a</span>
  <div class="acct-choices">
    <label><input type="radio" name="role" value="student"> Student</label>
    <label><input type="radio" name="role" value="coach"> Coach</label>
  </div></div>
  <label class="acct-field" data-grad hidden><span>Graduation year</span>
    <select name="graduation_year"><option value="">Choose…</option>{years}<option value="other">Other</option></select></label>
  <label class="acct-field" data-grad-other hidden><span>Graduation year (other)</span>
    <input name="graduation_year_other" type="number" min="2000" max="2100" inputmode="numeric"></label>
  <label class="acct-field"><span>School</span>
    <input name="school" type="text" maxlength="120" autocomplete="off" list="uil-schools-{prefix}"
      placeholder="Start typing your school's name" data-school-input></label>
  <datalist id="uil-schools-{prefix}" data-school-list></datalist>
  <label class="acct-check" data-school-other hidden><input type="checkbox" name="school_other"> My school isn't on the list</label>"""

    body = f"""<section class="account" data-account>
<h1>Your account</h1>
<p class="lede">Sign in to save your practice answers and test scores to your account, so they follow you to any browser or device. You can still practice without an account; your progress is then kept in this browser only.</p>
<div data-view="loading"><p class="muted">Loading…</p></div>
<div data-view="off" hidden><p>Accounts aren't switched on yet. Your progress is saved in this browser.</p></div>
<form id="acct-signin" data-view="signin" hidden novalidate>
  <h2>Sign in</h2>
  {email}
  {field("password", "Password", "password", "current-password")}
  <button type="submit" class="acct-btn">Sign in</button>
  <p class="acct-msg" role="status"></p>
  <p class="acct-alt"><a href="#" data-go="forgot">Forgot your password?</a> · No account yet? <a href="#" data-go="signup">Create one</a></p>
</form>
<form id="acct-signup" data-view="signup" hidden novalidate>
  <h2>Create an account</h2>
  {email}
  {field("password", "Password (at least 8 characters)", "password", "new-password")}
  {field("password2", "Password again", "password", "new-password")}
  <fieldset class="acct-profile"><legend>About you <span class="muted">(optional; you can change this later)</span></legend>
  {profile_fields("su")}
  </fieldset>
  <button type="submit" class="acct-btn">Create account</button>
  <p class="acct-msg" role="status"></p>
  <p class="acct-alt">Anything you've already answered in this browser will be saved to your new account. Already have an account? <a href="#" data-go="signin">Sign in</a></p>
</form>
<form id="acct-forgot" data-view="forgot" hidden novalidate>
  <h2>Forgot your password?</h2>
  <p>Enter your email and we'll send you a link to set a new password.</p>
  {email}
  <button type="submit" class="acct-btn">Send the link</button>
  <p class="acct-msg" role="status"></p>
  <p class="acct-alt"><a href="#" data-go="signin">Back to sign in</a></p>
</form>
<form id="acct-reset" data-view="reset" hidden novalidate>
  <h2>Set a new password</h2>
  {field("password", "New password (at least 8 characters)", "password", "new-password")}
  {field("password2", "New password again", "password", "new-password")}
  <button type="submit" class="acct-btn">Save password</button>
  <p class="acct-msg" role="status"></p>
</form>
<div data-view="account" hidden>
  <p class="acct-who">Signed in as <strong data-acct-email></strong></p>
  <p>Saved to your account: <span data-acct-count></span>. <span class="acct-status muted" data-acct-status></span></p>
  <p><a class="acct-btn" href="{BASE}tests/">Go to practice tests</a></p>
</div>
<form id="acct-profile" data-view-also="account" hidden novalidate>
  <h2>Your profile</h2>
  {profile_fields("pf")}
  <button type="submit" class="acct-btn">Save profile</button>
  <p class="acct-msg" role="status"></p>
</form>
<div data-view-also="account" hidden>
  <p class="acct-alt"><a href="#" data-go="reset">Change password</a> · <button type="button" class="linkish" data-signout>Sign out</button></p>
  <p class="muted small">Signing out clears your progress from this browser; it stays saved in your account.</p>
</div>
</section>
<script>window.LITCRIT_SCHOOLS = "{BASE}assets/data/schools.json?v={BUILD_ID}";</script>
<script src="{BASE}assets/account.js?v={BUILD_ID}" defer></script>"""
    write("account/index.html", page("Your account", body, None, "Sign in to save your practice test progress.", "account/"))


def search_page():
    body = """<h1>Search</h1>
<form class="search big" action="" role="search" autocomplete="off">
  <input type="search" name="q" placeholder="Search terms, authors, works…" aria-label="Search" data-search data-full>
</form>
<div class="full-results" data-full-results></div>"""
    write("search/index.html", page("Search", body, None, "Search the site", "search/"))


def search_index(db):
    entries = []
    for key, _, singular in SECTIONS:
        if key in NO_PAGES or key not in db:
            continue
        for r in db[key].values():
            if r["title"].strip().lower() == "no award":
                continue
            extra = ""
            if key == "terms":
                extra = r["short"][:90]
            elif key == "authors":
                extra = " – ".join(x for x in (r["birth"], r["death"]) if x)
            elif key == "works":
                extra = ", ".join(db["authors"][a]["title"] for a in r["authors"])
            elif key == "periods":
                extra = r["region"]
            elif key == "poems":
                extra = ", ".join(db["authors"][a]["title"] for a in r["authors"])
            elif key == "tests":
                extra = f'{len(r["questions"])} questions'
            elif key == "essays":
                extra = ", ".join(db["poems"][p]["title"] for p in r["poems"] if p in db["poems"])
            alt = r.get("alternate", "") if key == "authors" else ""
            entries.append([r["title"], singular, r["url"][len(BASE):], extra, alt])
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "search.json").write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def old_address_redirects(db):
    """Pages at the old /tags/ addresses that forward to /sets/, so saved links and bookmarks keep working."""
    def stub(to):
        return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved</title>'
                f'<meta name="robots" content="noindex"><link rel="canonical" href="{to}">'
                f'<meta http-equiv="refresh" content="0; url={to}">'
                f'<script>location.replace("{to}" + location.search + location.hash)</script></head>'
                f'<body><p>This page has moved to <a href="{to}">{to}</a>.</p></body></html>')
    write("tags/index.html", stub(f"{BASE}sets/"))
    for g in db["tags"].values():
        write(f"tags/{g['slug']}/index.html", stub(g["url"]))


def sitemap(db):
    write("robots.txt", "User-agent: *\nAllow: /\n" + (f"Sitemap: {SITE_URL}sitemap.xml\n" if SITE_URL else ""))
    if not SITE_URL:
        return
    urls = [SITE_URL] + [f"{SITE_URL}{folder(k)}/" for k, _, _ in SECTIONS]
    for key in db:
        for r in db[key].values():
            if r.get("url") and "#" not in r["url"]:
                urls.append(SITE_URL + r["url"][len(BASE):])
    body = "".join(f"<url><loc>{e(u)}</loc></url>" for u in urls)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>')


# ---------------------------------------------------------------- main

BUILD_DATE = datetime.date.today().strftime("%B %-d, %Y")
BUILD_ID = str(int(time.time()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures")
    ap.add_argument("--save-data")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()

    raw = load_data(args)
    db = normalize(raw)
    assign_urls(db)
    resolver = Resolver(db)
    rel = build_relations(db)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(Path(__file__).parent / "assets", OUT / "assets")
    (OUT / ".nojekyll").write_text("")
    schools = load_schools(args)
    if schools:
        (OUT / "assets" / "data").mkdir(parents=True, exist_ok=True)
        (OUT / "assets" / "data" / "schools.json").write_text(json.dumps(schools, ensure_ascii=False, separators=(",", ":")))

    if not args.no_images:
        prepare_media(db)

    periods_by_term = defaultdict(list)
    for p in db["periods"].values():
        tid = resolver.find("terms", p["term_text"]) if p["term_text"] else None
        if tid:
            periods_by_term[tid].append(p["id"])

    card_data(db, rel)
    global RESOLVER
    RESOLVER = resolver
    build_nav_menus(db)

    print("Writing pages…", flush=True)
    for t in db["terms"].values():
        term_page(db, rel, resolver, t, periods_by_term)
    for a in db["authors"].values():
        author_page(db, rel, resolver, a)
    for w in db["works"].values():
        work_page(db, rel, resolver, w)
    for p in db["prizes"].values():
        prize_page(db, rel, p)
    for p in db["periods"].values():
        period_page(db, resolver, p)
    for g in db["tags"].values():
        tag_page(db, rel, g)
    for t in db["tests"].values():
        test_page(db, rel, t)
    for p in db["poems"].values():
        poem_page(db, rel, p)
    for x in db["essays"].values():
        essay_page(db, rel, x)

    alpha_index(db, "terms", "Terms", "Definitions are cross-linked: follow any term in small capitals.")
    alpha_index(db, "authors", "Authors", "Sorted by last name.")
    alpha_index(db, "works", "Works", "Sorted by title.")
    alpha_index(db, "poems", "Poems", "Poems and passages from the tests.")
    catalog_terms(db, rel)
    catalog_authors(db, rel)
    catalog_works(db, rel)
    catalog_poems(db, rel)
    tests_index(db, rel)
    essays_index(db, rel)
    reading_lists_index(db)
    prizes_index(db, rel)
    periods_index(db)
    tags_index(db, rel)
    resources_index(db, resolver)
    flashcard_pages(db, rel)
    home(db, rel, resolver)
    reference_page(db)
    study_page(db, rel)
    quiz_page(db, rel)
    search_page()
    account_page()
    search_index(db)
    sitemap(db)
    old_address_redirects(db)
    write("404.html", page("Page not found", f'<h1>Page not found</h1><p class="lede">That page may have been renamed. Try searching, or go <a href="{BASE}">home</a>.</p>'))

    n = sum(1 for _ in OUT.rglob("*.html"))
    print(f"Done: {n:,} pages in {OUT}/", flush=True)


if __name__ == "__main__":
    main()
