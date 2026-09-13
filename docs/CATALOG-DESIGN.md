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

Stage B built the plans and, in doing so, found prerequisite edges no four-year plan could satisfy.
**Eleven were dropped**, each logged:

- **Ten cases of a required course depending on an elective** (AERO-4005 on AERO-3025, MATL-3010 on
  MATL-3025 and MATL-3040, NUCL-3015 on NUCL-3025, and so on). If the spine needs it, it isn't an
  elective — and no plan can promise a pool course.
- **`CHEM-3015` Reactor Engineering waiting on `CHEM-3005` Unit Operations II**, which made
  Chemical's spine five deep and pushed the capstone past graduation. It keeps Thermodynamics, the
  prerequisite that matters, and Senior Design keeps Reactor Engineering.
- Plus one first-year edge: Engineering Graphics no longer waits on Introduction to Engineering,
  since Manufacturing needs graphics in term 1.

Each major's plan is checked: 4 slots a term, and no named course scheduled before anything it
depends on. Elective pools run from 13 courses (Chemical) to 51 (Electrical) for 6 slots, so two
students in a major graduate with different transcripts.

**`room`, `instructor`, `course_offering`** — Stage C, and the point where the buildings stop
being an island. In v1 nothing linked a course or a person to a place, so no spatial question could
ever reach a student.

- **`room`** — 125 rooms in the 14 buildings that teach: lecture halls, classrooms, teaching labs,
  computer labs, seminar rooms and two auditoriums, each with a capacity.
- **`instructor`** — 184 faculty across all 15 departments, with rank (professor through adjunct),
  an office in their department's building, and a teaching load that depends on rank. **Hire and
  departure years run across the window**: 26 arrive after 2019 and 37 leave before 2026, so the
  faculty of 2019 is visibly not the faculty of 2026. The base faculty of each department is sized
  to its busiest term and stays for the whole window, so no term is ever short-staffed.
- **`course_offering`** — 3,562 sections across the 15 semesters, about 237 a term. Each carries a
  section number, an instructor, a room, a seat capacity, and a meeting pattern: MWF 50-minute
  slots, TR 75-minute slots, three-hour lab blocks, and evening slots for independent study.

**Rotation.** The spine runs every term: foundation courses, and each major's required courses and
labs. Senior Design I is a fall course and Senior Design II a spring one. Mid-level electives run
once a year, a quarter of the senior electives every other year, and an elective with fewer than
five likely takers does not run at all.

**What the timetable guarantees.** No room is double-booked, no instructor is double-booked, no
section exceeds its room's capacity, no one teaches outside their own department, and nobody
teaches in a year they were not employed. All five are checked after every build. Together with
`building_distance` this makes walk-time answerable: an instructor with ten minutes to get from
Kuromaku Hall to the Hollister Building has 498 metres to cover.

## History

The semester table runs **Fall 2016 – Fall 2026, 21 semesters**, and every one has four cohorts in
residence. That takes fourteen graduating classes: the four still enrolled (2027–2030) and ten of
alumni (2017–2026), 250 to a class, about 3,500 students in all.

**Every class from 2020 on has a complete four-year record.** The first cut of Stage D started the
record in Fall 2019, which left the class of 2020 with only a senior year on file — the same hole
the audit found, one level down. Extending the semester table back three years closed it for 2020,
2021 and 2022. The classes of 2017, 2018 and 2019 now sit at that boundary instead, with two,
four and six terms on record: the years of a registrar system that did not migrate older coursework,
and far enough back that no demo reaches them. Their earlier coursework counts as completed for
prerequisite purposes, so their recorded terms are still coherent.

## How students register (Stage D)

`student_enrollment` is generated on every build by `build_db.py`, and each row now names the
section (`offering_id`) as well as the course and semester.

**Semester by semester, seniors first, in three passes.** Each term, everyone in residence registers:
first for the courses their plan names (plus anything carried over), then for their elective slots,
then for any course they are eligible for if a slot is still empty. Within a pass, seniors go before
juniors, and a course with one section is placed before a course with six. Every pick is a section
that ran that term, had a seat, and did not collide with the rest of the student's week.

That ordering is the result of three failed first attempts, each of which looked fine until measured:
registering one student through all eight terms before the next (whoever had the lowest ID took
seats everywhere, and later classes came up 30% short); a single pass per student (a senior's filler
course took the Calculus I seat a freshman needed, and everything behind it slipped); and a Stage C
bug that read `FALL 2019` as a spring term, so first-term courses were sized for nobody.

**What it models.** A failed course is retaken — the only repeat that exists. A course that is full,
clashes or is not offered slips to a later term. A student who still owes a required course after
eight terms, usually a Senior Design that slipped behind its prerequisites, gets up to two more.
Each student's outcome is derived from their own transcript into `student.degree_status`
(`enrolled`, `graduated`, `graduated late`, `did not complete`) and `graduated_semester_id`;
`class_year` and `grad_year` stay as when they were expected to finish.

| Measure | v1 | v2 |
|---|---|---|
| Freshman enrollments at the 3000/4000 level | 45% | 0% — year one is all level 1; year four is 79% level 3–4 |
| Retakes of a course already passed | 1,875 | 0 — all 2,454 repeats follow an F |
| Students who ever took a core course | 12.1% | 99.6% |
| Semesters with no enrollments | 8 of 15 | 0 of 21 |
| Student-terms carrying a full four courses | — | 94% |
| On-time graduation, full-record classes | — | 61–78%, with 25–35% graduating late and 2–5% not completing |

Checked after every build, all zero: prerequisite violations, labs taken without their lecture,
retakes of passed courses, students double-booked, sections over capacity, enrollments that disagree
with their section, grades on in-progress courses, and graduates missing a required course.

## Stages

| Stage | What lands | Status |
|---|---|---|
| A | Departments and the rebuilt, renumbered catalog with the foundation layer | **done** — 318 courses, 15 departments, 351 prerequisite rows, 68 courses newly written |
| B | Prerequisites and degree plans | **done** — 9 programs, 288 requirement rows, 118–122 units each |
| C | Instructors and course offerings | **done** — 125 rooms, 184 instructors, 3,562 offerings, no clashes |
| D | Alumni cohorts, and the transcript generator that walks the degree plans | **done** — 3,500 students, 83,029 enrollments, every integrity check zero |

Each stage rebuilds `~/Kuromaku-U/db/kuromaku_u_v2.db` in place so it can be read in RazorSQL
between stages. The database stays out of the repo for now.

## Open

- Do courses enter and leave the catalog across the seven years, or is the catalog stable and only
  offerings vary? Stable is simpler and hides nothing a demo would ask.
- Part-time students, withdrawals, transfers and repeated failures: realism the generator could
  carry, deferred until the honest path works.
