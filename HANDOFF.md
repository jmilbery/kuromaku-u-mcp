# Kuromaku U — Handoff
_Written 2026-09-09_

## Where I stopped

The seed data is re-dated to a **Fall 2026** present and the database is rebuilt and current:
1,000 students, 303 courses, **15,472 enrollments**, classes of 2027–2030, ages 18–22. `main` is
clean and pushed through `f895cfa`. `sanity_check()` runs at the end of every build and reports
"all clear".

The 08c demo was re-verified against the rebuilt data and still works: Bracegirdle resolves, and
the fluid-mechanics question still forces the same three-call chain — he is now in **MECH-2040
Biofluid Mechanics, 11 students, four departments**.

## What's next

1. **Reconnect RazorSQL before recording.** `build_db.py` deletes and recreates the `.db`, so any
   open connection is on the old inode and will show the pre-fix 54,880.
2. **Decide about the eight empty semesters.** Fall 2019 – Spring 2023 have no enrollments now.
   Either add alumni cohorts (`is_alumni` is already in the schema, 0 on all four rows) or shorten
   the semester table. Not blocking the episode.
3. **Nothing else.** The server is where it should be — see below before changing that.

## What I'd have to re-derive

- **The server is deliberately minimal.** There is no `list_majors()` tool, so "what majors do you
  offer?" makes the model scrape all 303 courses and infer departments. That is the TechCast
  demonstration, not a defect. Do not add convenience tools without asking.
- **Three fields encode absolute years** — `class_year`, `semester`, `dob` — and they have now
  drifted twice. `sanity_check()` is the guard; if it complains, believe it. It catches a stale
  `is_current`, a class matriculating outside 17–19, ghost enrollments, and an empty current term.
- **Attendance is `class_year - 4 <= ay_start <= class_year - 1`.** The upper bound is the whole
  point: without it nobody graduates. It only works because the spring rows' `academic_year_start`
  is the *prior* year — the CSV had that wrong for 2020–2024 and it was masked by the missing bound.
- **`ku_semester.csv` is the source of truth again.** Recent semesters used to be appended in code
  by `extend_semesters_to_present()`, which disagreed with the CSV about the AY convention. That
  function is gone; add new semesters to the CSV.
- **Kuromaku U graduates in spring only.** A senior sitting in Fall 2026 finishes Spring 2027 — that
  is why the classes are 2027/28/29/30 and not 2026/27/28/29.
- **`%y` in `_norm_date` pivots 00–68 to the 2000s**, so the CSV's `m/d/yy` DOB format still works
  for 2004–2008 birth years.
- **The `.db` is gitignored** — it is a build artifact. `python3 schema/build_db.py` regenerates it
  deterministically from `data/*.csv` at seed 1729.

## Open questions

- Do the eight empty semesters get alumni cohorts, or does the semester table get shorter?
- `grad_year` is an empty column on every student row; `class_year` does that job. Drop it or fill
  it?
