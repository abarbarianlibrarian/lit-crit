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
NO_PAGES = {"resources", "questions", "reading-lists"}

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
    ("tags", "Tags", "Tag"),
    ("resources", "Resources", "Resource"),
]

SITE_TITLE = os.environ.get("SITE_TITLE", "Literary Criticism")
GA_ID = os.environ.get("GA_ID", "G-CRQBFM26RK")  # Google Analytics measurement ID
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
    nav = f'<a href="{BASE}"{" aria-current=page" if active == "home" else ""}>Home</a>' + "".join(
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
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer = window.dataLayer || []; function gtag(){{dataLayer.push(arguments);}} gtag('js', new Date()); gtag('config', '{GA_ID}');</script>
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
<script src="{BASE}assets/quiz.js?v={BUILD_ID}" defer></script>
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
    ctx = (db, resolver, t["mentioned"] + t["related"], t["title"])
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


def questions_section(db, qids, title="Practice questions", limit=10):
    qids = [q for q in dict.fromkeys(qids) if db["questions"][q]["url"]]
    if not qids:
        return ""
    qids.sort(key=lambda q: (test_sort(db["tests"][db["questions"][q]["test"][0]]),
                             int(db["questions"][q]["number"] or 0)))
    items = "".join(question_html(db, db["questions"][q], in_test=False) for q in qids[:limit])
    more = ""
    if len(qids) > limit:
        more = (f'<details class="more more-q"><summary>{len(qids) - limit} more questions</summary>'
                f'<ol class="plain questions compact">'
                + "".join(question_html(db, db["questions"][q], in_test=False) for q in qids[limit:])
                + "</ol></details>")
    total = sum(question_points(db["questions"][q]) for q in qids)
    return section(title, f'<div class="quiz">{score_bar(total, len(qids), test=False)}'
                          f'<ol class="plain questions compact">{items}</ol>{more}</div>', len(qids))


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


def question_html(db, q, in_test=True, rel=None):
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
<h1>{e(t['title'])}</h1>
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
    write(f"{key}/index.html", page(label, body, key, lede, f"{key}/",
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
           "filters": [{"key": "tag", "label": "Tag", "all": "All tags"}],
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
<h1>{e(x['title'])}</h1>
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
    rows = []
    for p in db["periods"].values():
        years = " – ".join(x for x in (p["start"], p["end"]) if x)
        rows.append({"n": p["title"], "u": p["url"], "s": years, "m": p["region"],
                     "f": {"region": [p["region"]] if p["region"] else [], "type": [p["type"]] if p["type"] else []},
                     "k": {"start": years_of(p["start"]), "region": p["region"], "name": sort_key(p["title"])},
                     "x": fold(f'{p["title"]} {p["description"]}')})
    rows.sort(key=lambda r: (r["k"]["region"], r["k"]["start"] or 0))
    cfg = {"placeholder": "Period name or description",
           "filters": [{"key": "region", "label": "Region", "all": "All regions"},
                       {"key": "type", "label": "Kind", "all": "All kinds"}],
           "range": {"key": "start", "label": "Began"},
           "sorts": [{"label": "By region, in order", "keys": ["region", "start"]},
                     {"label": "Chronological", "keys": ["start", "name"]}, {"label": "A–Z", "key": "name"}]}
    catalog_page("periods", "Periods", "Literary periods by region.", rows, cfg)


def tags_index(db, rel):
    rows = []
    for g in db["tags"].values():
        n = len(rel[("tags", g["id"])].get("terms", []))
        sets = [name for name, url in (("Quizlet", g["quizlet"]), ("Gimkit", g["gimkit"]),
                                       ("Blooket", g["blooket"]), ("Sporcle", g["sporcle"])) if url]
        rows.append({"n": g["title"], "u": g["url"], "s": " · ".join(sets), "m": f"{n} terms",
                     "f": {"set": sets}, "k": {"name": sort_key(g["title"]), "n": n}, "x": fold(g["title"])})
    rows.sort(key=lambda r: r["k"]["name"])
    cfg = {"placeholder": "Tag name",
           "filters": [{"key": "set", "label": "Study set", "all": "Any or none"}],
           "sorts": [{"label": "A–Z", "key": "name"}, {"label": "Most terms", "keys": ["-n", "name"]},
                     {"label": "Fewest terms", "keys": ["n", "name"]}]}
    catalog_page("tags", "Tags", "Terms grouped by topic, with study sets.", rows, cfg)


def resources_index(db, resolver):
    rows = []
    for r in db["resources"].values():
        work = ", ".join(r["work"]) or "General"
        wid = resolver.find("works", work)
        title = f"{work}: {r['title']}"
        rows.append({"n": title, "u": r["link"] if re.match(r"^https?://", r["link"] or "") else "", "ext": True,
                     "s": "", "m": " · ".join(x for x in (r["type"], r["year"]) if x),
                     "f": {"type": [r["type"]] if r["type"] else [], "year": [r["year"]] if r["year"] else [],
                           "work": r["work"] or ["General"]},
                     "k": {"work": sort_key(work), "name": sort_key(r["title"]), "year": r["year"]},
                     "x": fold(f"{work} {r['title']} {r['type']}")})
    rows.sort(key=lambda x: (x["k"]["work"], x["k"]["name"]))
    cfg = {"placeholder": "Work or resource",
           "filters": [{"key": "work", "label": "Work", "all": "All works"},
                       {"key": "type", "label": "Type", "all": "All types"},
                       {"key": "year", "label": "School year", "all": "All years", "order": "desc"}],
           "sorts": [{"label": "By work", "keys": ["work", "name"]}, {"label": "Newest school year", "keys": ["-year", "work"]}]}
    catalog_page("resources", "Reading resources", "Texts, audio and study materials for the reading list works.", rows, cfg)


def daily_term_html(db, resolver, tm):
    paras = [x for x in (tm["definition"] or "").strip().split("\n\n") if x.strip()]
    first = paras[0] if paras else ""
    if first.rstrip().endswith(":") and len(paras) > 1:  # keep the example the paragraph introduces
        first += "\n\n" + paras[1]
    ctx = (db, resolver, tm["mentioned"] + tm["related"], tm["title"])
    return f"""<article class="daily-card">
  <p class="daily-label">Term of the day</p>
  <h2 class="daily-title"><a href="{tm['url']}">{e(tm['title'])}</a></h2>
  {f'<p class="lede">{e(tm["short"])}</p>' if tm['short'] else ''}
  <div class="prose daily-def">{md_to_html(first, ctx)}</div>
  <p><a class="more-link" href="{tm['url']}">Read the full entry →</a></p>
</article>"""


def daily_author_html(db, rel, a):
    img = a.get("image") or (a["picture_url"] if re.match(r"^https?://", a["picture_url"]) else None)
    portrait = (f'<img class="portrait" src="{e(img, quote=True)}" alt="Portrait of {e(a["title"], quote=True)}" '
                f'loading="lazy" onerror="this.remove()">') if img else ""
    years = " – ".join(x for x in (a["birth"], a["death"]) if x)
    about = ", ".join(x for x in (a["nationality"], ", ".join(a["medium"]).lower()) if x)
    works = rel[("authors", a["id"])].get("works", [])
    works.sort(key=lambda w: (not db["works"][w]["notable"], db["works"][w]["year_written"] or "9999"))
    shown = "".join(f'<li><a href="{db["works"][w]["url"]}">{work_title_html(db["works"][w])}</a></li>' for w in works[:5])
    return f"""<article class="daily-card daily-author">
  <p class="daily-label">Author of the day</p>
  <div class="daily-author-body">
    {portrait}
    <div>
      <h2 class="daily-title"><a href="{a['url']}">{e(a['title'])}</a></h2>
      {f'<p class="lede">{e(years)}</p>' if years else ''}
      {f'<p class="daily-about">{e(about[:1].upper() + about[1:])}</p>' if about else ''}
      {f'<ul class="plain daily-works">{shown}</ul>' if shown else ''}
      <p><a class="more-link" href="{a['url']}">More about {e(a['title'])} →</a></p>
    </div>
  </div>
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
        cards = (daily_term_html(db, resolver, tm) if tm else "") + (daily_author_html(db, rel, au) if au else "")
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


def home(db, rel, resolver):
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
{daily_section(db, rel, resolver)}
<div class="stats">{counts}</div>
{section('Good places to start', f'<div class="chips">{start}</div>')}
"""
    write("index.html", page(SITE_TITLE, body, "home", "A cross-referenced reference to literary terms, authors, works, prizes and periods.", ""))


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
    home(db, rel, resolver)
    search_page()
    search_index(db)
    sitemap(db)
    write("404.html", page("Page not found", f'<h1>Page not found</h1><p class="lede">That page may have been renamed. Try searching, or go <a href="{BASE}">home</a>.</p>'))

    n = sum(1 for _ in OUT.rglob("*.html"))
    print(f"Done: {n:,} pages in {OUT}/", flush=True)


if __name__ == "__main__":
    main()
