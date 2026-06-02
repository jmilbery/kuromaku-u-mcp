# Screens to Capture — PE TechCast EP. 08b Demo Segment

Target runtime: **60-90 seconds of demo footage** inside Part 2. Capture
everything below in clean takes; edit down in post.

The arc: show code → show config → show wiring → show it work.

---

## A. The Code (15-20 seconds)

**Capture:**
- Editor (Cursor / VS Code) with `server/server_minimal.py` open
- Whole file visible — it's ~30 lines including comments, fits on one screen
- Cursor or highlight call-outs on these 4 lines as you narrate:
  - `from mcp.server.fastmcp import FastMCP`
  - `mcp = FastMCP("kuromaku-u-minimal")`
  - `@mcp.tool()`
  - `mcp.run()`

**Narration beat:**
> "Here's the whole MCP server. Import. Instance. Decorate a function as a tool. Run it. The rest is just SQL."

---

## B. The Config (10-15 seconds)

**Capture:**
- `~/.claude/settings.json` open in an editor
- Show the `mcpServers` block being pasted/edited in
- Optional: brief before/after split — "without MCP" config → "with MCP" config

**Narration beat:**
> "Three lines of JSON. Command, path to the server, name it. Save and restart Claude Code."

---

## C. The Wire-Up (5-10 seconds)

**Capture:**
- Claude Code freshly opened after restart
- Run `/mcp` — show the output with `kuromaku-u-minimal` listed green and tool count

**Narration beat:**
> "Slash MCP. It's connected. One tool registered. We're live."

---

## D. The Live Demo (20-30 seconds — the money shot)

**Capture:**
- Claude Code chat window, clean (no prior history visible)
- Type the Stage 1 prompt: *"Find me a Kuromaku University student with the last name Bracegirdle."*
- Watch Claude's response build:
  - Tool call indicator fires
  - Tool returns JSON
  - Claude formats the answer

**Narration beat:**
> "I'm asking a question that's not in the model's training data. It's in my SQLite database. Watch what happens."
> *(beat for tool call)*
> "Tool call fires. SQL runs. Real answer comes back. Heath Bracegirdle, mechanical engineering, class of 2024."

---

## E. (Optional) The Chained-Tools Encore (15-20 seconds)

If runtime budget allows, show the full six-tool server doing something
Claude couldn't do with just `find_student`:

**Capture:**
- Same Claude Code window
- Switch the active MCP server in your head (both are configured)
- Type the Stage 2 prompt: *"Who's in COMP-1005 this semester at Kuromaku U, and what are their majors?"*
- Watch Claude call `current_semester` → `course_roster` → format

**Narration beat:**
> "Same protocol. More tools. Now Claude chains three calls — get the current semester, get the roster for the course, format the answer. Thirteen students. Real names. Real majors. Real database."

---

## Production Notes

- **Resolution:** capture at native retina or 1080p+ — the editor text needs to be readable when scaled to thumbnail size
- **Font:** bump editor font size to 16-18pt before recording so code is legible on YouTube
- **Theme:** dark theme strongly preferred — matches the TechCast diagram aesthetic
- **Cursor visibility:** consider an app like Mouseposé or a recording tool with built-in cursor highlighting so viewers can follow your eye line
- **No mouse jitter:** pre-position the editor windows; don't drag mid-take
- **Audio:** narrate live OR record voice-over separately and sync in post — both work; live tends to feel more authentic
