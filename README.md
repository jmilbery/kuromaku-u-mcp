# Kuromaku University

A sample relational dataset and reference MCP server for the **PE TechCast — AI 'Splaining** series.

Kuromaku U is a fictional engineering university with 1,000 students, 318 courses across 15 departments, 48 buildings, four class years, fifteen semesters, and a fully-articulated code-table hierarchy (majors, minors, ethnicities, countries, states, grades). Everything in this repo is synthetic — no real students, no real data — which makes it safe to ship, clone, fork, and demo against.

This repo is the **recurring demo universe** for every episode of the AI series. Today it backs the MCP Part 2 episode; over the rest of the series it will support Fine-Tuning, AI Agents, Context Engineering, Multimodal, Reasoning Models, and beyond.

> **Versions.** `main` is the dataset the episodes so far were recorded against, and it stays that way so those demos keep reproducing. This `v2` branch is a progressive rebuild of the data with better values — real course titles and descriptions, realistic grades and enrollments, no real-looking personal data. Numbers here will not match earlier episodes. `docs/DATA-AUDIT.md` is the work list.

---

## What's in here

```
kuromaku-u/
├── README.md                       ← you are here
├── LICENSE                         ← MIT
├── pyproject.toml                  ← Python deps (just `mcp`)
├── data/                           ← 21 CSVs — the canonical source of truth
│   ├── ku_student.csv              ← 1,000 students with names, majors, photos
│   ├── ku_course_catalog.csv       ← 318 courses, numbered by level (1000–4000)
│   ├── ku_department.csv           ← 15 departments — 9 that grant majors, 6 foundation/gen-ed
│   ├── ku_course_prerequisite.csv  ← what comes before what (prereq / coreq)
│   ├── ku_program.csv              ← the 9 degrees, with total units
│   ├── ku_program_requirement.csv  ← each degree as 32 slots: 4 a term, 8 terms
│   ├── ku_room.csv                 ← 125 rooms in the 14 buildings that teach
│   ├── ku_instructor.csv           ← 184 faculty, with rank, office and hire/departure years
│   ├── ku_course_offering.csv      ← 3,562 sections: who teaches what, where, when
│   ├── ku_building.csv             ← 48 campus buildings
│   ├── ku_building_distance.csv    ← pairwise building distances in meters
│   ├── ku_semester.csv             ← 15 semesters (Fall 2019 – Fall 2026)
│   ├── ku_student_address.csv      ← student home addresses
│   ├── ku_class_year.csv           ← FR/SO/JR/SR class years
│   ├── ku_cd_major.csv             ← 10 engineering majors (AER, COM, MEC, …)
│   ├── ku_cd_minor.csv             ← available minors
│   ├── ku_cd_ethnicity.csv         ← ethnicity codes
│   ├── ku_cd_state.csv             ← all 50 US states + federal regions
│   ├── ku_cd_country.csv           ← ISO country codes
│   ├── ku_cd_grade.csv             ← letter grade ↔ numeric grade map
│   └── ku_cd_building_type.csv     ← dormitory / academic / library / etc.
├── schema/
│   ├── sqlite_init.sql             ← SQLite DDL (what the demo runs against)
│   ├── build_db.py                 ← Builds kuromaku_u.db from the CSVs
│   └── postgres/                   ← Original Postgres DDL (preserved for "advanced mode")
├── server/
│   ├── server_minimal.py           ← One tool — the "look how simple this is" server
│   ├── server.py                   ← Reference MCP server — 6 tools, ~40 lines of business logic
│   └── server_full.py              ← Full-coverage server — 21 tools, every table reachable
├── demo/                           ← Demo prompts, Claude Code config, screen-capture list
├── artwork/
│   ├── studentid.png               ← Kuromaku U student ID design
│   └── kuromaku-logo.png
├── docs/
│   ├── Kuromaku-U.pdf              ← Physical ER diagram
│   └── DATA-AUDIT.md               ← Column-by-column audit of the dataset, and what was fixed
└── episodes/                       ← Per-episode demo code lands here as we ship them
```

---

## Quick start — clone to demo in 4 commands

```bash
git clone https://github.com/jmilbery/kuromaku-u-mcp.git
cd kuromaku-u-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e . && python schema/build_db.py
```

That builds `kuromaku_u.db` (a single SQLite file, ~1.8 MB) with the 22 source tables — `ku_semester.csv` now carries the full timeline through Fall 2026 itself, rather than having recent semesters appended in code — and a deterministically-generated `student_enrollment` table (seed `1729`, 15,472 rows).

To run the MCP server:

```bash
python server/server.py
```

It speaks stdio MCP transport — wire it up to any MCP client.

> **macOS note:** modern Python on macOS is "externally managed" (PEP 668). Always use a venv. The `python3 -m venv .venv` step above creates one inside the repo; activate it before any `pip install` or you'll hit `error: externally-managed-environment`.

---

## Wiring it up to Claude Code (macOS)

Claude Code does **not** read `mcpServers` from `settings.json` (that's a Claude Desktop convention — see the section below). Use one of these instead.

**Option A — the `claude mcp add` CLI (simplest):**

```bash
claude mcp add kuromaku-u --scope user -- /absolute/path/to/.venv/bin/python /absolute/path/to/server/server.py
```

**Option B — a project `.mcp.json`** in your working directory:

```json
{
  "mcpServers": {
    "kuromaku-u": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/server/server.py"]
    }
  }
}
```

Either way, point `command` at the venv's Python (`.venv/bin/python`) so the `mcp` dependency resolves. Restart Claude Code and verify with `/mcp` — you should see `kuromaku-u` and its six tools listed.

Then ask Claude Code things like:

> "Who's taking COMP-2010 this semester, and what are their majors?"
> "Find me all students named Smith in the Mechanical Engineering program."
> "What's the full record for student 1042?"
> "Search the catalog for any course with 'machine learning' in the title."

Claude will call the tools, join the results across `course_roster` → `student_detail` as needed, and answer.

---

## Wiring it up to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (create it if missing):

```json
{
  "mcpServers": {
    "kuromaku-u": {
      "command": "python",
      "args": ["/absolute/path/to/kuromaku-u/server/server.py"]
    }
  }
}
```

Restart Claude Desktop. The tools show up under the 🔌 icon in the input bar.

---

## Tools exposed by the server

| Tool | What it does |
|---|---|
| `find_students(name, major, class_year, limit)` | Search the directory. Filters compose. |
| `student_detail(student_id)` | Full record for one student, with all lookups joined (major name, minor name, class year name, ethnicity name, primary address). |
| `student_courses(student_id, semester_id?)` | Courses a student is taking/took in a semester. Defaults to the current semester. Includes letter grade for past semesters. |
| `course_roster(catnum, semester_id?)` | Every student enrolled in a course in a given semester. |
| `search_catalog(keyword, department, limit)` | Search the course catalog by title keyword or department code. |
| `current_semester()` | Returns the row where `is_current = 1`. Useful before drilling into other tools. |

The whole server is ~300 lines of Python. The actual tool implementations are SQL queries. That's the punchline of the demo: MCP servers are not magic. They are functions plus JSON.

`server.py` is deliberately thin — there is no `list_majors()`, so "what majors do you offer?" makes the model scrape the catalog the long way round. That gap is the lesson; don't paper over it.

### The full-coverage server

`server/server_full.py` is the other end of the ladder: the same six tools, imported rather than copied, plus fifteen more so every table is reachable — transcripts, course detail and history, addresses and location search, semesters, majors and minors, code tables, buildings and distances, and aggregate counts and GPA stats. It is the MCP side of the MCP vs RAG episode.

```bash
claude mcp add kuromaku-u-full --scope user -- /absolute/path/to/.venv/bin/python /absolute/path/to/server/server_full.py
```

An optional read-only `run_sql` tool is off by default; set `KUROMAKU_U_ALLOW_SQL=1` to register it. It buys total coverage by giving up every guardrail the typed tools provide — it's there for the comparison, not as a recommendation.

---

## "Advanced mode" — running against Postgres

The original schema was authored in Postgres. The full DDL and data-load scripts live in `schema/postgres/`. If you'd rather run the demo against Postgres than SQLite, you can use that directory as a starting point — but the MCP server in this repo speaks SQLite. Adapting it to Postgres is a 10-line swap (`sqlite3` → `psycopg`) we may ship as an alternate `server/server_postgres.py` in a future commit.

---

## Why "Kuromaku U"?

"Kuromaku" — 黒幕 — is the Japanese term for the unseen power behind the scenes, the wire-puller. Jim Milbery uses the name as a recurring brand across a novel project and a small constellation of software experiments. Kuromaku U is the fictional engineering school we send our characters to when we need a realistic dataset and don't feel like inventing yet another one.

---

## License

MIT. Use it for whatever — explainer videos, course demos, MCP server tutorials, sample data for prototypes, conference talks, your own podcast. If you do something fun with it, drop a note: [jim@parkergale.com](mailto:jim@parkergale.com).
