# Kuromaku U — Data Audit
_Run 2026-09-10 against the Fall 2026 build (seed 1729): every column of all 15 tables, every
foreign key, and a set of plausibility checks. First full pass the dataset has had._

> **Status on `v2` (2026-09-11).** This audit is now the work list for the v2 rebuild, not a
> list of fixes that must spare the 08c demo. `main` keeps the audited data unchanged for the
> episodes already recorded. On v2 the 08c invariants are lifted: enrollments may move, and
> Tier 2 no longer waits.
>
> | Tier 1 | Status |
> |---|---|
> | 1 descriptions · 2 titles | Done. 303 written descriptions (346–585 chars), full titles; cross-lists kept and tagged, all 53 labs name their lecture, no lecture titled "Lab", no in-department duplicate titles. `search_catalog("machine learning")` now returns COMP-2005 and COMP-2040 |
> | 3 FIPS · 4 minors · 5 grad_year · 6 emails · 7 phones · 8 grades | Done: `f2442f1`. Enrollments byte-identical to the audited build |
> | 9 `COR` orphan | Fixed properly: `department` is a real table of 15, and the CORE courses moved to MATH, HUMN and SOCS. Zero orphaned keys |
>
> Stage A of `docs/CATALOG-DESIGN.md` then replaced the catalog outright: levels now mean
> something, the foundation layer exists, and Tier 2's "no level progression" finding is answered
> at the catalog end. The enrollment end waits for Stage D.

## So what

The **structure is sound**: no orphaned keys (bar one, below), no ghost enrollments, one current
semester, and building distances that are complete and symmetric. The **content is not**. Every
course description is Lorem Ipsum, the course titles are registrar abbreviations that break keyword
search, two columns load as empty because of a loader bug, and nearly every personal email and
cell number in a public repo looks real.

That matters more for the MCP vs RAG episode than for anything shipped so far. An MCP tool routes
around a bad title using the course code. A RAG index embeds whatever text it's given, so it would
have embedded 303 paragraphs of Latin without complaint.

Fixes fall into three tiers by what they disturb. **Tier 1 moves no enrollment rows**, so every
number in the 08c script holds. Tier 2 changes who took what, which means re-verifying the 08c demo.

---

## Tier 1 — safe: no enrollment row moves

| # | Field | Evidence | Fix |
|---|---|---|---|
| 1 | `course_catalog.course_desc` | **303 of 303 are Lorem Ipsum** (307–1,022 chars each) | Write real descriptions from title, department, type, units |
| 2 | `course_catalog.course_title` | Truncated registrar abbreviations: `Intr Aero Eng Sys`, `Foundatns Comp Sci`, `Intro to Ants` (antennas), `MarStructureConst`. 10 have doubled spaces (`Des  and  Mfg I`). The README's own example — *"any course with 'machine learning' in the title"* — **returns nothing**, because the title is `Intro Machine Learn`. 13 lectures are titled "Lab"; two pairs of lectures share a title (MANU-3005/3010, MECH-1005/1010) | Expand to full titles. **Keep `MECH-2040 Biofluid Mechanics` verbatim** — the 08c script names it. Keep the 15 cross-listed titles as cross-lists |
| 3 | `cd_state.fips` | **Null on all 51 rows — a loader bug.** The CSV column is `fips_state`; `build_db.py` reads `fips` and gets nothing | One line in `CSV_HEADER_ALIASES` |
| 4 | `student.cd_minor` | **All 1,000 students are `UND`**; the other 9 minors are never used | Give ~30% of students a minor (never their own major), in the CSV |
| 5 | `student.grad_year` | Null on all 1,000. `server.py` selects it, so it can't simply be dropped | Fill from `class_year` — Kuromaku graduates in the spring of the class year |
| 6 | `student.email` | **996 of 1,000 sit on 424 real third-party domains** (wired.com, ft.com, unesco.org, yandex.ru…). Some of those local parts could be real inboxes | Move to RFC 2606 reserved domains (`example.com/.net/.org`), keep the local parts |
| 7 | `student.cell_phone` | **996 of 1,000 are plausible real numbers**: real area codes, only 4 use 555 | Move to the fictional `555-01XX` range, keep the area codes |
| 8 | Grades (generated) | A 25.2% · B 25.0% · C 24.7% · **D 12.7% · F 12.3%**, GPA 2.38. The generator's comment says *"F is rare"*; the pool `[A,B,C,A,B,C,D,F]` makes it 1 in 8 | Draw grades from a second RNG, weighted (≈ A 35 / B 38 / C 18 / D 5 / F 4 → GPA ≈ 3.0). The main stream still consumes one draw per graded row, so **course selection stays byte-identical** |
| 9 | `course_catalog.cd_major_minor = 'COR'` | 8 CORE courses carry a department code with no `cd_major` row — the only orphaned key in the database | **Done** in `server_full.py` (reports `CORE CURRICULUM`). No schema change: a departments table would make it 16 tables, and 08c says fifteen |

**Invariant for every Tier 1 fix:** keep the row order of `ku_student.csv` and
`ku_course_catalog.csv`. `generate_enrollments()` walks both without an `ORDER BY`, so reordering
either file reshuffles every enrollment. It reads only `student_id`, `cd_major`, `class_year`,
`catnum`, `cd_major_minor` and `active_flag` — none of the fields above — which is why they're safe.

After the rebuild, re-check: 15,472 enrollments; Bracegirdle resolves; MECH-2040 in Fall 2026 has
11 students across four departments.

## Tier 2 — enrollment realism: moves rows, re-verify 08c

The total holds at 15,472 because every fix keeps four courses per student per term. But
Bracegirdle's schedule changes, so the 08c question *"what class is Bracegirdle taking in fluid
mechanics?"* has to be found again, and the script's numbers re-verified.

| # | Problem | Evidence |
|---|---|---|
| 10 | Retakes | 1,847 student–course pairs repeat; 1,875 are retakes of a course already passed with C or better |
| 11 | No level progression | 45% of freshman enrollments (503 of 1,120) are 3000/4000-level; seniors hold 1,848 1000-level enrollments |
| 12 | Labs without lectures | 2,388 of 2,516 lab enrollments have no matching lecture that term |
| 13 | Core isn't core | Only 12.1% of students have ever taken a CORE course |
| 14 | Empty history | Fall 2019 – Spring 2023 hold no enrollments; `is_alumni` is 0 on all 4 class-year rows. Already an open question in HANDOFF |

~~**Recommendation: after 08c records.**~~ **Unblocked on v2.** The 08c demo stays on `main`, so
nothing here has to preserve its numbers.

> **Status on `v2`: all five resolved** by the catalog rebuild (`docs/CATALOG-DESIGN.md`, Stages A–D).
> Retakes of passed courses: 0 (every repeat follows an F). Level progression: year-one enrollments
> are 100% level 1. Labs without lectures: 0. Core coverage: 99.6% of students. Empty history: every
> one of 21 semesters, Fall 2016 – Fall 2026, has four classes in residence.

## Tier 3 — leave alone

- **Student names** are Mockaroo-flavored (first names `Muffin`, `Hill`, `Mead`). Changing them breaks 08c.
- **250 international students across 224 countries**, one to four per country. Unrealistic spread, harmless.
- **Distances are straight-line**: the ratio to centroid distance is exactly 1.000. Correct as data; the `server_full.py` docstring now says so.
- **Unused lookup values** (`UNK` ethnicity, the `Buildings and Grounds` type, `UND` major) are normal for code tables.
- **Semester dates before Fall 2024 are templated** (09-01 → 12-15, 01-15 → 05-31).
- **Unloaded CSV audit columns** (`create_date`, `optimistic_lock`, …) are empty or constant.
- **`UNDECLARED` (major) vs `UNDECIDED` (minor)**: cosmetic.
- **Buildings are an island**: nothing links courses to rooms or students to dorms, so a spatial question can never reach a person. A schema limit, not a bug, and worth knowing before anyone asks one on camera.

## Clean

Zero orphans on 14 of 15 foreign keys · no graded current-semester rows, no ungraded past rows ·
exactly one active address per student · every US address has a state and a 5-digit ZIP, no
non-US address carries either · 2,256 distance pairs = 48 × 47, all symmetric · every class's DOB
window matches its class year · one current semester, and it's the newest.

## Doc drift (fix with the README update for `server_full.py`)

- README: "ten semesters" (15), "~250 lines" (304), lists only the six-tool server.
- `demo/demo-prompts.md`: Bracegirdle as class of 2024 and COMP-1005 at 19 students, both from before the re-date.
