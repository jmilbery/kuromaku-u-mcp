# Kuromaku U — Catalog and Curriculum Design (v2)

_Written 2026-09-11. The spec for the v2 rebuild: what the catalog has to look like before a
transcript drawn from it can look real. `docs/DATA-AUDIT.md` says what was wrong; this says what
replaces it._

## Why the catalog is first

Everything else is drawn from this table. Enrollments, transcripts, GPA history and every roster
question in a demo resolve back to a course row. The v1 catalog can't support any of it:

- **Course numbers carry no meaning.** 25 of 38 department-and-level groups are numbered
  alphabetically by title, so the level a course landed in was arbitrary. *Amorphous Semiconductor
  Devices* and *Nuclear Core Design and Analysis I* sit at the 1000 level.
- **No foundation layer.** No Calculus II or III, no Differential Equations, Linear Algebra,
  Physics, General Chemistry, Writing, Economics or Ethics. "CORE" was 8 business courses.
- **Majors too thin to fill four years.** A degree is ~32 courses. Materials had 13 lectures,
  Chemical 18, Aeronautical 22 — so students repeat courses (1,847 repeated pairs in v1).
- **16 broken sequences** — a II with no I, or an I with no II.
- **Nothing to sequence *with*.** No prerequisites, no degree plans. The generator could only draw
  at random, which is why 45% of freshman enrollments were 3000- and 4000-level.

## The degree

Four courses a term, eight terms, 32 courses. Lectures are 4 units, labs 2, so a term is 14–16
units and a degree is ~120.

| Slots | Block | Where it comes from |
|---:|---|---|
| 8 | Math and science foundation | MATH, PHYS, CHMY |
| 5 | General education | HUMN, SOCS |
| 3 | Engineering common core | ENGR |
| 10 | Major requirements (includes 2 labs and the two-term senior capstone) | the major's own department |
| 6 | Major and technical electives, 3000–4000 level | the major's department, or an approved neighbour |
| **32** | | |

Terms 1–2 are mostly foundation and general education; terms 3–4 shift to the major's own
1000/2000-level sequence; terms 5–8 are upper-level major work, electives and the capstone.

## Departments

`department` becomes a real table, replacing the `COR` code that pointed at no row. `cd_major` and
`cd_minor` stay as they are — they describe students, not courses.

| Code | Prefix | Name | Kind | Majors? |
|---|---|---|---|---|
| AER | AERO | Aeronautical Engineering | engineering | yes |
| CHE | CHEM | Chemical Engineering | engineering | yes |
| CIV | CIVL | Civil Engineering | engineering | yes |
| COM | COMP | Computer Science | engineering | yes |
| ENG | EENG | Electrical Engineering | engineering | yes |
| MAN | MANU | Manufacturing | engineering | yes |
| MAT | MATL | Materials Science | engineering | yes |
| MEC | MECH | Mechanical Engineering | engineering | yes |
| NUC | NUCL | Nuclear Engineering | engineering | yes |
| MTH | MATH | Mathematics | foundation | no |
| PHY | PHYS | Physics | foundation | no |
| CHM | CHMY | Chemistry | foundation | no |
| EGR | ENGR | Engineering (common core) | foundation | no |
| HUM | HUMN | Humanities and Writing | general education | no |
| SOC | SOCS | Social Science and Business | general education | no |

Chemistry is `CHMY`, because `CHEM` already belongs to Chemical Engineering. The v1 `CORE-*`
courses move: Calculus and Probability to MATH, American History and English Literature to
HUMN, Accounting, Finance, Management and Business Law to SOCS.

## Numbering

`PREFIX-Lnnn`, where **L is the level and it means something**:

| Level | Year | What belongs there |
|---|---|---|
| 1000 | freshman | first exposure, no prerequisites beyond placement |
| 2000 | sophomore | the major's core sequence begins; foundation math/science is a prerequisite |
| 3000 | junior | depth, analysis and design; 2000-level prerequisites |
| 4000 | senior | specialization, special topics, research, capstone |

Rules:
- Numbered in **teaching order** within a level, in steps of 5 (`1005`, `1010`, …), so a course can
  be inserted later without renumbering its neighbours.
- A **lab takes the number immediately after its lecture** and carries the lecture's title plus
  "Laboratory".
- **I comes before II**, in the same department, never more than one level apart. A sequence is
  either completed (the missing half is written) or the numeral is dropped.
- **Cross-listed courses keep one title** and appear under each department's own prefix, naming
  each other in the description.
- Catnums are **not stable from v1**. They are regenerated, and enrollments are regenerated with
  them. `main` keeps the v1 numbering for the recorded episodes.

## Per-department targets

Each engineering department needs to cover its own 10 required slots and offer a real choice for
the 6 elective ones:

- **10 required**: an intro, a 2000-level core sequence, 3000-level depth, 2 labs, and
  Senior Design I and II.
- **10+ electives** at the 3000 and 4000 levels, so two students in the same major graduate with
  visibly different transcripts.
- Roughly **22–28 courses** per engineering department. Electrical (67) and Civil (42) already
  exceed this and keep their surplus as electives; Materials (17), Chemical (22) and Aeronautical
  (25) need courses written.

Foundation and general education, sized to serve every major:

| Dept | Courses | Covering |
|---|---|---|
| MATH | ~9 | Calculus I–III, Differential Equations, Linear Algebra, Discrete Mathematics, Probability and Statistics, Numerical Methods |
| PHYS | ~5 | Physics I–II with labs, Modern Physics |
| CHMY | ~4 | General Chemistry I–II with lab, Organic Chemistry |
| ENGR | ~5 | Introduction to Engineering, Computing for Engineers, Engineering Graphics, Statics, Engineering Ethics and Professional Practice |
| HUMN | ~8 | Composition, Technical Writing, Literature, History, Philosophy |
| SOCS | ~8 | Economics, Accounting, Finance, Management, Business Law, Policy |

Target catalog: **~400 courses**, up from 303.

## The three tables the catalog feeds

**`course_prerequisite`** — `(catnum, prereq_catnum, requirement)` where requirement is
`prereq` or `coreq`. A lab is a `coreq` of its lecture. This is what makes a transcript sequence
survive inspection.

**`program` / `program_requirement`** — the degree plan per major. Each row is either a specific
course or an elective rule (a pool: department, minimum level, how many), with the term it's
normally taken. The enrollment generator walks this instead of drawing at random.

**`instructor` / `course_offering`** — which courses actually ran in a given semester, who taught
each one, in which building and room, with a seat capacity. This is also what finally connects
`building` to a person: in v1 the buildings were an island, so no spatial question could ever
reach a student.

## History

The semester table runs Fall 2019 – Fall 2026, and all 15 semesters get real enrollments. That
needs alumni: class-year rows and students for the classes of **2020 through 2026**, marked
`is_alumni`, each cohort attending its own four years and then leaving. The current four classes
(2027–2030) stay as they are.

Consequences: the student table grows from 1,000 to roughly 2,700, and enrollments from 15,472 to
roughly 75,000. Course offerings are per semester, so a course that didn't exist in 2019 simply has
no offering that year.

## Stages

| Stage | What lands | Status |
|---|---|---|
| A | Departments and the rebuilt, renumbered catalog with the foundation layer | **done** — 318 courses, 15 departments, 351 prerequisite rows, 68 courses newly written |
| B | Prerequisites and degree plans | next |
| C | Instructors and course offerings | |
| D | Alumni cohorts, and the transcript generator that walks the degree plans | |

Each stage rebuilds `~/Kuromaku-U/db/kuromaku_u_v2.db` in place so it can be read in RazorSQL
between stages. The database stays out of the repo for now.

## Open

- Do courses enter and leave the catalog across the seven years, or is the catalog stable and only
  offerings vary? Stable is simpler and hides nothing a demo would ask.
- Part-time students, withdrawals, transfers and repeated failures: realism the generator could
  carry, deferred until the honest path works.
