# v2 data generators

These scripts produced the v2 CSVs in `data/`. They are kept so the data has a provenance, not as a
supported pipeline: they were written and run once, in order, during the v2 rebuild (2026-09-11/12),
and several read intermediate files from a scratch directory that no longer exists. Their paths are
hardcoded to that scratch directory and to the v2 worktree.

`schema/build_db.py` is the supported path: it builds the database from the CSVs, and generates
`student_enrollment` from them on every run.

| Order | Script | What it wrote |
|---|---|---|
| 1 | `fix_students.py` | Tier 1 student fixes: minors, grad_year, reserved emails and 555-01XX phones |
| 2 | `titles.py` + `apply_catalog.py` | Tier 1 course titles and the first real descriptions |
| 3 | `assemble_catalog.py` | Stage A: the renumbered 318-course catalog, departments, prerequisites. Reads the per-department plans that Claude sub-agents wrote (not kept) and `foundation.json` |
| 4 | `build_programs.py` | Stage B: `ku_program.csv`, `ku_program_requirement.csv`; prunes prerequisite edges no plan can satisfy |
| 5 | `build_alumni.py` | Stage D: alumni cohorts. Takes class years as arguments and skips any already present |
| 6 | `build_schedule.py` | Stage C: rooms, instructors, the timetable of offerings. Re-run after cohorts change |

`catalog_spec.json` carries each course's role (required, lab, capstone, elective) as the Stage A
writers assigned it. That role is not stored in any CSV; `build_programs.py` and `build_schedule.py`
read it from here.
