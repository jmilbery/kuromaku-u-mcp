#!/usr/bin/env python3
"""
Kuromaku U — MCP Server
========================

The simplest possible MCP server exposing the Kuromaku University database to
an MCP client (Claude Code, Claude Desktop, Cursor, etc.).

Built for PE TechCast EP. 08b — MCP Part 2 (Under the Hood).

Tools exposed:
  • find_students      — search the student directory by name / major / class year
  • student_detail     — full record for one student (with major/minor/class-year names joined in)
  • student_courses    — courses a student is taking this semester (or any semester)
  • course_roster      — every student enrolled in a course in a given semester
  • search_catalog     — search the course catalog by keyword or department
  • current_semester   — what semester is "now"

Run it:
    pip install -e ".[dev]"          # from repo root
    python server/server.py          # stdio transport (for Claude Code / Desktop)

Register with Claude Code (NOT settings.json — that key is Claude Desktop):
    claude mcp add kuromaku-u --scope user -- \
        /abs/path/.venv/bin/python /abs/path/server/server.py
  ...or use a project .mcp.json with an mcpServers block. For Claude Desktop,
  add the same block to claude_desktop_config.json. Point command at the venv
  python so the `mcp` dependency resolves.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# ── DB path resolution ──────────────────────────────────────────────────────
# Default: ../kuromaku_u.db relative to this file
# Override: KUROMAKU_U_DB env var
DEFAULT_DB = Path(__file__).resolve().parent.parent / "kuromaku_u.db"
DB_PATH    = Path(os.environ.get("KUROMAKU_U_DB", DEFAULT_DB))

mcp = FastMCP("kuromaku-u")


def _conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise RuntimeError(
            f"Database not found at {DB_PATH}. Run `python schema/build_db.py` from the repo root first."
        )
    # Read-only at the connection: no tool can change a row, whatever SQL it runs.
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — find_students
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def find_students(
    name: str | None = None,
    major: str | None = None,
    class_year: int | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Search the Kuromaku U student directory.

    Args:
        name: optional substring match against first OR last name (case-insensitive).
        major: optional 3-letter major code (e.g., 'COM', 'ENG', 'MAT').
        class_year: optional graduation/class year (e.g., 2024).
        limit: max rows to return (default 25).

    Returns:
        List of student dicts: student_id, first_name, last_name, major code,
        class_year. Returns empty list when no matches.
    """
    where, params = [], []
    if name:
        where.append("(LOWER(s.first_name) LIKE ? OR LOWER(s.last_name) LIKE ?)")
        like = f"%{name.lower()}%"
        params.extend([like, like])
    if major:
        where.append("s.cd_major = ?")
        params.append(major.upper())
    if class_year is not None:
        where.append("s.class_year = ?")
        params.append(class_year)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT s.student_id, s.first_name, s.last_name,
               s.cd_major AS major, m.name_major AS major_name,
               s.class_year, cy.class_name AS class_year_name
        FROM student s
        LEFT JOIN cd_major   m  ON m.cd_major   = s.cd_major
        LEFT JOIN class_year cy ON cy.class_year = s.class_year
        {where_sql}
        ORDER BY s.last_name, s.first_name
        LIMIT ?
    """
    params.append(limit)
    with _conn() as conn:
        return _rows_to_dicts(conn.execute(sql, params).fetchall())


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — student_detail
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def student_detail(student_id: int) -> dict[str, Any] | None:
    """Full record for one student, with joined lookups.

    Args:
        student_id: integer student ID (e.g., 1042).

    Returns:
        Dict with all student fields + resolved major / minor / class-year /
        ethnicity names + address. None if the student doesn't exist.
    """
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT s.student_id, s.first_name, s.last_name, s.email, s.school_email,
                   s.gender, s.dob, s.class_year, s.grad_year,
                   s.cd_major, m.name_major,
                   s.cd_minor, mi.name_minor,
                   s.cd_ethnicity, e.name_ethnicity,
                   cy.class_name AS class_year_name,
                   s.campus_phone, s.cell_phone, s.student_photo, s.active_flag
            FROM student s
            LEFT JOIN cd_major     m  ON m.cd_major   = s.cd_major
            LEFT JOIN cd_minor     mi ON mi.cd_minor  = s.cd_minor
            LEFT JOIN cd_ethnicity e  ON e.cd_ethnicity = s.cd_ethnicity
            LEFT JOIN class_year   cy ON cy.class_year = s.class_year
            WHERE s.student_id = ?
            """,
            (student_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        addr = conn.execute(
            "SELECT address_1, address_2, city, cd_state, zip_code, cd_country FROM student_address WHERE student_id = ? AND active_flag = 1 LIMIT 1",
            (student_id,),
        ).fetchone()
        result["address"] = dict(addr) if addr else None
        return result


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — student_courses
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def student_courses(student_id: int, semester_id: int | None = None) -> list[dict[str, Any]]:
    """Courses a student is taking (or took) in a given semester.

    Args:
        student_id: integer student ID.
        semester_id: optional semester ID. If omitted, defaults to the current semester.

    Returns:
        List of enrollment dicts: catnum, course_title, units, semester_name, letter_grade.
        Empty list if the student isn't enrolled in anything for that semester.
    """
    with _conn() as conn:
        if semester_id is None:
            cur = conn.execute("SELECT semester_id FROM semester WHERE is_current = 1 LIMIT 1").fetchone()
            if cur:
                semester_id = cur[0]
            else:
                return []
        rows = conn.execute(
            """
            SELECT e.catnum, cc.course_title, cc.units,
                   s.semester_name,
                   e.cd_grade, g.letter_grade
            FROM student_enrollment e
            JOIN course_catalog cc ON cc.catnum      = e.catnum
            JOIN semester        s ON s.semester_id  = e.semester_id
            LEFT JOIN cd_grade   g ON g.cd_grade     = e.cd_grade
            WHERE e.student_id = ? AND e.semester_id = ?
            ORDER BY cc.catnum
            """,
            (student_id, semester_id),
        ).fetchall()
        return _rows_to_dicts(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — course_roster
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def course_roster(catnum: str, semester_id: int | None = None) -> dict[str, Any]:
    """Every student enrolled in a course in a given semester.

    Args:
        catnum: course catalog number (e.g., 'COMP-2010').
        semester_id: optional semester ID. Defaults to the current semester.

    Returns:
        Dict with course info + list of enrolled students (id, name, major).
    """
    with _conn() as conn:
        course = conn.execute(
            "SELECT catnum, course_title, units, cd_major_minor FROM course_catalog WHERE catnum = ?",
            (catnum.upper(),),
        ).fetchone()
        if not course:
            return {"error": f"course '{catnum}' not found"}

        if semester_id is None:
            cur = conn.execute("SELECT semester_id, semester_name FROM semester WHERE is_current = 1 LIMIT 1").fetchone()
            if not cur:
                return {"error": "no current semester defined"}
            semester_id, semester_name = cur[0], cur[1]
        else:
            sem = conn.execute("SELECT semester_name FROM semester WHERE semester_id = ?", (semester_id,)).fetchone()
            semester_name = sem[0] if sem else None

        roster = conn.execute(
            """
            SELECT s.student_id, s.first_name, s.last_name,
                   s.cd_major AS major, m.name_major AS major_name
            FROM student_enrollment e
            JOIN student          s ON s.student_id = e.student_id
            LEFT JOIN cd_major    m ON m.cd_major   = s.cd_major
            WHERE e.catnum = ? AND e.semester_id = ?
            ORDER BY s.last_name, s.first_name
            """,
            (catnum.upper(), semester_id),
        ).fetchall()
        return {
            "course": dict(course),
            "semester_id": semester_id,
            "semester_name": semester_name,
            "enrolled_count": len(roster),
            "students": _rows_to_dicts(roster),
        }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5 — search_catalog
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def search_catalog(
    keyword: str | None = None,
    department: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Search the Kuromaku U course catalog.

    Args:
        keyword: optional substring match against course title (case-insensitive).
        department: optional 3-letter major code to filter by department.
        limit: max rows to return.

    Returns:
        List of course dicts: catnum, course_title, units, department.
    """
    where, params = ["active_flag = 1"], []
    if keyword:
        where.append("LOWER(course_title) LIKE ?")
        params.append(f"%{keyword.lower()}%")
    if department:
        where.append("cd_major_minor = ?")
        params.append(department.upper())
    sql = f"""
        SELECT catnum, course_title, units, cd_major_minor AS department
        FROM course_catalog
        WHERE {' AND '.join(where)}
        ORDER BY catnum
        LIMIT ?
    """
    params.append(limit)
    with _conn() as conn:
        return _rows_to_dicts(conn.execute(sql, params).fetchall())


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6 — current_semester
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def current_semester() -> dict[str, Any] | None:
    """The semester currently marked is_current = 1.

    Useful when a caller needs the active semester ID before drilling into
    student_courses or course_roster.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT semester_id, semester_name, academic_year_start, academic_year_end, semester_start_date, semester_end_date FROM semester WHERE is_current = 1 LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


if __name__ == "__main__":
    mcp.run()
