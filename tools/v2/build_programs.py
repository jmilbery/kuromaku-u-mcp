"""Stage B: the degree plan for each of the nine majors.

32 slots, 4 a term, 8 terms. Named courses for the foundation, engineering core
and the major's own required spine; pools for the electives.

Two kinds of prerequisite edge get dropped, both logged:
  - a required course depending on an elective (that makes the elective required)
  - an edge that makes a department's required chain too deep to finish in four
    years, which usually means the writer chained two courses that real programs
    teach side by side
"""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

S = Path(__file__).resolve().parent
REPO = Path("/Users/jmilbery/Kuromaku-U/.claude/worktrees/v2")
cat = {r["catnum"]: r for r in csv.DictReader(open(REPO / "data/ku_course_catalog.csv", encoding="utf-8-sig"))}
spec = json.loads((S / "catalog_spec.json").read_text())
majors = {r["cd_major"]: r["name_major"] for r in csv.DictReader(open(REPO / "data/ku_cd_major.csv", encoding="utf-8-sig"))
          if r["cd_major"] != "UND"}
PRE_CSV = REPO / "data/ku_course_prerequisite.csv"
all_pre = [dict(r) for r in csv.DictReader(open(PRE_CSV, encoding="utf-8-sig"))]

# Graphics is a standalone first-year course; making it wait on Introduction to
# Engineering puts both in term 1 for Manufacturing, which needs graphics early.
# Reactor Engineering waiting on Unit Operations II makes Chemical's spine five
# deep and pushes it past the capstone. It keeps Thermodynamics, which is the
# prerequisite that matters, and the capstone keeps Reactor Engineering.
HAND_DROPPED = {("ENGR-1015", "ENGR-1005"), ("CHEM-3015", "CHEM-3005")}
CORE_ROLES = ("required", "lab", "capstone")
pruned = [r for r in all_pre if (r["catnum"], r["prereq_catnum"]) in HAND_DROPPED] + \
         [r for r in all_pre if (r["catnum"], r["prereq_catnum"]) not in HAND_DROPPED
          if spec.get(r["catnum"], {}).get("role") in CORE_ROLES
          and spec.get(r["prereq_catnum"], {}).get("role") == "elective"
          and spec[r["catnum"]]["dept"] == spec[r["prereq_catnum"]]["dept"]]
kept = [r for r in all_pre if r not in pruned]
prereqs = defaultdict(list)
for r in kept:
    prereqs[r["catnum"]].append((r["prereq_catnum"], r["requirement"]))
relaxed = []

GENED, MAJEL = 4, 6          # elective slots per degree
SCIENCE = "math and science"
CORE = "engineering core"
GE = "general education"

def standard(found_a, found_b, third=("ENGR-2005", 3)):
    """The usual layout: intro and composition first, physics and math early,
    the third engineering-core course in term 3 unless the major needs it later."""
    return [("ENGR-1005", 1, CORE), ("MATH-1005", 1, SCIENCE), ("CHMY-1005", 1, SCIENCE),
            ("HUMN-1005", 1, GE),
            ("ENGR-1010", 2, CORE), ("MATH-1010", 2, SCIENCE), ("PHYS-1005", 2, SCIENCE),
            ("PHYS-1010", 2, SCIENCE),
            ("PHYS-1015", 3, SCIENCE), (found_a, 3, SCIENCE), (found_b, 4, SCIENCE),
            (third[0], third[1], CORE)]

FIXED = {
    "AER": standard("MATH-2015", "MATH-2005"),
    "CIV": standard("MATH-2015", "MATH-3005"),
    "MAT": standard("CHMY-1015", "PHYS-2005"),
    "MEC": standard("MATH-2015", "MATH-2005"),
    "NUC": standard("MATH-2015", "PHYS-2005"),
    # Neither needs statics; ethics is a level-3 course, so it sits in term 7.
    "COM": standard("MATH-2020", "MATH-3005", third=("ENGR-3005", 7)),
    "ENG": standard("MATH-2015", "MATH-2005", third=("ENGR-3005", 7)),
    # Manufacturing's Design and Manufacturing I needs graphics from the start,
    # so graphics moves to term 1 and chemistry slides to term 3.
    "MAN": [("ENGR-1005", 1, CORE), ("MATH-1005", 1, SCIENCE), ("ENGR-1015", 1, CORE),
            ("HUMN-1005", 1, GE),
            ("ENGR-1010", 2, CORE), ("MATH-1010", 2, SCIENCE), ("PHYS-1005", 2, SCIENCE),
            ("PHYS-1010", 2, SCIENCE),
            ("PHYS-1015", 3, SCIENCE), ("CHMY-1005", 3, SCIENCE), ("MATH-3005", 3, SCIENCE),
            ("MATH-2015", 4, SCIENCE)],
    # Chemical's spine is the deepest in the school, so its chemistry and
    # differential equations have to clear early.
    "CHE": [("ENGR-1005", 1, CORE), ("MATH-1005", 1, SCIENCE), ("CHMY-1005", 1, SCIENCE),
            ("HUMN-1005", 1, GE),
            ("ENGR-1010", 2, CORE), ("MATH-1010", 2, SCIENCE), ("PHYS-1005", 2, SCIENCE),
            ("CHMY-1015", 2, SCIENCE),
            ("PHYS-1015", 3, SCIENCE), ("PHYS-1010", 3, SCIENCE), ("MATH-2015", 3, SCIENCE),
            ("ENGR-3005", 7, CORE)],
}


def unmet(c, term, plan, left):
    """Prerequisite edges of c that this term placement would violate."""
    bad = []
    for p, kind in prereqs.get(c, []):
        if p in left:
            bad.append((p, kind))
        elif p in plan and (plan[p] > term or (plan[p] == term and kind != "coreq")):
            bad.append((p, kind))
    return bad


def plan_major(m):
    problems, slots, plan = [], [], {}
    dept = [c for c, v in spec.items() if v["dept"] == m]
    required = [c for c in dept if spec[c]["role"] in ("required", "lab")]
    capstone = sorted(c for c in dept if spec[c]["role"] == "capstone")
    if len(required) != 8 or len(capstone) != 2:
        return [f"{m}: {len(required)} required + {len(capstone)} capstone, want 8 + 2"], []

    used = defaultdict(int)
    for catnum, term, block in FIXED[m]:
        slots.append((term, block, "COURSE", catnum, None, None))
        plan[catnum] = term
        used[term] += 1
    for catnum, term in zip(capstone, (7, 8)):
        slots.append((term, "major", "COURSE", catnum, None, None))
        plan[catnum] = term
        used[term] += 1

    # Capstone prerequisites first, then by chain depth: the courses other
    # courses wait on get the early terms.
    cap_needs, frontier = set(), [p for c in capstone for p, _ in prereqs.get(c, [])]
    while frontier:
        c = frontier.pop()
        if c in required and c not in cap_needs:
            cap_needs.add(c)
            frontier += [p for p, _ in prereqs.get(c, [])]

    left = set(required)
    for term in range(3, 8):
        while used[term] < 4 and left:
            ready = [c for c in left if not unmet(c, term, plan, left)]
            if not ready:
                break
            pick = min(ready, key=lambda x: (x not in cap_needs, int(cat[x]["course_level"]), x))
            slots.append((term, "major", "COURSE", pick, None, None))
            plan[pick] = term
            used[term] += 1
            left.discard(pick)
    # Anything still unplaced could not fit behind its own prerequisites. Drop the
    # edge that blocks it (recorded), and place it in the earliest free term.
    for c in sorted(left):
        for term in range(3, 8):
            if used[term] < 4:
                for p, kind in unmet(c, term, plan, left - {c}):
                    relaxed.append({"catnum": c, "prereq_catnum": p, "requirement": kind, "major": m})
                    prereqs[c] = [(q, k) for q, k in prereqs[c] if q != p]
                slots.append((term, "major", "COURSE", c, None, None))
                plan[c] = term
                used[term] += 1
                break
        else:
            problems.append(f"{m}: nowhere to put {c}")
    # A capstone prerequisite sharing the capstone's term is the same problem.
    for cap in capstone:
        for p, kind in list(prereqs.get(cap, [])):
            if p in plan and plan[p] >= plan[cap]:
                relaxed.append({"catnum": cap, "prereq_catnum": p, "requirement": kind, "major": m})
                prereqs[cap] = [(q, k) for q, k in prereqs[cap] if q != p]

    # Free slots: general education first, the major's own electives later, since
    # they are level 3 and up.
    free = sorted(t for t in range(1, 9) for _ in range(4 - used[t]))
    if len(free) != GENED + MAJEL:
        problems.append(f"{m}: {len(free)} free slots, want {GENED + MAJEL}")
    for i, term in enumerate(free):
        if i < GENED:
            slots.append((term, GE, "ELECTIVE", None, "gened", 1))
        else:
            slots.append((term, "major elective", "ELECTIVE", None, "major_elective", 3))

    per_term = defaultdict(int)
    for s in slots:
        per_term[s[0]] += 1
    for term in range(1, 9):
        if per_term[term] != 4:
            problems.append(f"{m}: term {term} has {per_term[term]} slots")
    for catnum, term in plan.items():
        for p, kind in prereqs.get(catnum, []):
            if p not in plan:
                problems.append(f"{m}: {catnum} (term {term}) needs {p}, not in the plan")
            elif plan[p] > term or (plan[p] == term and kind != "coreq"):
                problems.append(f"{m}: {catnum} in term {term} but {p} ({kind}) in term {plan[p]}")
    return problems, slots


problems, rows, unit_totals = [], [], {}
for m in sorted(majors):
    probs, slots = plan_major(m)
    problems += probs
    per_term = defaultdict(list)
    for s in slots:
        per_term[s[0]].append(s)
    units = 0
    for term in range(1, 9):
        ordered = sorted(per_term[term], key=lambda s: (s[2] == "ELECTIVE", s[3] or ""))
        for i, s in enumerate(ordered, start=1):
            u = int(cat[s[3]]["units"]) if s[3] else 4
            units += u
            rows.append([m, term, i, s[2], s[1], s[3] or "", s[4] or "", s[5] or "", u])
    unit_totals[m] = units

if problems:
    print(f"{len(problems)} problem(s) — nothing written:")
    print("\n".join(f"  {p}" for p in problems[:40]))
    sys.exit(1)

drop = {(r["catnum"], r["prereq_catnum"]) for r in pruned} | {(r["catnum"], r["prereq_catnum"]) for r in relaxed}
with open(PRE_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["catnum", "prereq_catnum", "requirement"])
    w.writerows([[r["catnum"], r["prereq_catnum"], r["requirement"]] for r in all_pre
                 if (r["catnum"], r["prereq_catnum"]) not in drop])

with open(REPO / "data/ku_program.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["cd_major", "degree_name", "total_units", "terms"])
    for m, name in sorted(majors.items()):
        w.writerow([m, f"Bachelor of Science in {name.title()}", unit_totals[m], 8])

with open(REPO / "data/ku_program_requirement.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["cd_major", "term", "slot", "requirement_type", "requirement_block",
                "catnum", "pool_kind", "pool_min_level", "units"])
    w.writerows(rows)

print(f"dropped {len(pruned)} edges where a required course depended on an elective:")
for r in pruned:
    print(f"  {r['catnum']} no longer requires {r['prereq_catnum']}")
print(f"relaxed {len(relaxed)} edges that made a chain too deep for four years:")
for r in relaxed:
    print(f"  [{r['major']}] {r['catnum']} no longer requires {r['prereq_catnum']}")
print(f"programs {len(majors)} · requirement rows {len(rows)} · units {sorted(set(unit_totals.values()))}")
