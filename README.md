# Kuromaku University

A sample relational dataset and reference MCP server for the **PE TechCast — AI 'Splaining** series.

Kuromaku U is a fictional engineering university with 1,000 students, 303 courses, 48 buildings, four class years, ten semesters, and a fully-articulated code-table hierarchy (majors, minors, ethnicities, countries, states, grades). Everything in this repo is synthetic — no real students, no real data — which makes it safe to ship, clone, fork, and demo against.

This repo is the **recurring demo universe** for every episode of the AI series. Today it backs the MCP Part 2 episode; over the rest of the series it will support Fine-Tuning, AI Agents, Context Engineering, Multimodal, Reasoning Models, and beyond.

---

## What's in here

```
kuromaku-u/
├── README.md                       ← you are here
├── LICENSE                         ← MIT
├── pyproject.toml                  ← Python deps (just `mcp`)
├── data/                           ← 14 CSVs — the canonical source of truth
│   ├── ku_student.csv              ← 1,000 students with names, majors, photos
│   ├── ku_course_catalog.csv       ← 303 courses across 10 majors
│   ├── ku_building.csv             ← 48 campus buildings
│   ├── ku_building_distance.csv    ← pairwise building distances in meters
│   ├── ku_semester.csv             ← 10 semesters (Fall 2019 onward)
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
│   └── server.py                   ← Reference MCP server — 6 tools, ~40 lines of business logic
├── artwork/
│   ├── studentid.png               ← Kuromaku U student ID design
│   └── kuromaku-logo.png
├── docs/
│   └── Kuromaku-U.pdf              ← Physical ER diagram
└── episodes/                       ← Per-episode demo code lands here as we ship them
```

---

## Quick start — clone to demo in 4 commands

```bash
git clone https://github.com/jmilbery/kuromaku-u.git
cd kuromaku-u
python3 -m venv .venv && source .venv/bin/activate
pip install -e . && python schema/build_db.py
```

That builds `kuromaku_u.db` (a single SQLite file, ~4 MB) with the 14 source tables, 4 appended "current" semesters that extend the timeline through Spring 2026, and a deterministically-generated `student_enrollment` table (seed `1729`, ~55,000 rows).

To run the MCP server:

```bash
python server/server.py
```

It speaks stdio MCP transport — wire it up to any MCP client.

> **macOS note:** modern Python on macOS is "externally managed" (PEP 668). Always use a venv. The `python3 -m venv .venv` step above creates one inside the repo; activate it before any `pip install` or you'll hit `error: externally-managed-environment`.

---

## Wiring it up to Claude Code (macOS)

Add the server to your Claude Code MCP config. Claude Code reads MCP server definitions from your project's `.claude/settings.json` (or your global `~/.claude/settings.json`). Add a `mcpServers` block:

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

Restart Claude Code. Verify the server is connected with `/mcp` — you should see `kuromaku-u` and its six tools listed.

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

The whole server is ~250 lines of Python. The actual tool implementations are SQL queries. That's the punchline of the demo: MCP servers are not magic. They are functions plus JSON.

---

## "Advanced mode" — running against Postgres

The original schema was authored in Postgres. The full DDL and data-load scripts live in `schema/postgres/`. If you'd rather run the demo against Postgres than SQLite, you can use that directory as a starting point — but the MCP server in this repo speaks SQLite. Adapting it to Postgres is a 10-line swap (`sqlite3` → `psycopg`) we may ship as an alternate `server/server_postgres.py` in a future commit.

---

## Why "Kuromaku U"?

"Kuromaku" — 黒幕 — is the Japanese term for the unseen power behind the scenes, the wire-puller. Jim Milbery uses the name as a recurring brand across a novel project and a small constellation of software experiments. Kuromaku U is the fictional engineering school we send our characters to when we need a realistic dataset and don't feel like inventing yet another one.

---

## License

MIT. Use it for whatever — explainer videos, course demos, MCP server tutorials, sample data for prototypes, conference talks, your own podcast. If you do something fun with it, drop a note: [jim@parkergale.com](mailto:jim@parkergale.com).
