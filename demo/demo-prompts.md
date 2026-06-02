# Demo Prompts — PE TechCast EP. 08b (MCP Part 2)

Two stages. Stage 1 shows the minimal server (one tool). Stage 2 shows the
full server (six tools, chained calls). Pick from each list; we don't need
to land all of them.

---

## Stage 1 — `kuromaku-u-minimal` (one tool: `find_student`)

The "look how simple this is" moment. One prompt → one tool call → real data
pulled from SQLite → clean answer.

**Recommended:**
> *"Find me a Kuromaku University student with the last name Bracegirdle."*

Returns one student (Heath Bracegirdle, MEC, class of 2024). Clean, fast,
unambiguous. Good first-impression prompt.

**Alternates if you want a second take:**
> *"Look up any Kuromaku U students named Andrzejczak."*
Returns two students (Luci and Alexandros) — shows the tool can return lists.

> *"Search for any Kuromaku students with 'smith' in their name."*
Returns Greensmith and Harrismith — fuzzy match demo.

---

## Stage 2 — `kuromaku-u` (full six-tool server)

The "and here's what it looks like with the full surface area" moment. The
prompts below force Claude to call MULTIPLE tools in sequence — proves MCP
isn't a single-shot lookup, it's tool-use chained.

**Recommended (the headline):**
> *"Who's in COMP-1005 this semester at Kuromaku University, and what are their majors?"*

Claude's reasoning trace:
1. Calls `current_semester()` → gets Spring 2026
2. Calls `course_roster("COMP-1005")` → gets 13 students
3. Returns formatted list with name + major

Three sequential tool calls. Real answer. ~10 second response.

**Alternate (the advisor view):**
> *"Tell me everything about Kuromaku U student Alexandros Andrzejczak — major, what year they're in, and what courses they're taking this semester."*

Claude's reasoning trace:
1. Calls `find_students(name="Andrzejczak")` → finds student 1182
2. Calls `student_detail(1182)` → gets full record
3. Calls `student_courses(1182)` → gets Spring 2026 schedule (4 courses)
4. Synthesizes a coherent advisor-style summary

Four tool calls. Authentic "Claude as registrar's assistant" demo.

**Alternate (the catalog browse):**
> *"What computer science courses are available at Kuromaku U?"*

Single tool: `search_catalog(department="COM")` → returns 29 CS courses.
Good if you want a fast supporting beat.

---

## Pre-recording checklist

Before hitting record on a take:

- [ ] `~/.claude/settings.json` has the mcpServers block from `claude-code-config.json`
- [ ] Claude Code is freshly restarted (so the new MCP servers register)
- [ ] In Claude Code, `/mcp` shows BOTH `kuromaku-u-minimal` and `kuromaku-u` green
- [ ] `kuromaku_u.db` exists at the repo root (rebuild with `python schema/build_db.py` if not)
- [ ] Terminal cwd is `/Users/jmilbery/kuromaku-u` (so file paths in the editor make sense on camera)
