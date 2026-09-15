#!/usr/bin/env python3
"""
server_minimal.py — the simplest possible MCP server.

This is what the demo close-up shows: "every MCP server is just this shape."
Import the SDK, name the server, decorate a function as a tool, run it.
The full six-tool version lives in server.py.

Register with Claude Code (NOT settings.json — that's Claude Desktop):

    claude mcp add kuromaku-u-minimal --scope user -- \
        /abs/path/.venv/bin/python /abs/path/server/server_minimal.py

  ...or drop an mcpServers block in a project .mcp.json. Point command at
  the venv python so the `mcp` dep resolves.

Restart Claude Code. /mcp should show it green. Then ask:
"Find me a Kuromaku U student named Bracegirdle."
"""
import sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DB = Path(__file__).resolve().parent.parent / "kuromaku_u.db"
mcp = FastMCP("kuromaku-u-minimal")


@mcp.tool()
def find_student(name: str) -> list[dict]:
    """Find Kuromaku U students by first or last name (case-insensitive)."""
    sql = """SELECT student_id, first_name, last_name, cd_major, class_year
             FROM student
             WHERE LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
             ORDER BY last_name LIMIT 10"""
    like = f"%{name.lower()}%"
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, (like, like)).fetchall()]


if __name__ == "__main__":
    mcp.run()
