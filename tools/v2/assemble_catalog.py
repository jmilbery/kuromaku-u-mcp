"""Stage A assembly: nine department plans + the foundation layer -> the v2 catalog.

Assigns catnums from each department's teaching order, resolves prerequisites by
title, re-appends the lab and cross-list sentences, validates, then writes
data/ku_department.csv (already written), ku_course_catalog.csv and
ku_course_prerequisite.csv. Writes nothing if a check fails.
"""
import csv, json, re, sys
from collections import defaultdict
from pathlib import Path

S = Path(__file__).resolve().parent
A = S / "stageA"
REPO = Path("/Users/jmilbery/Kuromaku-U/.claude/worktrees/v2")
DEPTS = ["AER", "CHE", "CIV", "COM", "ENG", "MAN", "MAT", "MEC", "NUC"]
PREFIX = {r["cd_department"]: r["catnum_prefix"]
          for r in csv.DictReader(open(REPO / "data/ku_department.csv", encoding="utf-8-sig"))}
FOUND_DEPT = {"MATH": "MTH", "PHYS": "PHY", "CHMY": "CHM", "ENGR": "EGR", "HUMN": "HUM", "SOCS": "SOC"}
CODES = r"[A-Z]{4}-\d{4}(?:,? (?:and )?[A-Z]{4}-\d{4})*"
TAILS = re.compile(rf"\s*(?:Laboratory companion to|Cross-listed with) {CODES}\.")

problems: list[str] = []
courses: list[dict] = []        # final rows, in catalog order
prereq_pairs: list[tuple] = []  # (catnum, prereq_catnum, requirement)

# ---- foundation: catnums are fixed in foundation.json --------------------------
foundation = json.loads((S / "foundation.json").read_text())
fdesc = json.loads((A / "out_foundation.json").read_text())
if set(fdesc) != {f["catnum"] for f in foundation}:
    problems.append(f"foundation descriptions: {set(fdesc) ^ {f['catnum'] for f in foundation}}")
for f in foundation:
    entry = fdesc.get(f["catnum"], {})
    courses.append({
        "catnum": f["catnum"], "dept": f["dept"], "title": f["title"], "type": f["type"],
        "units": f["units"], "level": int(f["catnum"][5]), "role": "foundation",
        "desc": entry.get("description", ""), "source": f.get("reuse") or "new",
    })
    for p in entry.get("prerequisites", []):
        prereq_pairs.append((f["catnum"], p, "prereq"))

# ---- engineering departments: catnums assigned from teaching order ------------
title_to_catnum = defaultdict(dict)   # dept -> lowercase title -> catnum
spec = {}
for d in DEPTS:
    # Electrical was too big for one writer (67 courses blew the output cap), so it
    # comes back in three files: the required spine, then two elective halves.
    paths = [A / f"out_{d}.json"] if (A / f"out_{d}.json").exists() else sorted(A.glob(f"out_{d}_*.json"))
    if not paths:
        sys.exit(f"missing plan for {d}")
    plan = {"courses": [], "dropped": [], "notes": ""}
    for i, p in enumerate(paths):
        part = json.loads(p.read_text())
        for c in part["courses"]:
            c["_batch"] = i
        plan["courses"] += part["courses"]
        plan["dropped"] += part.get("dropped", [])
    ROLE_ORDER = {"required": 0, "lab": 0, "capstone": 0, "elective": 1}
    plan["courses"].sort(key=lambda c: (int(c["level"]), ROLE_ORDER.get(c["role"], 1), c.get("_batch", 0)))
    spec[d] = plan
    seq = defaultdict(int)
    for c in plan["courses"]:
        lvl = int(c["level"])
        seq[lvl] += 5
        if seq[lvl] > 995:
            problems.append(f"{d} level {lvl}: more than 199 courses")
        catnum = f"{PREFIX[d]}-{lvl}{seq[lvl]:03d}"
        t = c["title"].strip()
        if t.lower() in title_to_catnum[d]:
            problems.append(f"{d}: duplicate title {t}")
        title_to_catnum[d][t.lower()] = catnum
        courses.append({
            "catnum": catnum, "dept": d, "title": t, "type": c["type"], "units": int(c["units"]),
            "level": lvl, "role": c["role"], "desc": " ".join(c["description"].split()),
            "source": c.get("source", "new"), "companion": c.get("companion_lecture_title"),
            "prereqs": c.get("prerequisites") or [], "xl_hint": c.get("cross_listed_with"),
        })
    roles = defaultdict(int)
    for c in plan["courses"]:
        roles[c["role"]] += 1
    if roles["required"] + roles["lab"] + roles["capstone"] != 10:
        problems.append(f"{d}: required core is {roles['required']}+{roles['lab']}+{roles['capstone']}, want 10")
    if roles["elective"] < 10:
        problems.append(f"{d}: only {roles['elective']} electives")

by_catnum = {c["catnum"]: c for c in courses}
for c in courses:
    if c["dept"] in FOUND_DEPT.values():
        title_to_catnum[c["dept"]][c["title"].lower()] = c["catnum"]
found_titles = {c["title"].lower(): c["catnum"] for c in courses if c["role"] == "foundation"}

# ---- labs: companion lecture, as a coreq -------------------------------------
for c in courses:
    if c["type"] != "LAB":
        continue
    want = (c.get("companion") or re.sub(r"\s+Laboratory$", "", c["title"])).lower()
    lec = title_to_catnum[c["dept"]].get(want)
    if not lec or by_catnum[lec]["type"] != "LEC":
        problems.append(f"{c['catnum']} {c['title']}: no companion lecture for {want!r}")
        continue
    c["companion_catnum"] = lec
    prereq_pairs.append((c["catnum"], lec, "coreq"))

# ---- cross-lists: same title in more than one department ---------------------
by_title = defaultdict(list)
for c in courses:
    by_title[c["title"].lower()].append(c)
xlists = {t: [x["catnum"] for x in cs] for t, cs in by_title.items()
          if len({x["dept"] for x in cs}) > 1 and len({x["type"] for x in cs}) == 1}
for t, cs in by_title.items():
    same = [x for x in cs if x["dept"] == cs[0]["dept"]]
    if len(same) > 1:
        problems.append(f"duplicate title within {cs[0]['dept']}: {t}")

# One course in two departments is one course: it gets one description, taken from
# the department that had it in v1. A title that collides without having been
# cross-listed in v1 is reported rather than merged silently.
new_collisions = []
for t, catnums in xlists.items():
    members = [by_catnum[c] for c in catnums]
    if not any(m.get("xl_hint") for m in members):
        new_collisions.append((t, [m["catnum"] for m in members]))
    members.sort(key=lambda m: (m.get("source", "new") == "new", m["catnum"]))
    canon = TAILS.sub("", members[0]["desc"]).strip()
    for m in members[1:]:
        m["desc"] = canon
if new_collisions:
    print("title collisions that were NOT cross-listed in v1 (merged into one course):")
    for t, cs in new_collisions:
        print(f"  {t}: {cs}")

# ---- prerequisites by title --------------------------------------------------
for c in courses:
    for p in c.get("prereqs", []):
        p = p.strip()
        if re.fullmatch(r"[A-Z]{4}-\d{4}", p):
            target = p if p in by_catnum else None
        else:
            target = title_to_catnum[c["dept"]].get(p.lower()) or found_titles.get(p.lower())
        if not target:
            problems.append(f"{c['catnum']} {c['title']}: unresolved prerequisite {p!r}")
            continue
        if target == c["catnum"]:
            problems.append(f"{c['catnum']}: prerequisite of itself")
            continue
        if by_catnum[target]["level"] > c["level"]:
            problems.append(f"{c['catnum']} (L{c['level']}) requires {target} (L{by_catnum[target]['level']})")
        prereq_pairs.append((c["catnum"], target, "prereq"))

# ---- description tails, then checks -----------------------------------------
for c in courses:
    d = TAILS.sub("", c["desc"]).strip()
    if c.get("companion_catnum"):
        d += f" Laboratory companion to {c['companion_catnum']}."
    others = [x for x in xlists.get(c["title"].lower(), []) if x != c["catnum"]]
    if others:
        d += f" Cross-listed with {', '.join(others)}."
    c["desc"] = d
    if not (200 <= len(d) <= 800):
        problems.append(f"{c['catnum']}: description length {len(d)}")
    if any(ch in d for ch in '";') or not d.isascii():
        problems.append(f"{c['catnum']}: description punctuation")
    if re.search(r"lorem|ipsum|kuromaku", d, re.I):
        problems.append(f"{c['catnum']}: forbidden word in description")

seen = defaultdict(list)
for c in courses:
    for sent in re.split(r"(?<=\.)\s+", c["desc"]):
        if sent.startswith(("Laboratory companion to", "Cross-listed with")):
            continue
        seen[sent].append(c["catnum"])
for sent, cs in seen.items():
    if len(cs) > 1 and not any(set(cs) <= set(v) for v in xlists.values()):
        problems.append(f"sentence shared by {cs}: {sent[:60]}")

if problems:
    print(f"{len(problems)} problem(s) — nothing written:")
    print("\n".join(f"  {p}" for p in sorted(set(problems))[:60]))
    sys.exit(1)

# ---- write -------------------------------------------------------------------
CAT = REPO / "data/ku_course_catalog.csv"
hdr = ["catnum", "major_minor_code", "course_title", "course_desc", "course_type", "units",
       "course_level", "active_flag", "create_date", "last_update_date", "updated_by_user_id",
       "optimistic_lock", "locked_by_user_id"]
with open(CAT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(hdr)
    for c in courses:
        w.writerow([c["catnum"], c["dept"], c["title"], c["desc"], c["type"], c["units"],
                    c["level"], "t", "", "", "", "", ""])

PRE = REPO / "data/ku_course_prerequisite.csv"
# One row per pair: a lab naming its own lecture arrives twice, once as the
# coreq from the pairing and once as a prereq from the writer's list. Coreq wins.
merged: dict[tuple, str] = {}
for a, b, r in prereq_pairs:
    if merged.get((a, b)) != "coreq":
        merged[(a, b)] = r
uniq = sorted((a, b, r) for (a, b), r in merged.items())
with open(PRE, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["catnum", "prereq_catnum", "requirement"])
    w.writerows(uniq)

# Stage B needs the roles and the old->new mapping; keep them out of the repo for now.
json.dump({c["catnum"]: {k: c[k] for k in ("dept", "title", "type", "units", "level", "role", "source")}
           for c in courses}, open(S / "catalog_spec.json", "w"), indent=1)
json.dump({c["source"]: c["catnum"] for c in courses if re.fullmatch(r"[A-Z]{4}-\d{4}", c.get("source") or "")},
          open(S / "catnum_map.json", "w"), indent=1)

lv = defaultdict(int)
for c in courses:
    lv[c["level"]] += 1
print(f"courses {len(courses)} · prerequisites {len(uniq)} · cross-listed titles {len(xlists)}")
print("by level:", dict(sorted(lv.items())))
print("by dept:", {d: sum(1 for c in courses if c['dept'] == d) for d in PREFIX})
print("new courses written:", sum(1 for c in courses if c["source"] == "new"))
