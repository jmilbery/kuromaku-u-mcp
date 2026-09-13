"""Tier 1 #1-2: apply expanded titles + real descriptions to the catalog.

Writes data/ku_course_catalog.csv (BOM, CRLF, no trailing newline, row order
kept) and swaps the same two fields in schema/postgres/ku_course_catalog.sql.
Refuses to write anything if a check fails.
"""
import csv, io, json, re, sys
from pathlib import Path

S = Path(__file__).resolve().parent
REPO = Path("/Users/jmilbery/Kuromaku-U/.claude/worktrees/v2")
CSV_PATH = REPO / "data/ku_course_catalog.csv"
SQL_PATH = REPO / "schema/postgres/ku_course_catalog.sql"
sys.path.insert(0, str(S))
from titles import TITLES

desc: dict[str, str] = {}
for b in range(1, 7):
    part = json.loads((S / f"desc_b{b}.json").read_text())
    assert not (set(part) & set(desc)), f"overlap in b{b}"
    desc.update({k: " ".join(v.split()) for k, v in part.items()})

xl = json.loads((S / "xlists.json").read_text())
for c, primary in xl["secondary"].items():
    assert c not in desc, f"{c} should have been copied, not written"
    desc[c] = desc[primary]

# Lab -> lecture pairing comes from the ORIGINAL titles (same department, same
# old title), because several lectures were renamed away from their lab's name.
orig = {r["catnum"]: r for r in csv.DictReader(open(CSV_PATH, encoding="utf-8-sig"))}
companion = {}
for c, r in orig.items():
    if r["course_type"] == "LAB":
        lec = sorted(x for x, o in orig.items() if o["course_type"] == "LEC"
                     and o["major_minor_code"] == r["major_minor_code"]
                     and o["course_title"] == r["course_title"])
        if lec:
            companion[c] = lec[0]
xl_of = {c: [x for x in g if x != c] for g in xl["groups"] for c in g}

CODES = r"[A-Z]{4}-\d{4}(?:,? (?:and )?[A-Z]{4}-\d{4})*"
TAILS = re.compile(rf"\s*(?:Laboratory companion to|Cross-listed with) {CODES}\.")
for c in desc:
    d = TAILS.sub("", desc[c]).strip()
    if c in companion:
        d += f" Laboratory companion to {companion[c]}."
    if c in xl_of:
        d += f" Cross-listed with {', '.join(xl_of[c])}."
    desc[c] = d

# ---- checks -----------------------------------------------------------------
problems = []
assert set(desc) == set(TITLES), set(TITLES) ^ set(desc)
for c, d in desc.items():
    if not (200 <= len(d) <= 700):
        problems.append(f"{c}: length {len(d)}")
    if any(ch in d for ch in '";') or not d.isascii():
        problems.append(f"{c}: punctuation")
    if re.search(r"lorem|ipsum|kuromaku", d, re.I):
        problems.append(f"{c}: forbidden word")
labs_unpaired = sorted(c for c, r in orig.items() if r["course_type"] == "LAB" and c not in companion)
print(f"labs paired {len(companion)} · unpaired {labs_unpaired or 'none'}")
# no sentence shared between courses, except cross-list copies and boilerplate tails
xl_sets = [set(g) for g in xl["groups"]]
seen: dict[str, str] = {}
for c, d in sorted(desc.items()):
    for sent in re.split(r"(?<=\.)\s+", d):
        if sent.startswith(("Laboratory companion to", "Cross-listed with")):
            continue
        prev = seen.get(sent)
        if prev and not any({prev, c} <= g for g in xl_sets):
            problems.append(f"{c} repeats a sentence from {prev}: {sent[:60]}")
        seen.setdefault(sent, c)
if problems:
    print("\n".join(problems))
    sys.exit(f"{len(problems)} problem(s) — nothing written")

# ---- CSV --------------------------------------------------------------------
raw = CSV_PATH.read_bytes()
assert raw.startswith(b"\xef\xbb\xbf")
text = raw[3:].decode("utf-8")
rows = list(csv.reader(io.StringIO(text, newline="")))
header, body = rows[0], rows[1:]
it, idesc = header.index("course_title"), header.index("course_desc")
for r in body:
    r[it], r[idesc] = TITLES[r[0]], desc[r[0]]
out = io.StringIO(newline="")
csv.writer(out, lineterminator="\r\n").writerows([header] + body)
new = out.getvalue()
if not text.endswith("\n"):
    new = new[:-2]
CSV_PATH.write_bytes(b"\xef\xbb\xbf" + new.encode("utf-8"))

# ---- Postgres INSERTs ---------------------------------------------------------
q = lambda s: "'" + s.replace("'", "''") + "'"
LIT = r"'(?:[^']|'')*'"
pat = re.compile(rf"VALUES \('([A-Z]{{4}}-\d{{4}})', ({LIT}), {LIT}, {LIT}, ")
sql = SQL_PATH.read_text(encoding="utf-8")
hits = 0
def swap(m):
    global hits
    hits += 1
    c = m.group(1)
    return f"VALUES ('{c}', {m.group(2)}, {q(TITLES[c])}, {q(desc[c])}, "
sql = pat.sub(swap, sql)
assert hits == 303, hits
SQL_PATH.write_text(sql, encoding="utf-8")

lens = sorted(len(d) for d in desc.values())
print(f"applied 303 titles + descriptions · desc length {lens[0]}–{lens[-1]} (median {lens[151]}) · postgres rows {hits}")
