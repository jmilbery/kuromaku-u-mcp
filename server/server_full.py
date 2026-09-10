#!/usr/bin/env python3
"""
Kuromaku U — Full-Coverage MCP Server
======================================

Every table in the Kuromaku U database, reachable by a tool.

server_minimal.py is one tool. server.py is six, chosen on purpose and left
thin. This is the other end of that ladder: the six from server.py, unchanged,
plus enough more that no question about the data forces the model the long way
round. Built for PE TechCast — MCP vs RAG, as the MCP side of the comparison.

Coverage, by table:
  student, student_address ....... find_students, student_detail,
                                   student_addresses, students_by_location
  student_enrollment, cd_grade ... student_courses, student_transcript,
                                   course_roster, course_history
  course_catalog ................. search_catalog, course_detail
  semester ....................... current_semester, list_semesters
  cd_major, cd_minor ............. list_majors, list_minors
  class_year, cd_ethnicity,
  cd_country, cd_state,
  cd_building_type ............... code_table
  building, building_distance .... list_buildings, building_distance,
                                   buildings_near
  aggregates across all of it .... student_counts, enrollment_counts, gpa_stats

Optional, off by default: run_sql — a single read-only SQL tool that covers
everything above on its own. Set KUROMAKU_U_ALLOW_SQL=1 to register it. It is
here for the comparison, not as a recommendation: it buys total coverage by
giving up every guardrail the typed tools provide.

Run it:
    python server/server_full.py          # stdio transport

Register with Claude Code:
    claude mcp add kuromaku-u-full --scope user -- \
        /abs/path/.venv/bin/python /abs/path/server/server_full.py
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

# The six tools from server.py are imported, not copied, so this server stays a
# strict superset of it and the two can never drift apart.
from server import (
    DB_PATH, _conn, _rows_to_dicts,
    find_students, student_detail, student_courses,
    course_roster, search_catalog, current_semester,
)

mcp = FastMCP("kuromaku-u-full")

for _tool in (find_students, student_detail, student_courses,
              course_roster, search_catalog, current_semester):
    mcp.tool()(_tool)


def _current_semester_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT semester_id FROM semester WHERE is_current = 1 LIMIT 1").fetchone()
    return row[0] if row else None


def _gpa(graded: list[tuple[float, int]]) -> float | None:
    """Units-weighted GPA over (numeric_grade, units) pairs."""
    units = sum(u for _, u in graded)
    return round(sum(g * u for g, u in graded) / units, 2) if units else None


# CORE-* courses carry department code COR, which has no row in cd_major: the
# schema has majors but no departments table. Name it rather than report null.
_CORE_NAME = "CASE WHEN {code} = 'COR' THEN 'CORE CURRICULUM' END"


# One active address per student. student_address keeps history, so a plain
# join on active_flag could double-count anyone with two rows marked active.
_PRIMARY_ADDRESS = """
    LEFT JOIN (SELECT student_id, MIN(row_id) AS row_id
                 FROM student_address WHERE active_flag = 1
                GROUP BY student_id) pa ON pa.student_id = s.student_id
    LEFT JOIN student_address a  ON a.row_id      = pa.row_id
    LEFT JOIN cd_state        st ON st.cd_state   = a.cd_state
    LEFT JOIN cd_country      co ON co.cd_country = a.cd_country
"""


# ─────────────────────────────────────────────────────────────────────────────
# STUDENTS — addresses and location
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def student_addresses(student_id: int) -> list[dict[str, Any]]:
    """Every address on file for one student, current and past.

    student_detail returns only the active address. Use this when the question
    is about address history, or about a student with more than one address.

    Args:
        student_id: integer student ID.

    Returns:
        List of address dicts with state and country names resolved, active
        address first. Empty list if the student has no address on file.
    """
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT a.address_1, a.address_2, a.city,
                   a.cd_state, st.name_state, a.province,
                   a.zip_code, a.postal_code,
                   a.cd_country, co.name_country, a.active_flag
            FROM student_address a
            LEFT JOIN cd_state   st ON st.cd_state   = a.cd_state
            LEFT JOIN cd_country co ON co.cd_country = a.cd_country
            WHERE a.student_id = ?
            ORDER BY a.active_flag DESC, a.row_id
            """,
            (student_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


@mcp.tool()
def students_by_location(
    state: str | None = None,
    country: str | None = None,
    city: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Students whose current home address is in a given state, country or city.

    Args:
        state: US state as a 2-letter code ('TX') or full name ('Texas').
        country: country as a code or full name.
        city: substring match against city (case-insensitive).
        limit: max students to list. match_count is always the full total.

    Returns:
        Dict with match_count (every match) and up to `limit` students: id,
        name, major, class year, city, state, country. Give at least one filter.
    """
    where, params = [], []
    if state:
        where.append("(UPPER(a.cd_state) = ? OR UPPER(st.name_state) = ?)")
        params.extend([state.upper(), state.upper()])
    if country:
        where.append("(UPPER(a.cd_country) = ? OR UPPER(co.name_country) = ?)")
        params.extend([country.upper(), country.upper()])
    if city:
        where.append("LOWER(a.city) LIKE ?")
        params.append(f"%{city.lower()}%")
    if not where:
        return {"error": "give at least one of state, country or city"}

    sql = f"""
        SELECT s.student_id, s.first_name, s.last_name,
               s.cd_major AS major, s.class_year,
               a.city, a.cd_state AS state, co.name_country AS country
        FROM student s
        {_PRIMARY_ADDRESS}
        WHERE {' AND '.join(where)}
        ORDER BY s.last_name, s.first_name
    """
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"match_count": len(rows), "students": _rows_to_dicts(rows[:limit])}


# ─────────────────────────────────────────────────────────────────────────────
# ACADEMICS — transcripts and course history
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def student_transcript(student_id: int) -> dict[str, Any] | None:
    """A student's full academic record: every semester, every course, every grade.

    Use this instead of calling student_courses once per semester. Includes term
    and cumulative GPA (units-weighted, 4.0 scale). Current-semester courses have
    no grade yet and are excluded from GPA.

    Args:
        student_id: integer student ID.

    Returns:
        Dict with the student's name, a list of semesters (courses, grades, term
        GPA), cumulative_gpa, units_completed and units_in_progress. None if the
        student doesn't exist.
    """
    with _conn() as conn:
        student = conn.execute(
            "SELECT student_id, first_name, last_name, cd_major, class_year FROM student WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        if not student:
            return None
        rows = conn.execute(
            """
            SELECT sm.semester_id, sm.semester_name,
                   e.catnum, cc.course_title, cc.units,
                   g.letter_grade, g.numeric_grade
            FROM student_enrollment e
            JOIN course_catalog cc ON cc.catnum     = e.catnum
            JOIN semester       sm ON sm.semester_id = e.semester_id
            LEFT JOIN cd_grade  g  ON g.cd_grade    = e.cd_grade
            WHERE e.student_id = ?
            ORDER BY sm.academic_year_start, sm.semester_id, e.catnum
            """,
            (student_id,),
        ).fetchall()

    semesters: dict[int, dict[str, Any]] = {}
    graded_all: list[tuple[float, int]] = []
    in_progress = 0
    for r in rows:
        sem = semesters.setdefault(r["semester_id"], {
            "semester_id": r["semester_id"], "semester_name": r["semester_name"],
            "courses": [], "_graded": [],
        })
        sem["courses"].append({
            "catnum": r["catnum"], "course_title": r["course_title"],
            "units": r["units"], "letter_grade": r["letter_grade"],
        })
        if r["numeric_grade"] is None:
            in_progress += r["units"]
        else:
            sem["_graded"].append((r["numeric_grade"], r["units"]))
            graded_all.append((r["numeric_grade"], r["units"]))

    for sem in semesters.values():
        sem["term_gpa"] = _gpa(sem.pop("_graded"))

    return {
        **dict(student),
        "semesters": list(semesters.values()),
        "cumulative_gpa": _gpa(graded_all),
        "units_completed": sum(u for g, u in graded_all if g > 0),
        "units_in_progress": in_progress,
    }


@mcp.tool()
def course_detail(catnum: str) -> dict[str, Any] | None:
    """Everything the catalog says about one course, plus how often it has run.

    search_catalog returns titles only. Use this for the description, the course
    type (LEC lecture, LAB lab, IND independent study), units, and the
    department's full name.

    Args:
        catnum: course catalog number (e.g., 'MECH-2040').

    Returns:
        Dict with catalog fields, semesters_offered, total_enrollments and
        current_enrollment. None if the course doesn't exist.
    """
    with _conn() as conn:
        row = conn.execute(
            f"""
            SELECT cc.catnum, cc.course_title, cc.course_desc, cc.course_type,
                   cc.units, cc.active_flag,
                   cc.cd_major_minor AS department,
                   COALESCE(m.name_major, {_CORE_NAME.format(code="cc.cd_major_minor")}) AS department_name
            FROM course_catalog cc
            LEFT JOIN cd_major m ON m.cd_major = cc.cd_major_minor
            WHERE cc.catnum = ?
            """,
            (catnum.upper(),),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        stats = conn.execute(
            """
            SELECT COUNT(DISTINCT semester_id) AS semesters_offered,
                   COUNT(*) AS total_enrollments,
                   SUM(semester_id = ?) AS current_enrollment
            FROM student_enrollment WHERE catnum = ?
            """,
            (_current_semester_id(conn), catnum.upper()),
        ).fetchone()
        result.update({k: stats[k] or 0 for k in stats.keys()})
        return result


@mcp.tool()
def course_history(catnum: str) -> dict[str, Any]:
    """How a course has run over time: enrollment and average GPA by semester,
    plus its grade distribution across every graded offering.

    Args:
        catnum: course catalog number (e.g., 'MECH-2040').

    Returns:
        Dict with the course title, a per-semester list (enrolled, graded,
        avg_gpa) and grade_distribution (letter grade → count).
    """
    with _conn() as conn:
        course = conn.execute(
            "SELECT catnum, course_title FROM course_catalog WHERE catnum = ?",
            (catnum.upper(),),
        ).fetchone()
        if not course:
            return {"error": f"course '{catnum}' not found"}
        by_semester = conn.execute(
            """
            SELECT sm.semester_id, sm.semester_name,
                   COUNT(*) AS enrolled,
                   COUNT(g.numeric_grade) AS graded,
                   ROUND(AVG(g.numeric_grade), 2) AS avg_gpa
            FROM student_enrollment e
            JOIN semester      sm ON sm.semester_id = e.semester_id
            LEFT JOIN cd_grade g  ON g.cd_grade     = e.cd_grade
            WHERE e.catnum = ?
            GROUP BY sm.semester_id
            ORDER BY sm.academic_year_start, sm.semester_id
            """,
            (catnum.upper(),),
        ).fetchall()
        distribution = conn.execute(
            """
            SELECT g.letter_grade, COUNT(*) AS n
            FROM student_enrollment e JOIN cd_grade g ON g.cd_grade = e.cd_grade
            WHERE e.catnum = ?
            GROUP BY g.cd_grade ORDER BY g.cd_grade
            """,
            (catnum.upper(),),
        ).fetchall()
        return {
            "course": dict(course),
            "semesters": _rows_to_dicts(by_semester),
            "grade_distribution": {r["letter_grade"]: r["n"] for r in distribution},
        }


# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE — semesters, majors, minors, code tables
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def list_semesters() -> list[dict[str, Any]]:
    """Every semester on file, oldest first, with how many students enrolled.

    Returns:
        List of semester dicts: id, name, academic year, dates, is_current,
        enrollments and students. Semesters with no enrollments show zeros.
    """
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT sm.semester_id, sm.semester_name,
                   sm.academic_year_start, sm.academic_year_end,
                   sm.semester_start_date, sm.semester_end_date, sm.is_current,
                   COUNT(e.row_id) AS enrollments,
                   COUNT(DISTINCT e.student_id) AS students
            FROM semester sm
            LEFT JOIN student_enrollment e ON e.semester_id = sm.semester_id
            GROUP BY sm.semester_id
            ORDER BY sm.academic_year_start, sm.semester_id
            """
        ).fetchall()
        return _rows_to_dicts(rows)


@mcp.tool()
def list_majors() -> list[dict[str, Any]]:
    """Every major Kuromaku U offers, with how many students and active courses each has.

    This is the answer to "what majors do you offer?" — one call. (server.py
    leaves it out on purpose, which forces the model to infer majors by reading
    all 303 courses.)

    Returns:
        List of dicts: major code, name, students, active_courses.
    """
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT m.cd_major AS major, m.name_major AS name,
                   (SELECT COUNT(*) FROM student s WHERE s.cd_major = m.cd_major) AS students,
                   (SELECT COUNT(*) FROM course_catalog cc
                     WHERE cc.cd_major_minor = m.cd_major AND cc.active_flag = 1) AS active_courses
            FROM cd_major m
            ORDER BY m.sort_order
            """
        ).fetchall()
        return _rows_to_dicts(rows)


@mcp.tool()
def list_minors() -> list[dict[str, Any]]:
    """Every minor Kuromaku U offers, with how many students have declared each.

    Returns:
        List of dicts: minor code, name, students.
    """
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT mi.cd_minor AS minor, mi.name_minor AS name,
                   (SELECT COUNT(*) FROM student s WHERE s.cd_minor = mi.cd_minor) AS students
            FROM cd_minor mi
            ORDER BY mi.sort_order
            """
        ).fetchall()
        return _rows_to_dicts(rows)


_CODE_TABLES = {
    "class_year":    ("class_year",       "sort_order"),
    "ethnicity":     ("cd_ethnicity",     "sort_order"),
    "country":       ("cd_country",       "sort_order"),
    "state":         ("cd_state",         "sort_order"),
    "grade":         ("cd_grade",         "cd_grade"),
    "building_type": ("cd_building_type", "sort_order"),
}


@mcp.tool()
def code_table(
    table: Literal["class_year", "ethnicity", "country", "state", "grade", "building_type"],
) -> list[dict[str, Any]]:
    """The rows of one lookup table — what a code means.

    Use when a result contains a code you need to translate (a state code, an
    ethnicity code, a building type number) or to list the valid values of one.
    'grade' maps letter grades to the 4.0 scale. 'state' carries census region,
    division and federal circuit. Majors and minors have their own tools.

    Args:
        table: which lookup table to return.

    Returns:
        Every row of that table, in its natural order.
    """
    name, order = _CODE_TABLES[table]
    with _conn() as conn:
        return _rows_to_dicts(conn.execute(f"SELECT * FROM {name} ORDER BY {order}").fetchall())


# ─────────────────────────────────────────────────────────────────────────────
# CAMPUS — buildings and distances
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_building(conn: sqlite3.Connection, ref: str) -> tuple[sqlite3.Row | None, str | None]:
    """Match a building by exact ID, else by unique name substring."""
    row = conn.execute(
        "SELECT building_id, name FROM building WHERE building_id = ?", (ref.upper(),)
    ).fetchone()
    if row:
        return row, None
    rows = conn.execute(
        "SELECT building_id, name FROM building WHERE LOWER(name) LIKE ? ORDER BY name",
        (f"%{ref.lower()}%",),
    ).fetchall()
    if len(rows) == 1:
        return rows[0], None
    if not rows:
        return None, f"no building matches '{ref}'"
    names = ", ".join(f"{r['name']} ({r['building_id']})" for r in rows[:10])
    return None, f"'{ref}' matches {len(rows)} buildings: {names}"


@mcp.tool()
def list_buildings(building_type: str | None = None) -> list[dict[str, Any]]:
    """Campus buildings, optionally filtered by type.

    Args:
        building_type: optional substring of the type name (e.g., 'dorm',
            'academic', 'library'). See code_table('building_type') for all types.

    Returns:
        List of dicts: building_id, name, building_type, centroid_x, centroid_y.
    """
    where, params = "", []
    if building_type:
        where = "WHERE LOWER(t.name_building_type) LIKE ?"
        params.append(f"%{building_type.lower()}%")
    with _conn() as conn:
        rows = conn.execute(
            f"""
            SELECT b.building_id, b.name, t.name_building_type AS building_type,
                   b.centroid_x, b.centroid_y
            FROM building b
            LEFT JOIN cd_building_type t ON t.cd_building_type = b.cd_building_type
            {where}
            ORDER BY b.name
            """,
            params,
        ).fetchall()
        return _rows_to_dicts(rows)


@mcp.tool()
def building_distance(from_building: str, to_building: str) -> dict[str, Any]:
    """Straight-line distance in meters between two campus buildings,
    centroid to centroid — as the crow flies, not a walking route.

    Args:
        from_building: building ID (e.g., 'KUROMAKUH') or part of its name.
        to_building: building ID or part of its name.

    Returns:
        Dict with both buildings and distance_in_meters.
    """
    with _conn() as conn:
        a, err = _resolve_building(conn, from_building)
        if err:
            return {"error": err}
        b, err = _resolve_building(conn, to_building)
        if err:
            return {"error": err}
        if a["building_id"] == b["building_id"]:
            meters = 0.0
        else:
            row = conn.execute(
                "SELECT distance_in_meters FROM building_distance WHERE building_id = ? AND target_building_id = ?",
                (a["building_id"], b["building_id"]),
            ).fetchone()
            meters = row[0] if row else None
        return {
            "from": dict(a),
            "to": dict(b),
            "distance_in_meters": round(meters, 1) if meters is not None else None,
        }


@mcp.tool()
def buildings_near(
    building: str,
    within_meters: float | None = None,
    building_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """The buildings closest to a given one, nearest first.

    Args:
        building: building ID or part of its name.
        within_meters: optional radius; only buildings at most this far away.
        building_type: optional substring of the type name (e.g., 'dorm').
        limit: max buildings to return.

    Returns:
        Dict with the origin building and a list of nearby buildings with
        building_type and distance_in_meters.
    """
    with _conn() as conn:
        origin, err = _resolve_building(conn, building)
        if err:
            return {"error": err}
        where, params = ["bd.building_id = ?"], [origin["building_id"]]
        if within_meters is not None:
            where.append("bd.distance_in_meters <= ?")
            params.append(within_meters)
        if building_type:
            where.append("LOWER(t.name_building_type) LIKE ?")
            params.append(f"%{building_type.lower()}%")
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT b.building_id, b.name, t.name_building_type AS building_type,
                   ROUND(bd.distance_in_meters, 1) AS distance_in_meters
            FROM building_distance bd
            JOIN building b ON b.building_id = bd.target_building_id
            LEFT JOIN cd_building_type t ON t.cd_building_type = b.cd_building_type
            WHERE {' AND '.join(where)}
            ORDER BY bd.distance_in_meters
            LIMIT ?
            """,
            params,
        ).fetchall()
        return {"from": dict(origin), "nearby": _rows_to_dicts(rows)}


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS — counts and GPA, grouped
# ─────────────────────────────────────────────────────────────────────────────
_STUDENT_GROUPS = {
    "major":      ("s.cd_major",     "m.name_major"),
    "minor":      ("s.cd_minor",     "mi.name_minor"),
    "class_year": ("s.class_year",   "cy.class_name"),
    "gender":     ("s.gender",       "s.gender"),
    "ethnicity":  ("s.cd_ethnicity", "e.name_ethnicity"),
    "state":      ("a.cd_state",     "st.name_state"),
    "country":    ("a.cd_country",   "co.name_country"),
}


@mcp.tool()
def student_counts(
    group_by: Literal["major", "minor", "class_year", "gender", "ethnicity", "state", "country"],
    major: str | None = None,
    class_year: int | None = None,
    state: str | None = None,
) -> dict[str, Any]:
    """How many students, broken down by one attribute. Use for any "how many
    students…" question — find_students lists people and caps at a limit.

    Filters compose with the grouping: group_by='state', major='MEC' answers
    "where are the mechanical engineers from?". State and country come from
    each student's current home address.

    Args:
        group_by: the attribute to break the count down by.
        major: optional 3-letter major code filter.
        class_year: optional class year filter (e.g., 2027).
        state: optional 2-letter home-state filter.

    Returns:
        Dict with total (students matching the filters) and groups — key,
        label, students — largest first.
    """
    key, label = _STUDENT_GROUPS[group_by]
    where, params = [], []
    if major:
        where.append("s.cd_major = ?")
        params.append(major.upper())
    if class_year is not None:
        where.append("s.class_year = ?")
        params.append(class_year)
    if state:
        where.append("a.cd_state = ?")
        params.append(state.upper())
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT {key} AS key, {label} AS label, COUNT(*) AS students
        FROM student s
        LEFT JOIN cd_major     m  ON m.cd_major     = s.cd_major
        LEFT JOIN cd_minor     mi ON mi.cd_minor    = s.cd_minor
        LEFT JOIN class_year   cy ON cy.class_year  = s.class_year
        LEFT JOIN cd_ethnicity e  ON e.cd_ethnicity = s.cd_ethnicity
        {_PRIMARY_ADDRESS}
        {where_sql}
        GROUP BY {key}
        ORDER BY students DESC, key
    """
    with _conn() as conn:
        groups = _rows_to_dicts(conn.execute(sql, params).fetchall())
        return {"total": sum(g["students"] for g in groups), "groups": groups}


# Each grouping starts from the thing being grouped and LEFT JOINs enrollments
# onto it, so a course or semester with nobody in it shows up as a zero rather
# than vanishing. "Which courses had no one this term?" needs those zeros.
_ENROLLMENT_GROUPS = {
    "semester": (
        "semester sm LEFT JOIN student_enrollment e ON e.semester_id = sm.semester_id {on}",
        "sm.semester_id", "sm.semester_name"),
    "course": (
        "course_catalog cc LEFT JOIN student_enrollment e ON e.catnum = cc.catnum {on}",
        "cc.catnum", "cc.course_title"),
    "department": (
        "course_catalog cc LEFT JOIN cd_major d ON d.cd_major = cc.cd_major_minor "
        "LEFT JOIN student_enrollment e ON e.catnum = cc.catnum {on}",
        "cc.cd_major_minor", f"COALESCE(d.name_major, {_CORE_NAME.format(code='cc.cd_major_minor')})"),
    "major": (
        "student s LEFT JOIN cd_major d ON d.cd_major = s.cd_major "
        "LEFT JOIN student_enrollment e ON e.student_id = s.student_id {on}",
        "s.cd_major", "d.name_major"),
    "class_year": (
        "student s LEFT JOIN class_year cy ON cy.class_year = s.class_year "
        "LEFT JOIN student_enrollment e ON e.student_id = s.student_id {on}",
        "s.class_year", "cy.class_name"),
}


@mcp.tool()
def enrollment_counts(
    group_by: Literal["semester", "course", "department", "major", "class_year"],
    semester_id: int | None = None,
    order: Literal["most", "fewest"] = "most",
    limit: int = 50,
) -> dict[str, Any]:
    """Course enrollments counted and broken down. Use for "how many
    enrollments", "most/least popular course", "which courses are empty".

    'department' groups by the course's department; 'major' groups by the
    enrolled student's major. Zero-enrollment groups are included, so
    order='fewest' surfaces empty courses.

    Args:
        group_by: what to break the count down by.
        semester_id: optional; restrict to one semester. Omit for every
            semester on record. current_semester() gives this term's ID.
        order: 'most' (default) or 'fewest' first.
        limit: max groups to return. total always counts everything.

    Returns:
        Dict with total enrollments (for the semester filter) and groups —
        key, label, enrollments, students.
    """
    from_sql, key, label = _ENROLLMENT_GROUPS[group_by]
    params: list[Any] = []
    if semester_id is not None and group_by == "semester":
        from_sql, where = from_sql.format(on=""), "WHERE sm.semester_id = ?"
        params.append(semester_id)
    elif semester_id is not None:
        from_sql, where = from_sql.format(on="AND e.semester_id = ?"), ""
        params.append(semester_id)
    else:
        from_sql, where = from_sql.format(on=""), ""
    direction = "DESC" if order == "most" else "ASC"
    sql = f"""
        SELECT {key} AS key, {label} AS label,
               COUNT(e.row_id) AS enrollments,
               COUNT(DISTINCT e.student_id) AS students
        FROM {from_sql}
        {where}
        GROUP BY {key}
        ORDER BY enrollments {direction}, key
        LIMIT ?
    """
    with _conn() as conn:
        groups = conn.execute(sql, [*params, limit]).fetchall()
        if semester_id is None:
            total = conn.execute("SELECT COUNT(*) FROM student_enrollment").fetchone()[0]
        else:
            total = conn.execute(
                "SELECT COUNT(*) FROM student_enrollment WHERE semester_id = ?", (semester_id,)
            ).fetchone()[0]
        return {"total": total, "groups": _rows_to_dicts(groups)}


_GPA_GROUPS = {
    "major":      ("s.cd_major",       "d.name_major"),
    "class_year": ("s.class_year",     "cy.class_name"),
    "semester":   ("sm.semester_id",   "sm.semester_name"),
    "department": ("cc.cd_major_minor", f"COALESCE(cd.name_major, {_CORE_NAME.format(code='cc.cd_major_minor')})"),
    "course":     ("cc.catnum",        "cc.course_title"),
    "student":    ("s.student_id",     "s.first_name || ' ' || s.last_name"),
}


@mcp.tool()
def gpa_stats(
    group_by: Literal["major", "class_year", "semester", "department", "course", "student"],
    semester_id: int | None = None,
    major: str | None = None,
    class_year: int | None = None,
    min_graded_courses: int = 1,
    order: Literal["highest", "lowest"] = "highest",
    limit: int = 25,
) -> dict[str, Any]:
    """Average GPA (units-weighted, 4.0 scale) over graded courses, grouped.

    Answers "which major has the highest GPA", "top students in the class of
    2027", "hardest courses". Current-semester courses have no grade yet and
    are not counted.

    Args:
        group_by: what to rank. 'department' is the course's department;
            'major' is the student's.
        semester_id: optional; restrict to grades from one semester.
        major: optional student major filter (3-letter code).
        class_year: optional student class year filter.
        min_graded_courses: drop groups with fewer graded courses than this —
            use 4 or more when ranking students or courses, to skip tiny samples.
        order: 'highest' (default) or 'lowest' first.
        limit: max groups to return.

    Returns:
        Dict with overall_gpa (across every matching grade) and groups — key,
        label, gpa, graded_courses, graded_units.
    """
    key, label = _GPA_GROUPS[group_by]
    where, params = [], []
    if semester_id is not None:
        where.append("e.semester_id = ?")
        params.append(semester_id)
    if major:
        where.append("s.cd_major = ?")
        params.append(major.upper())
    if class_year is not None:
        where.append("s.class_year = ?")
        params.append(class_year)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    from_sql = f"""
        FROM student_enrollment e
        JOIN cd_grade       g  ON g.cd_grade     = e.cd_grade
        JOIN course_catalog cc ON cc.catnum      = e.catnum
        JOIN student        s  ON s.student_id   = e.student_id
        JOIN semester       sm ON sm.semester_id = e.semester_id
        LEFT JOIN cd_major   d  ON d.cd_major    = s.cd_major
        LEFT JOIN cd_major   cd ON cd.cd_major   = cc.cd_major_minor
        LEFT JOIN class_year cy ON cy.class_year = s.class_year
        {where_sql}
    """
    gpa = "ROUND(SUM(g.numeric_grade * cc.units) * 1.0 / SUM(cc.units), 3)"
    direction = "DESC" if order == "highest" else "ASC"
    with _conn() as conn:
        groups = conn.execute(
            f"""
            SELECT {key} AS key, {label} AS label, {gpa} AS gpa,
                   COUNT(*) AS graded_courses, SUM(cc.units) AS graded_units
            {from_sql}
            GROUP BY {key}
            HAVING COUNT(*) >= ?
            ORDER BY gpa {direction}, key
            LIMIT ?
            """,
            [*params, min_graded_courses, limit],
        ).fetchall()
        overall = conn.execute(f"SELECT {gpa} {from_sql}", params).fetchone()[0]
        return {"overall_gpa": overall, "groups": _rows_to_dicts(groups)}


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONAL — run_sql, the one tool that covers everything
# ─────────────────────────────────────────────────────────────────────────────
if os.environ.get("KUROMAKU_U_ALLOW_SQL") == "1":

    def _deny_attach(action, *_):
        if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    @mcp.tool()
    def run_sql(query: str, limit: int = 200) -> dict[str, Any]:
        """Run one read-only SQL query against the Kuromaku U SQLite database.

        Prefer the typed tools; use this only when none of them fits. Tables:
        student, student_address, student_enrollment, course_catalog, semester,
        class_year, cd_major, cd_minor, cd_grade, cd_ethnicity, cd_country,
        cd_state, building, building_distance, cd_building_type. For column
        definitions, query sqlite_master. The connection is read-only: one
        statement per call, no writes, no ATTACH.

        Args:
            query: a single SQL SELECT statement (SQLite dialect).
            limit: max rows to return.

        Returns:
            Dict with columns, rows (as lists), row_count and truncated.
        """
        if not DB_PATH.exists():
            return {"error": f"database not found at {DB_PATH}"}
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.set_authorizer(_deny_attach)
        try:
            cur = conn.execute(query)
            rows = cur.fetchmany(limit + 1)
            columns = [c[0] for c in cur.description or []]
        except sqlite3.Error as e:
            return {"error": str(e)}
        finally:
            conn.close()
        return {
            "columns": columns,
            "rows": [list(r) for r in rows[:limit]],
            "row_count": min(len(rows), limit),
            "truncated": len(rows) > limit,
        }


if __name__ == "__main__":
    mcp.run()
