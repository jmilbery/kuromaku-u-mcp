# Kuromaku U — Handoff
_Written 2026-09-15_

## Where I stopped

All three MCP servers now open `kuromaku_u.db` read-only (`mode=ro`): `server.py` in `e59367b`,
`server_minimal.py` in `561fb6a` (edited in place, still 42 lines, so it matches the Part 2 code
slide). The README has a "Which server?" section; the closeout commit corrects its tool count for
`server_full.py` (21, not 16). `main` is clean and pushed. The database is unchanged since 9/9.

## What's next

1. **Don't rebuild the DB until 08c records.** Its script now shows the majors mismatch below on
   camera. Recording is tracked in the spiel HANDOFF.
2. **Tier 1 of `docs/DATA-AUDIT.md`**, after 08c records. If it touches `COR` or `UND`, 08c's
   majors check changes — re-run the query below.
3. **Rest of the doc drift:** README still says 10 semesters and has the "machine learning" catalog
   example; `demo/demo-prompts.md` carries pre-re-date numbers.

## What I'd have to re-derive

- **08c's majors check depends on a data quirk.** `cd_major` has 10 rows. The course catalog has 10
  `cd_major_minor` codes, but one is `COR` (core courses, not a major) and `UND` (Undeclared) has no
  courses. Students hold 9 distinct majors. So Claude, which has no `list_majors` in `server.py`,
  gets it wrong whichever route it takes. Check with:
  `select distinct cd_major_minor from course_catalog where cd_major_minor not in (select cd_major from cd_major)`.
- **Three servers, three jobs** (replaces the 9/10 "two servers" note):
  - `server_minimal.py` — 1 tool, Part 2's "30 lines" slide. Don't grow it.
  - `server.py` — 6 tools, thin on purpose, the Part 3 demo. No convenience tools without asking.
  - `server_full.py` — the six imported plus 15 = **21**; `run_sql` only with `KUROMAKU_U_ALLOW_SQL=1`.
- **`grep -c '@mcp.tool' server_full.py` says 16 and is wrong.** It misses the six registered in a
  loop via `mcp.tool()(_tool)`. That miscount shipped in the README for one commit.
- **Read-only is enforced at the connection:** `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`.
  `server_full.py`'s typed tools use `server.py`'s `_conn()`, so they inherited it; `run_sql` has its
  own read-only connection plus the `_deny_attach` authorizer.
- **Claude picks up server changes only on restart.** Claude Code's config runs
  `~/kuromaku-u/.venv/bin/python ~/kuromaku-u/server/server.py` — same directory as `~/Kuromaku-U`
  (case-insensitive filesystem).
- **`MECH-2040 Biofluid Mechanics` no longer has to stay verbatim for 08c** — the fluid-mechanics
  question was cut from the script. Check `demo/demo-prompts.md` before renaming it.
- **Row order of `ku_student.csv` and `ku_course_catalog.csv` is load-bearing.**
  `generate_enrollments()` walks both without an `ORDER BY`; reordering either reshuffles every
  enrollment. It reads only `student_id`, `cd_major`, `class_year`, `catnum`, `cd_major_minor`,
  `active_flag` — edit anything else freely, never reorder.
- **RazorSQL goes stale on rebuild.** `build_db.py` deletes and recreates the `.db`; an open
  connection stays on the old inode and shows old numbers.
- **The personal data is all synthetic** — generator output from the original build. The
  email/phone fix is consistency, not privacy.
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
