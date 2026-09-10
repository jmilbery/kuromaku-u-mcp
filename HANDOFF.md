# Kuromaku U — Handoff
_Written 2026-09-10_

## Where I stopped

Two new files are committed and pushed: **`server/server_full.py`** (21 tools, the MCP side of the
MCP vs RAG episode) and **`docs/DATA-AUDIT.md`** (first full audit of all 15 tables). The database
is unchanged since 9/9: 1,000 students, 303 courses, **15,472 enrollments**, Fall 2026 current,
`sanity_check()` all clear.

**The next phase is a cleanup project:** make the data clean and consistent. `docs/DATA-AUDIT.md`
is the work list.

## What's next

1. **Tier 1 of `docs/DATA-AUDIT.md`** — nine fixes, none move an enrollment row. After rebuild:
   15,472 enrollments, Bracegirdle resolves, MECH-2040 Fall 2026 = 11 students, four depts.
2. **Doc drift, same pass.** README (15 semesters, 304 lines, add `server_full.py`, fix the
   "machine learning" example) and `demo/demo-prompts.md` (pre-re-date numbers).
3. **Tier 2 waits until 08c records** — it moves rows and re-opens the Bracegirdle question.
   Reconnect RazorSQL after every rebuild.

## What I'd have to re-derive

- **Row order of `ku_student.csv` and `ku_course_catalog.csv` is load-bearing.**
  `generate_enrollments()` walks both without an `ORDER BY`; reordering either reshuffles every
  enrollment. It reads only `student_id`, `cd_major`, `class_year`, `catnum`, `cd_major_minor`,
  `active_flag` — edit anything else freely, never reorder.
- **Keep `MECH-2040 Biofluid Mechanics` verbatim** when expanding titles — the 08c script names it.
- **RazorSQL goes stale on rebuild.** `build_db.py` deletes and recreates the `.db`; an open
  connection stays on the old inode and shows old numbers.
- **The personal data is all synthetic** — generator output from the original build. Real-looking
  domains and area codes, no real people. The email/phone fix is consistency, not privacy.
- **Two servers, two jobs.** `server.py` is deliberately minimal — no `list_majors()`, so "what
  majors do you offer?" makes the model scrape the catalog. That is the TechCast demonstration; do
  not add convenience tools to it without asking. `server_full.py` imports those six and adds 15;
  that is where coverage belongs.
- **Three fields encode absolute years** — `class_year`, `semester`, `dob` — and have drifted
  twice. `sanity_check()` is the guard; if it complains, believe it.
- **Attendance is `class_year - 4 <= ay_start <= class_year - 1`.** Works only because spring rows'
  `academic_year_start` is the *prior* year.
- **`ku_semester.csv` is the source of truth.** Add new semesters to the CSV, not in code.
- **Kuromaku U graduates in spring only** — a Fall 2026 senior finishes Spring 2027, hence classes
  2027–2030.
- **The `.db` is gitignored** — `python3 schema/build_db.py` regenerates it deterministically from
  `data/*.csv` at seed 1729.

## Open questions

- Eight empty semesters: alumni cohorts, or a shorter semester table?
- Real course descriptions — hand-written, or generated from title/department/type/units?
