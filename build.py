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
        "authors": "fld7yDp5hGXqHPeFG",
    }),
    "authors": ("tblv2LTIvL1vj36zt", {
        "name": "fldir5h8wsLHZmNkd", "nationality": "fldNiSyQVIr0teads", "birth": "fldf97H8m30BZfQuE",
        "death": "fldCDFWFnZJKY3mqm", "groups": "fldx28iQe6cYRk0pa", "prizes": "fldf8HBg9txnPnabO",
        "picture": "fldluSS0389Zj68Zl", "picture_url": "fldzmCf0XXpX4c5Tb", "wikipedia": "fldAAuog6Fwr9drOP",
        "youtube": "fldCqLxv0I0o7sIwJ", "periods": "fldOoPpnA2yNHkANz", "medium": "fldEGUGQHuKJxaxiR",
        "first": "fldSm5ftkHEn0C596", "last": "fld3cDnR7vH49g28M", "alternate": "fld83eZxzidKWyNUC",
        "terms": "fldJhoUfxqtEGQHwi", "works": "fldvgfsTJz4vMzRxj",
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
        "work": "fldpIadf3Zq41nZKo", "link": "fld94UO33vHDZzs7N",
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
}

# Tables shown inside other pages rather than with pages of their own.
NO_PAGES = {"resources", "questions", "essays", "reading-lists"}

SECTIONS = [  # url folder, nav label, singular label
    ("terms", "Terms", "Term"),
    ("authors", "Authors", "Author"),
    ("works", "Works", "Work"),
    ("poems", "Poems", "Poem"),
    ("tests", "Tests", "Test"),
    ("reading-lists", "Reading Lists", "Reading list"),
    ("prizes", "Prizes", "Prize"),
    ("periods", "Periods", "Period"),
    ("tags", "Tags", "Tag"),
    ("resources", "Resources", "Resource"),
]

SITE_TITLE = os.environ.get("SITE_TITLE", "Literary Criticism")
BASE = "/" + os.environ.get("BASE_PATH", "/").strip("/") + "/"
BASE = "/" if BASE == "//" else BASE
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/") + "/" if os.environ.get("SITE_URL") else ""

OUT = Path("site")
MEDIA_CACHE = Path(".media-cache")


# ---------------------------------------------------------------- fetching

def fetch_table(token, table_id, field_ids):
    records, offset = [], None
    while True:
        params = [("pageSize", "100"), ("returnFieldsByFieldId", "true")]
        params += [("fields[]", f) for f in field_ids]
        if offset:
            params.append(("offset", offset))
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}?" + urllib.parse.urlencode(params)
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
    "resources": {},
    "reading-lists": {"novel": "works", "play": "works", "poet": "authors"},
    "poems": {"authors": "authors", "essays": "essays", "questions": "questions"},
    "questions": {"test": "tests", "poems": "poems", "rl_works": "works", "terms": "terms",
                  "authors": "authors", "works": "works"},
    "tests": {"questions": "questions"},
    "essays": {"poems": "poems"},
}
LIST_FIELDS = {
    "authors": {"groups", "periods", "medium"},
    "works": {"reading_list", "type", "language"},
    "resources": {"work"},
    "questions": {"correct"},
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
            r["url"] = None if key in NO_PAGES else f"{BASE}{key}/{slug}/"
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


class Resolver:
    """Finds records by name, for text fields that hold names instead of links."""

    def __init__(self, db):
        self.by_name = {k: {} for k in db}
        for key, recs in db.items():
            for r in sorted(recs.values(), key=lambda r: r["id"], reverse=True):
                for n in self.name_variants(r["title"]):
                    self.by_name[key][n] = r["id"]
                if key == "authors" and r.get("alternate"):
                    for alt in re.split(r"[;,]", r["alternate"]):
                        for n in self.name_variants(alt):
                            self.by_name[key].setdefault(n, r["id"])

    @staticmethod
    def name_variants(name):
        name = name.strip()
        if not name:
            return []
        out = {fold(name)}
        m = re.match(r"^(.*?)\s*\((?:or|also|also called|sometimes)\s+(.*?)\)\s*$", name, re.I)
        if m:
            out.add(fold(m.group(1)))
            for alt in re.split(r",|\bor\b", m.group(2)):
                if alt.strip():
                    out.add(fold(alt.strip()))
        base = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
        if base:
            out.add(fold(base))
        m = re.match(r"^(.*),\s*(the|a|an)$", name, re.I)
        if m:
            out.add(fold(f"{m.group(2)} {m.group(1)}"))
            out.add(fold(m.group(1)))
        return [o.strip() for o in out if o.strip()]

    def find(self, key, name):
        return self.by_name[key].get(fold(name.strip()))


# ---------------------------------------------------------------- rich text

def autolink_caps(text_html, ctx):
    """In definitions, words set in CAPITALS are cross-references to other terms."""
    if not ctx:
        return text_html
    db, resolver, prefer = ctx

    def repl(m):
        phrase = m.group(0)
        if len(re.sub(r"[^A-Z]", "", phrase)) < 3:
            return phrase
        candidates = [phrase]
        words = phrase.split()
        last = words[-1]
        for suffix, rep in (("IES", "Y"), ("ES", ""), ("S", ""), ("'S", ""), ("’S", "")):
            if last.endswith(suffix) and len(last) > len(suffix) + 2:
                candidates.append(" ".join(words[:-1] + [last[: -len(suffix)] + rep]))
        tid = None
        for c in candidates:
            key = fold(html.unescape(c))
            hits = [x for x in prefer if key in Resolver.name_variants(db["terms"][x]["title"])]
            tid = hits[0] if hits else resolver.find("terms", html.unescape(c))
            if tid:
                break
        if not tid:
            return phrase
        return f'<a class="xref" href="{db["terms"][tid]["url"]}">{phrase.lower()}</a>'

    return re.sub(r"(?<![\w/#&])[A-Z][A-Z’'\-]+(?:\s+(?:OF|AND|THE|IN|A|[A-Z][A-Z’'\-]+))*(?![\w])",
                  repl, text_html)


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
    nav = "".join(
        f'<a href="{BASE}{k}/"{" aria-current=page" if k == active else ""}>{label}</a>'
        for k, label, _ in SECTIONS
    )
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
{extra_head}
</head>
<body>
<header class="top">
  <div class="wrap top-inner">
    <a class="brand" href="{BASE}"><span class="mark">¶</span>{e(SITE_TITLE)}</a>
    <form class="search" action="{BASE}search/" role="search" autocomplete="off">
      <input type="search" name="q" placeholder="Search terms, authors, works…" aria-label="Search" data-search>
      <div class="results" hidden data-results></div>
    </form>
  </div>
  <nav class="wrap nav" aria-label="Sections">{nav}</nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap">Updated {BUILD_DATE} · <a href="{BASE}">{e(SITE_TITLE)}</a></div></footer>
<script>window.SITE_BASE = "{BASE}";</script>
<script src="{BASE}assets/search.js?v={BUILD_ID}" defer></script>
</body>
</html>
"""


def write(path, content):
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def crumbs(key, label):
    return f'<p class="crumbs"><a href="{BASE}{key}/">{label}</a></p>'


# ---------------------------------------------------------------- record pages

def term_page(db, rel, resolver, t, periods_by_term):
    tid = t["id"]
    related = list(dict.fromkeys(t["related"]))
    mentioned = [x for x in t["mentioned"] if x not in related]
    mentioned_in = rel[("terms", tid)].get("rev:terms:mentioned", [])
    related_by = [x for x in rel[("terms", tid)].get("rev:terms:related", []) if x not in related and x not in mentioned_in]
    ctx = (db, resolver, t["mentioned"] + t["related"])
    body = f"""{crumbs('terms', 'Terms')}
<article class="record">
<h1>{e(t['title'])}</h1>
{f'<p class="lede">{e(t["short"])}</p>' if t['short'] else ''}
<div class="prose">{md_to_html(t['definition'], ctx)}</div>
</article>
{section('Related terms', chips(db, 'terms', related), len(related))}
{section('Terms mentioned', chips(db, 'terms', mentioned), len(mentioned))}
{section('Mentioned in', chips(db, 'terms', mentioned_in, limit=40), len(mentioned_in))}
{section('Also see', chips(db, 'terms', related_by, limit=40), len(related_by))}
{section('Periods', chips(db, 'periods', periods_by_term.get(tid, [])))}
{section('Authors', chips(db, 'authors', rel[('terms', tid)].get('authors', []), limit=40), len(rel[('terms', tid)].get('authors', [])))}
{section('Tags', chips(db, 'tags', rel[('terms', tid)].get('tags', [])))}
{questions_section(db, rel[('terms', tid)].get('questions', []))}
"""
    write(f"terms/{t['slug']}/index.html",
          page(t["title"], body, "terms", t["short"] or t["definition"][:200], f"terms/{t['slug']}/"))


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
<h1>{e(a['title'])}</h1>
{f'<p class="lede">{e(years)}</p>' if years else ''}
{meta}
{f'<p class="links">{links}</p>' if links else ''}
</div>
</article>
{section('Works', work_list(db, works), len(works))}
{section('Prizes', f'<ul class="plain">{prize_list}</ul>' if prize_list else '', len(prizes))}
{section('Movements and groups', chips(db, 'terms', group_ids))}
{section('Periods', chips(db, 'terms', period_term_ids))}
{section('Appears in these terms', chips(db, 'terms', terms, limit=60), len(terms))}
{section('Poems and passages', chips(db, 'poems', rel[('authors', aid)].get('poems', [])), len(rel[('authors', aid)].get('poems', [])))}
{section('Reading lists', reading_list_links(db, rel[('authors', aid)].get('reading-lists', [])))}
{questions_section(db, rel[('authors', aid)].get('questions', []))}
"""
    desc = f"{a['title']} ({years}). " + (f"{a['nationality']} {', '.join(a['medium']).lower()}." if a["nationality"] else "")
    write(f"authors/{a['slug']}/index.html", page(a["title"], body, "authors", desc, f"authors/{a['slug']}/"))


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
<h1>{work_title_html(w)}{star}</h1>
{f'<p class="lede">by {by}</p>' if by else ''}
{meta}
</div>
</article>
{section('Synopsis', f'<div class="prose">{md_to_html(w["synopsis"])}</div>' if w['synopsis'] else '')}
{section('Prizes', f'<ul class="plain">{prize_list}</ul>' if prize_list else '')}
{section('Terms', chips(db, 'terms', term_ids))}
{section('Reading resources', f'<ul class="plain">{res_list}</ul>' if res_list else '')}
{section('Reading lists', reading_list_links(db, rel[('works', wid)].get('reading-lists', [])))}
{questions_section(db, rel[('works', wid)].get('questions', []))}
"""
    author_names = ", ".join(db["authors"][a]["title"] for a in authors)
    desc = (w["synopsis"] or f"{w['title']}" + (f" by {author_names}" if author_names else ""))[:250]
    write(f"works/{w['slug']}/index.html", page(w["title"], body, "works", desc, f"works/{w['slug']}/"))


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


def questions_section(db, qids, title="Practice questions", limit=12):
    qids = [q for q in dict.fromkeys(qids) if db["questions"][q]["url"]]
    if not qids:
        return ""
    qids.sort(key=lambda q: (test_sort(db["tests"][db["questions"][q]["test"][0]]),
                             int(db["questions"][q]["number"] or 0)))

    def li(q):
        r = db["questions"][q]
        prompt = re.sub(r"\s+", " ", r["title"])
        prompt = prompt if len(prompt) < 160 else prompt[:157].rsplit(" ", 1)[0] + "…"
        return f'<li><a href="{r["url"]}">{e(prompt)}</a> <span class="muted">{e(test_label(db, r))}</span></li>'

    items = "".join(li(q) for q in qids[:limit])
    more = ""
    if len(qids) > limit:
        more = f'<details class="more"><summary>{len(qids) - limit} more</summary><ul class="plain qlist">' \
               + "".join(li(q) for q in qids[limit:]) + "</ul></details>"
    return section(title, f'<ul class="plain qlist">{items}</ul>{more}', len(qids))


def reading_list_links(db, ids):
    ids = sorted(dict.fromkeys(ids), key=lambda i: db["reading-lists"][i]["title"], reverse=True)
    if not ids:
        return ""
    links = "".join(f'<a class="chip" href="{db["reading-lists"][i]["url"]}">{e(db["reading-lists"][i]["title"])}</a>'
                    for i in ids)
    return f'<div class="chips">{links}</div>'


def multiline(text):
    return "<br>".join(e(line) for line in text.strip().split("\n"))


def question_html(db, q):
    choices = ""
    for letter in "abcde":
        if q[letter]:
            choices += f'<li data-letter="{letter.upper()}">{e(q[letter])}</li>'
    correct = [c.strip().upper() for c in q["correct"] if c.strip()]
    answer = ", ".join(
        f"{c}. {e(q[c.lower()])}" if c.lower() in "abcde" and q.get(c.lower()) else e(c) for c in correct)
    links = []
    for p in q["poems"]:
        links.append(f'<a href="{db["poems"][p]["url"]}">{e(db["poems"][p]["title"])}</a>')
    for k in ("works", "authors"):
        for x in q[k]:
            r = db[k][x]
            links.append(f'<a href="{r["url"]}">{work_title_html(r) if k == "works" else e(r["title"])}</a>')
    terms = sorted(q["terms"], key=lambda t: sort_key(db["terms"][t]["title"]))
    term_links = ", ".join(f'<a href="{db["terms"][t]["url"]}">{e(db["terms"][t]["title"])}</a>' for t in terms)
    return f"""<li class="q" id="q-{q['id']}">
<div class="qnum">{e(q['number'])}</div>
<div class="qbody">
<p class="prompt">{multiline(q['prompt'] or q['name'])}</p>
{f'<ol class="choices">{choices}</ol>' if choices else ''}
{f'<details class="answer"><summary>Show answer</summary><p>{answer}</p></details>' if answer else ''}
{f'<p class="qmeta">About: {" · ".join(links)}</p>' if links else ''}
{f'<p class="qmeta">Terms: {term_links}</p>' if term_links else ''}
</div>
</li>"""


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
<h1>{e(t['title'])}</h1>
<p class="lede">{len(qids)} question{'s' if len(qids) != 1 else ''}. Try each one, then open “Show answer.”</p>
{facts([('Year', e(t['year'])), ('Contest', e(t['type'])), ('Passage', e(t['passage']))])}
</article>
{section('Poems and passages on this test', chips(db, 'poems', poems, sort=False))}
"""
    for part in sorted(parts, key=lambda p: (p == "", p)):
        heading = f'<h2 class="letter">{e(part)}</h2>' if part else ""
        body += heading + '<ol class="plain questions">' + "".join(question_html(db, db["questions"][q]) for q in parts[part]) + "</ol>"
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
<h1>{e(p['title'])}</h1>
{f'<p class="lede">by {by}</p>' if by else ''}
{f'<div class="poem">{multiline(p["text"])}</div>' if p['text'] else ''}
</article>
{section('Appeared on', chips(db, 'tests', tests, sort=False), len(tests))}
{section('Essay prompts', essay_html, len(essays))}
{questions_section(db, rel[('poems', pid)].get('questions', []), 'Questions about this text', limit=30)}
"""
    names = ", ".join(db["authors"][a]["title"] for a in authors)
    write(f"poems/{p['slug']}/index.html", page(p["title"], body, "poems", f"{p['title']}" + (f" by {names}" if names else ""), f"poems/{p['slug']}/"))


def tests_index(db, rel):
    by_year = defaultdict(list)
    for t in db["tests"].values():
        by_year[t["year"] or "Other"].append(t)
    total = len(db["questions"])
    body = f'<h1>Tests</h1><p class="lede">{len(db["tests"])} released tests with {total:,} practice questions.</p>'
    for year in sorted(by_year, reverse=True):
        cards = "".join(
            f'<a class="card" href="{t["url"]}"><strong>{e(t["type"] or t["title"])}</strong>'
            f'<span class="muted">{len(rel[("tests", t["id"])].get("questions", []))} questions</span></a>'
            for t in sorted(by_year[year], key=lambda t: sort_key(t["type"] or t["title"])))
        body += f'<h2 class="letter">{e(year)}</h2><div class="cards">{cards}</div>'
    write("tests/index.html", page("Tests", body, "tests", "Released tests with practice questions", "tests/"))


def reading_lists_index(db):
    body = '<h1>Reading lists</h1><p class="lede">The novel, play and poet for each school year.</p>'
    rows = ""
    for rl in sorted(db["reading-lists"].values(), key=lambda r: r["title"], reverse=True):
        def cell(key, ids):
            return ", ".join(rec_link(db, key, i, "plainlink") for i in ids) or '<span class="muted">—</span>'
        rows += (f'<tr id="{rl["slug"]}"><th scope="row">{e(rl["title"])}</th>'
                 f'<td>{cell("works", rl["novel"])}</td><td>{cell("works", rl["play"])}</td>'
                 f'<td>{cell("authors", rl["poet"])}</td></tr>')
    body += f'<div class="tablewrap"><table class="rl"><thead><tr><th>Year</th><th>Novel</th><th>Play</th><th>Poet</th></tr></thead><tbody>{rows}</tbody></table></div>'
    write("reading-lists/index.html", page("Reading lists", body, "reading-lists", "Reading lists by school year", "reading-lists/"))


def prize_page(db, rel, p):
    pid = p["id"]
    works = rel[("prizes", pid)].get("works", [])
    authors = rel[("prizes", pid)].get("authors", [])
    body = f"""{crumbs('prizes', 'Prizes')}
<article class="record">
<h1>{e(p['title'])}</h1>
{facts([('Prize', e(p['type'])), ('Year', e(p['year'])), ('Nationality', e(', '.join(dict.fromkeys(db['authors'][a]['nationality'] for a in authors if db['authors'][a]['nationality']))) if 'nobel' in p['type'].lower() else '')])}
{f'<blockquote class="citation">{e(p["citation"])}</blockquote>' if p['citation'] else ''}
</article>
{section('Winner', chips(db, 'authors', authors))}
{section('Winning work', chips(db, 'works', works))}
"""
    write(f"prizes/{p['slug']}/index.html", page(p["title"], body, "prizes", p["citation"] or p["title"], f"prizes/{p['slug']}/"))


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
<h1>{e(p['title'])}</h1>
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
    body = f"""{crumbs('tags', 'Tags')}
<article class="record">
<h1>{e(g['title'])}</h1>
<p class="lede">{len(terms)} term{'s' if len(terms) != 1 else ''}</p>
{f'<p class="links">Study this set: {study}</p>' if study else ''}
</article>
{f'<ul class="plain defs">{rows}</ul>' if rows else ''}
"""
    write(f"tags/{g['slug']}/index.html", page(g["title"], body, "tags", f"{len(terms)} literary terms tagged {g['title']}", f"tags/{g['slug']}/"))


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


def alpha_index(db, key, label, intro):
    recs = list(db[key].values())
    sorter = author_sort if key == "authors" else (lambda r: sort_key(r["title"]))
    recs.sort(key=sorter)
    groups = defaultdict(list)
    for r in recs:
        groups[letter_of(r["last"] if key == "authors" and r["last"] else r["title"])].append(r)
    letters = sorted(groups, key=lambda L: (L == "#", L))
    split = len(recs) > 700
    head = f'<h1>{label}</h1><p class="lede">{len(recs):,} {label.lower()}. {intro}</p>'
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
        if i == 0:
            write(f"{key}/index.html", page(label, body, key, f"{label} in {SITE_TITLE}", f"{key}/"))


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
            if is_no_award(db, p, authors, works):
                rows.append(f'<li class="none">{yr}<span class="noaward">No Award</span></li>')
                continue
            if nobel:
                who = ", ".join(db["authors"][a]["title"] for a in authors)
                what = ", ".join(db["works"][w]["title"] for w in works)
                label = " — ".join(x for x in (who, what) if x) or p["title"]
                nats = list(dict.fromkeys(db["authors"][a]["nationality"] for a in authors if db["authors"][a]["nationality"]))
                nat = f'<span class="nat">{e(", ".join(nats))}</span>'
                rows.append(f'<li>{yr}<a href="{p["url"]}">{e(label)}</a>{nat}</li>')
            else:
                work_cell = ", ".join(f'<a href="{db["works"][w]["url"]}">{work_title_html(db["works"][w])}</a>' for w in works) \
                    or f'<a href="{p["url"]}">{e(p["title"])}</a>'
                author_cell = ", ".join(f'<a href="{db["authors"][a]["url"]}">{e(db["authors"][a]["title"])}</a>' for a in authors)
                rows.append(f'<li>{yr}<span class="pw">{work_cell}</span><span class="pa">{author_cell}</span></li>')
        cls = "plain years nobel" if nobel else "plain years pulitzer"
        tabs += (f'<a role="tab" href="#{slug}" id="tab-{slug}" aria-controls="{slug}"'
                 f'{" aria-selected=true" if i == 0 else ""}>{e(t)} <span class="count">{len(by_type[t])}</span></a>')
        panels += (f'<section class="tabpanel" id="{slug}" role="tabpanel" aria-labelledby="tab-{slug}">'
                   f'<h2 class="letter">{e(t)} <span class="count">{len(by_type[t])}</span></h2>'
                   f'<ul class="{cls}">{"" if nobel else PULITZER_HEAD}{"".join(rows)}</ul></section>')
    body = (f'<h1>Prizes</h1><p class="lede">{len(db["prizes"]):,} awards, newest first.</p>'
            f'<nav class="tabs" role="tablist" aria-label="Prize">{tabs}</nav>{panels}')
    write("prizes/index.html", page("Prizes", body, "prizes", "Literary prizes and their winners", "prizes/",
                                    extra_head=f'<script src="{BASE}assets/tabs.js?v={BUILD_ID}" defer></script>'))


def periods_index(db):
    by_region = defaultdict(list)
    for p in db["periods"].values():
        by_region[p["region"] or "Other"].append(p)
    body = '<h1>Periods</h1><p class="lede">Literary periods by region, in order.</p>'
    for region in sorted(by_region):
        rows = "".join(
            f'<li><span class="yr">{e(" – ".join(x for x in (p["start"], p["end"]) if x))}</span>'
            f'<a href="{p["url"]}">{e(p["title"])}</a>'
            f'{" <span class=muted>(" + e(p["type"]) + ")</span>" if p["type"] and p["type"] != "Period" else ""}</li>'
            for p in sorted(by_region[region], key=lambda p: (int(p["start"] or 0), sort_key(p["title"]))))
        body += f'<h2 class="letter">{e(region)}</h2><ul class="plain years">{rows}</ul>'
    write("periods/index.html", page("Periods", body, "periods", "Literary periods by region", "periods/"))


def tags_index(db, rel):
    tags = sorted(db["tags"].values(), key=lambda g: sort_key(g["title"]))
    cards = "".join(
        f'<a class="card" href="{g["url"]}"><strong>{e(g["title"])}</strong>'
        f'<span class="muted">{len(rel[("tags", g["id"])].get("terms", []))} terms</span></a>' for g in tags)
    body = f'<h1>Tags</h1><p class="lede">Terms grouped by topic, with study sets.</p><div class="cards">{cards}</div>'
    write("tags/index.html", page("Tags", body, "tags", "Literary terms grouped by topic", "tags/"))


def resources_index(db, resolver):
    by_work = defaultdict(list)
    for r in db["resources"].values():
        by_work[", ".join(r["work"]) or "General"].append(r)
    body = '<h1>Reading resources</h1><p class="lede">Texts, audio and study materials, grouped by work.</p>'
    for name in sorted(by_work, key=sort_key):
        wid = resolver.find("works", name) or resolver.find("authors", name)
        heading = e(name)
        if wid and wid in db["works"]:
            heading = f'<a href="{db["works"][wid]["url"]}">{work_title_html(db["works"][wid])}</a>'
        elif wid and wid in db["authors"]:
            heading = f'<a href="{db["authors"][wid]["url"]}">{e(name)}</a>'
        rows = "".join(
            f'<li>{ext_link(r["link"], r["title"]) or e(r["title"])}'
            f'{" <span class=muted>" + e(r["type"]) + (" · " + e(r["year"]) if r["year"] else "") + "</span>" if r["type"] or r["year"] else ""}</li>'
            for r in sorted(by_work[name], key=lambda r: sort_key(r["title"])))
        body += f'<h2 class="letter">{heading}</h2><ul class="plain">{rows}</ul>'
    write("resources/index.html", page("Reading resources", body, "resources", "Reading resources by work", "resources/"))


def home(db, rel):
    counts = "".join(
        f'<a class="stat" href="{BASE}{k}/"><strong>{len(db[k]):,}</strong><span>{label}</span></a>'
        for k, label, _ in SECTIONS if db[k])
    # A few well-connected terms to start from.
    popular = sorted(db["terms"].values(),
                     key=lambda t: -(len(rel[("terms", t["id"])].get("rev:terms:mentioned", [])) + len(t["related"])))[:24]
    start = "".join(f'<a class="chip" href="{t["url"]}">{e(t["title"])}</a>' for t in popular)
    body = f"""
<section class="hero">
  <h1>{e(SITE_TITLE)}</h1>
  <p class="lede">A cross-referenced reference to literary terms, authors, works, prizes and periods.</p>
  <form class="search big" action="{BASE}search/" role="search" autocomplete="off">
    <input type="search" name="q" placeholder="Try “sonnet” or “Beloved”" aria-label="Search" data-search>
    <div class="results" hidden data-results></div>
  </form>
</section>
<div class="stats">{counts}</div>
{section('Good places to start', f'<div class="chips">{start}</div>')}
"""
    write("index.html", page(SITE_TITLE, body, None, "A cross-referenced reference to literary terms, authors, works, prizes and periods.", ""))


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
        if key in NO_PAGES:
            continue
        for r in db[key].values():
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
            alt = r.get("alternate", "") if key == "authors" else ""
            entries.append([r["title"], singular, r["url"][len(BASE):], extra, alt])
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "search.json").write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def sitemap(db):
    write("robots.txt", "User-agent: *\nAllow: /\n" + (f"Sitemap: {SITE_URL}sitemap.xml\n" if SITE_URL else ""))
    if not SITE_URL:
        return
    urls = [SITE_URL] + [f"{SITE_URL}{k}/" for k, _, _ in SECTIONS]
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

    if not args.no_images:
        prepare_media(db)

    periods_by_term = defaultdict(list)
    for p in db["periods"].values():
        tid = resolver.find("terms", p["term_text"]) if p["term_text"] else None
        if tid:
            periods_by_term[tid].append(p["id"])

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

    alpha_index(db, "terms", "Terms", "Definitions are cross-linked: follow any term in small capitals.")
    alpha_index(db, "authors", "Authors", "Sorted by last name.")
    alpha_index(db, "works", "Works", "Sorted by title.")
    alpha_index(db, "poems", "Poems", "Poems and passages from the tests, with their full text.")
    tests_index(db, rel)
    reading_lists_index(db)
    prizes_index(db, rel)
    periods_index(db)
    tags_index(db, rel)
    resources_index(db, resolver)
    home(db, rel)
    search_page()
    search_index(db)
    sitemap(db)
    write("404.html", page("Page not found", f'<h1>Page not found</h1><p class="lede">That page may have been renamed. Try searching, or go <a href="{BASE}">home</a>.</p>'))

    n = sum(1 for _ in OUT.rglob("*.html"))
    print(f"Done: {n:,} pages in {OUT}/", flush=True)


if __name__ == "__main__":
    main()
