# Kuromaku U — history

Fictional engineering university as a real SQLite database, plus a deliberately minimal MCP server
over it. Repo `jmilbery/kuromaku-u-mcp`. Local: `/Users/jmilbery/Kuromaku-U`. The recurring demo
universe for the PE TechCast AI 'Splaining series.

**The server is thin on purpose.** See the closing note in `f895cfa` before "improving" the tool
surface.

---

## 2026-09-09 — The seed data had drifted six years; found by reading rows on camera

First entry — this file did not exist before today.

Rehearsing the 08c demo surfaced Heath Bracegirdle as `class_year 2024, "Freshman"` in a database
whose current semester was Spring 2026. Pulling that thread found three fields all encoding absolute
years against a demo that keeps being re-dated, and one logic bug underneath them.

- **`extend_semesters_to_present()`** appended semesters 11–14 in code on top of a CSV that ended at
  Spring 2024, and marked Spring 2026 current. Nothing moved `ku_class_year.csv` forward with it.
  The two also disagreed about the academic-year convention: the CSV's spring rows had
  `academic_year_start = academic_year_end`, the appended ones used `start = end-1`.
- **Nobody ever graduated.** `generate_enrollments` bounded attendance only from below
  (`ay_start >= class_year - 4`), so all 1,000 students attended all 13 semesters and 2021 graduates
  sat on current rosters. That is where 54,880 enrollments came from — the function's own docstring
  had estimated ~16,000 for years.
- **Date of birth** put every class in 1999–2003, with no gradient between freshmen and seniors. A
  Fall 2026 freshman born in 1999 is 27.

Fixed in the seed layer, not by patching the `.db`: `ku_semester.csv` now carries all 15 rows
through **Fall 2026** and `extend_semesters_to_present` is retired; class years are 2027/28/29/30
(Kuromaku U graduates in spring only, so a senior sitting in Fall 2026 finishes Spring 2027);
student class years shifted +6 and DOBs regenerated per cohort into clean 12-month windows;
attendance bounded to `class_year-4 .. class_year-1`. **15,472 enrollments**, matching the
docstring's long-standing estimate.

`sanity_check()` now runs at the end of every build and prints loudly when the current semester is
not the newest, a class matriculated outside 17–19, enrollments fall outside a student's own four
years, or the current semester is empty. Verified against both drift modes by replaying this exact
bug on a scratch copy. (1f85c2f)

Also relabelled `CHE` "CHEMISTRY" → **Chemical Engineering** and `ENG` "ENGINEERING" →
**Electrical Engineering**, in `cd_major` and `cd_minor` together — every course under them was
already chemical and electrical respectively, and ENG is the largest department in the school.
(f895cfa)

**Rejected: adding a `list_majors()` tool.** Answering "what majors do you offer?" currently costs a
303-row catalogue scrape plus probe calls to rule out `COR` and `UND`. Jim wants that on camera —
a thin server means the model can only compose what you gave it, and every gap becomes work it does
the long way round. That is the episode's actual argument. Do not add convenience tools here without
asking.

**Consequence accepted, not fixed:** Fall 2019 – Spring 2023 now hold zero enrollments, because the
oldest cohort is the class of 2027 who arrived in AY 2023-24. Eight semesters advertise history the
data no longer has. `class_year.is_alumni` exists and is 0 on all four rows, so adding alumni
cohorts would repopulate it.

Downstream corrections in the same pass: the 08c deck script, `diagrams/kuromaku-u-datamodel.html`
(`54,880 rows` → `15,472 rows`), `demo/demo-prompts.md` (COMP-1005 is 19 students now, not 13), and
the README build description.

---

## 2026-09-10 — A full-coverage server for the RAG episode, and the first full data audit

**`server/server_full.py`** — 21 tools, the MCP side of the MCP vs RAG comparison. It *imports* the
six tools from `server.py` rather than copying them, so it is a strict superset and the two cannot
drift. `server.py` is untouched: the 9/9 rejection of `list_majors()` stands for the minimal server;
the full server is the other end of the ladder (`server_minimal.py` 1 → `server.py` 6 →
`server_full.py` 21). Optional `run_sql` tool, off unless `KUROMAKU_U_ALLOW_SQL=1`. Reports the
orphaned `COR` department as `CORE CURRICULUM` without adding a 16th table (08c says fifteen).

**`docs/DATA-AUDIT.md`** — every column of all 15 tables, every FK, plausibility checks. Structure is
sound (one orphaned key); content is not: 303 Lorem Ipsum course descriptions, truncated registrar
titles that break keyword search (the README's own "machine learning" example returns nothing),
a loader bug nulling `cd_state.fips`, unused minors, empty `grad_year`, a 1-in-8 F rate. Fixes are
tiered by whether they move enrollment rows — Tier 1 doesn't, Tier 2 does and re-opens 08c.

**Correction from Jim on the audit's privacy framing:** every personal field is generator output
from the original build years ago. The emails sit on real domains but are not real accounts; the
phone numbers are generated. Moving them to `example.com` / `555-01XX` is a consistency fix in the
cleanup, not an emergency.

Committed as-is so the work can continue from the laptop. **This starts the cleanup project** —
making the dataset clean and consistent, with the audit as the work list.
