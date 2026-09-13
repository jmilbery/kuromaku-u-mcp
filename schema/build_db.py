#!/usr/bin/env python3
"""
build_db.py — build kuromaku_u.db (SQLite) from the CSVs in ../data.

Steps:
  1. Run schema/sqlite_init.sql to create the empty schema
  2. Load each CSV into its matching table
  3. Generate deterministic enrollments by walking each student's degree plan
       through the timetable: 4 courses a term, in sections that actually ran,
       respecting prerequisites, seat limits and time clashes

Usage:
  python schema/build_db.py            # builds ../kuromaku_u.db
  python schema/build_db.py --db /tmp/ku.db
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_DB_PATH  = REPO_ROOT / "kuromaku_u.db"
SCHEMA_SQL       = Path(__file__).resolve().parent / "sqlite_init.sql"

# CSV → table column mapping. Order matches SQLite columns.
# Tuple: (table_name, csv_filename, [csv_columns_to_load_in_order_of_sqlite_columns])
LOAD_PLAN = [
    ("class_year",       "ku_class_year.csv",      ["class_year","class_short_name","class_name","is_alumni","sort_order"]),
    ("cd_building_type", "ku_cd_building_type.csv",["cd_building_type","name_building_type","sort_order"]),
    ("cd_ethnicity",     "ku_cd_ethnicity.csv",    ["cd_ethnicity","name_ethnicity","sort_order"]),
    ("cd_major",         "ku_cd_major.csv",        ["cd_major","name_major","sort_order"]),
    ("cd_minor",         "ku_cd_minor.csv",        ["cd_minor","name_minor","sort_order"]),
    ("cd_grade",         "ku_cd_grade.csv",        ["cd_grade","letter_grade","numeric_grade"]),
    ("cd_country",       "ku_cd_country.csv",      ["cd_country","name_country","sort_order"]),
    ("cd_state",         "ku_cd_state.csv",        ["cd_state","name_state","fips","standard_federal_region","census_region","census_region_name","census_division","census_division_name","circuit_court","sort_order"]),
    ("building",         "ku_building.csv",        ["building_id","name","cd_building_type","centroid_x","centroid_y"]),
    ("building_distance","ku_building_distance.csv",["building_id","target_building_id","distance_in_meters"]),
    ("semester",         "ku_semester.csv",        ["semester_id","semester_name","academic_year_start","academic_year_end","semester_start_date","semester_end_date","is_current"]),
    ("department",       "ku_department.csv",      ["cd_department","catnum_prefix","name_department","dept_kind","offers_major","sort_order"]),
    ("course_catalog",   "ku_course_catalog.csv",  ["catnum","cd_major_minor","course_title","course_desc","course_type","units","course_level","active_flag"]),
    ("course_prerequisite","ku_course_prerequisite.csv",["catnum","prereq_catnum","requirement"]),
    ("program",          "ku_program.csv",         ["cd_major","degree_name","total_units","terms"]),
    ("room",             "ku_room.csv",            ["building_id","room_number","room_type","capacity"]),
    ("instructor",       "ku_instructor.csv",      ["instructor_id","first_name","last_name","email","cd_department","rank_title","hire_year","end_year","office_building_id","office_room","active_flag"]),
    ("course_offering",  "ku_course_offering.csv", ["offering_id","catnum","semester_id","section_number","instructor_id","building_id","room_number","capacity","meeting_days","start_time","end_time"]),
    ("program_requirement","ku_program_requirement.csv",["cd_major","term","slot","requirement_type","requirement_block","catnum","pool_kind","pool_min_level","units"]),
    ("student",          "ku_student.csv",         ["student_id","first_name","last_name","email","school_email","gender","dob","class_year","grad_year","cd_ethnicity","cd_major","cd_minor","campus_phone","cell_phone","student_photo","active_flag"]),
    ("student_address",  "ku_student_address.csv", ["student_id","address_1","address_2","city","cd_state","province","zip_code","postal_code","cd_country","active_flag"]),
]

# CSV header may differ from SQLite column name. Map them when needed.
CSV_HEADER_ALIASES = {
    # ku_student.csv has "ethnicity" but the SQL column is "cd_ethnicity"
    ("student", "cd_ethnicity"): "ethnicity",
    # ku_course_catalog.csv calls the department code "major_minor_code"
    ("course_catalog", "cd_major_minor"): "major_minor_code",
    # ku_cd_state.csv calls it "fips_state"; without this every fips loaded null
    ("cd_state", "fips"): "fips_state",
}

# Share of past-semester grades by letter: GPA ≈ 3.0, and F genuinely rare.
GRADE_WEIGHTS = {"A": 35, "B": 38, "C": 18, "D": 5, "F": 4}


def _open_csv(path: Path):
    """Open a CSV, stripping the BOM if present."""
    return open(path, encoding="utf-8-sig", newline="")


def _norm_bool(v: str | None) -> int | None:
    """KU CSVs use 't'/'f' for booleans. Map to 1/0; pass through None on empty."""
    if v is None or v == "":
        return None
    v = v.strip().lower()
    if v in ("t", "true", "1", "y", "yes"):
        return 1
    if v in ("f", "false", "0", "n", "no"):
        return 0
    return None


def _norm_date(v: str | None) -> str | None:
    """
    CSVs use a mix of date formats:
      - ku_student.csv DOB:   'm/d/yy'   (e.g., '12/5/00')
      - ku_semester.csv:      'YYYY-MON-DD' (e.g., '2019-SEP-01')
      - ku_class_year.csv:    'YYYY-MM-DD'
    Normalize all to ISO 'YYYY-MM-DD' for SQLite text storage.
    """
    if v is None or v == "":
        return None
    v = v.strip()
    fmts = ["%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%Y-%b-%d", "%Y-%B-%d"]
    for fmt in fmts:
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    return v  # leave as-is if no format matches; better than silently dropping


def _is_bool_column(table: str, col: str) -> bool:
    return col in {"is_alumni", "active_flag", "is_current"}


def _is_date_column(table: str, col: str) -> bool:
    return col in {"dob", "semester_start_date", "semester_end_date", "create_date", "last_update_date", "last_updated_date"}


def _is_int_column(table: str, col: str) -> bool:
    INT_COLS = {
        "class_year","grad_year","cd_building_type","fips","census_region","census_division","circuit_court",
        "semester_id","academic_year_start","academic_year_end","units","student_id","cd_grade",
        "course_level","offers_major","term","slot","pool_min_level","total_units","terms",
        "capacity","instructor_id","hire_year","end_year","offering_id",
    }
    return col in INT_COLS


def _is_real_column(table: str, col: str) -> bool:
    return col in {"sort_order","centroid_x","centroid_y","distance_in_meters","numeric_grade"}


def coerce(table: str, col: str, raw: str | None):
    """Convert raw CSV string to the right Python type for SQLite insert."""
    if raw is None or raw == "":
        return None
    raw = raw.strip()
    if _is_bool_column(table, col):
        return _norm_bool(raw)
    if _is_date_column(table, col):
        return _norm_date(raw)
    if _is_int_column(table, col):
        try:
            return int(raw)
        except ValueError:
            return None
    if _is_real_column(table, col):
        try:
            return float(raw)
        except ValueError:
            return None
    return raw  # text


def load_table(conn: sqlite3.Connection, data_dir: Path, table: str, csv_name: str, columns: list[str]) -> int:
    csv_path = data_dir / csv_name
    if not csv_path.exists():
        print(f"  ! missing: {csv_path}", file=sys.stderr)
        return 0

    placeholders = ",".join(["?"] * len(columns))
    col_list     = ",".join(columns)
    sql          = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    rows_inserted = 0
    with _open_csv(csv_path) as f:
        reader = csv.DictReader(f)
        batch: list[tuple] = []
        for row in reader:
            values: list = []
            for col in columns:
                csv_key = CSV_HEADER_ALIASES.get((table, col), col)
                values.append(coerce(table, col, row.get(csv_key)))
            batch.append(tuple(values))
            if len(batch) >= 1000:
                conn.executemany(sql, batch)
                rows_inserted += len(batch)
                batch.clear()
        if batch:
            conn.executemany(sql, batch)
            rows_inserted += len(batch)
    conn.commit()
    return rows_inserted


def sanity_check(conn: sqlite3.Connection) -> list[str]:
    """
    Guard against the failure that produced this function.

    class_year, semester and dob all encode absolute years, and this demo keeps
    being re-dated. Three separate times those fields drifted out from under the
    "current" semester and nothing noticed — a 2024 graduate was still labelled a
    freshman in 2026, students who left in 2021 sat on current rosters, and
    freshmen were born in 1999. Each was found by reading rows on camera.

    None of this is fatal, so nothing here raises. It prints loudly instead.
    """
    problems: list[str] = []
    cur = conn.cursor()

    # 1. One current semester, and it must be the newest one on file.
    current = cur.execute(
        "SELECT semester_id, semester_name FROM semester WHERE is_current = 1"
    ).fetchall()
    newest = cur.execute(
        "SELECT semester_id, semester_name FROM semester "
        "ORDER BY academic_year_start DESC, semester_id DESC LIMIT 1"
    ).fetchone()
    if len(current) != 1:
        problems.append(f"{len(current)} semesters marked is_current; expected exactly 1")
    elif current[0][0] != newest[0]:
        problems.append(
            f"is_current is on {current[0][1]}, but the newest semester is {newest[1]}"
        )

    # 2. Each class should have matriculated at about 18.
    for class_year, name, dob_median in cur.execute(
        """
        SELECT s.class_year, cy.class_name,
               AVG(julianday(s.dob))          -- mean is close enough to median here
          FROM student s JOIN class_year cy ON cy.class_year = s.class_year
         GROUP BY 1, 2 ORDER BY cy.sort_order
        """
    ).fetchall():
        matriculation = cur.execute(
            "SELECT julianday(?)", (f"{class_year - 4}-09-01",)
        ).fetchone()[0]
        age = (matriculation - dob_median) / 365.25
        if not (17.0 <= age <= 19.0):
            problems.append(
                f"class of {class_year} ({name}) matriculated at a mean age of "
                f"{age:.1f}; expected 17-19"
            )

    # 3. Nobody attends before arriving or after graduating.
    ghosts = cur.execute(
        """
        SELECT COUNT(*) FROM student_enrollment se
          JOIN student  s  ON s.student_id  = se.student_id
          JOIN semester sm ON sm.semester_id = se.semester_id
         WHERE sm.academic_year_start NOT BETWEEN s.class_year - 4 AND s.class_year  -- four years, plus one to finish
        """
    ).fetchone()[0]
    if ghosts:
        problems.append(f"{ghosts:,} enrollments fall outside the student's own four years plus a fifth to finish")

    # 4. The semester everyone will demo against should not be empty.
    if len(current) == 1:
        n = cur.execute(
            "SELECT COUNT(*) FROM student_enrollment WHERE semester_id = ?", (current[0][0],)
        ).fetchone()[0]
        if n == 0:
            problems.append(f"the current semester ({current[0][1]}) has no enrollments")

    return problems


def _clash(a, b) -> bool:
    """Two sections collide if they share a day and overlap in time."""
    if not (a["days"] & b["days"]):
        return False
    return a["start"] < b["end"] and b["start"] < a["end"]


def generate_enrollments(conn: sqlite3.Connection, *, seed: int = 1729) -> int:
    """
    Register every student, semester by semester, the way a registrar would.

    Each semester, everyone in residence registers — seniors first, then
    juniors, sophomores and freshmen, in shuffled order within a class. Each
    student takes the four courses their degree plan calls for that term, in a
    section that actually ran, had a seat, and did not collide with the rest of
    their week. Prerequisites are respected and a passed course is never taken
    again.

    v1 drew four courses at random from the whole catalog, which is why 45% of
    freshman enrollments were upper-level and 1,875 were retakes of courses the
    student had already passed. An earlier v2 pass registered one student
    through all eight terms before the next, so whoever had the lowest ID took
    seats in every semester first and later classes came up 30% short.

    What it deliberately models:
      - The record starts with the first semester on file. A class whose early
        years fall before that has those years counted as done, just unrecorded.
      - A failed course goes back on the list and is retaken — the only kind of
        repeat that should exist.
      - A course that is full, clashes or is not offered slips to a later term;
        the empty slot is filled with something else the student can take.
    """
    rng = random.Random(seed)
    grade_rng = random.Random(seed + 1)
    cur = conn.cursor()

    semesters = []
    current_semester = None
    for sid, name, ay, is_current in cur.execute(
            "SELECT semester_id, semester_name, academic_year_start, is_current FROM semester"):
        is_fall = "FALL" in name.upper()
        semesters.append((ay, 0 if is_fall else 1, sid))
        if is_current:
            current_semester = sid
    semesters.sort()
    first_ay = semesters[0][0]

    plan = defaultdict(list)
    for row in cur.execute(
            "SELECT cd_major, term, requirement_type, catnum, pool_kind "
            "FROM program_requirement ORDER BY cd_major, term, slot"):
        plan[row[0]].append(row[1:])

    offerings = defaultdict(list)
    for oid, catnum, sid, cap, days, start, end in cur.execute(
            "SELECT offering_id, catnum, semester_id, capacity, meeting_days, start_time, end_time "
            "FROM course_offering"):
        offerings[(catnum, sid)].append(
            {"id": oid, "cap": cap, "taken": 0, "days": set(days), "start": start, "end": end})

    prereq = defaultdict(list)
    for catnum, p, kind in cur.execute(
            "SELECT catnum, prereq_catnum, requirement FROM course_prerequisite"):
        prereq[catnum].append((p, kind))

    dept, level = {}, {}
    for catnum, d, lvl in cur.execute("SELECT catnum, cd_major_minor, course_level FROM course_catalog"):
        dept[catnum], level[catnum] = d, lvl or 1
    named = {m: {c for _, _, c, _ in rows if c} for m, rows in plan.items()}
    gened_pool = sorted(c for c in dept if dept[c] in ("HUM", "SOC"))
    major_pool = {m: sorted(c for c in dept if dept[c] == m and level[c] >= 3 and c not in named[m])
                  for m in plan}
    # What a student reaches for when a plan slot cannot be filled: their own
    # department, the foundation subjects, or general education.
    fallback_pool = {m: sorted(c for c in dept
                               if dept[c] == m or dept[c] in ("MTH", "PHY", "CHM", "EGR", "HUM", "SOC"))
                     for m in plan}

    grade_rows = cur.execute("SELECT cd_grade, letter_grade FROM cd_grade ORDER BY cd_grade").fetchall()
    grades = [g for g, _ in grade_rows]
    weights = [GRADE_WEIGHTS.get(letter, 0) for _, letter in grade_rows]
    fail_code = next((g for g, letter in grade_rows if letter == "F"), None)

    def seats_left(catnum, sem):
        return sum(o["cap"] - o["taken"] for o in offerings.get((catnum, sem), []))

    def seat(catnum, sem, chosen):
        """The emptiest section of this course that fits the student's week."""
        free = [o for o in offerings.get((catnum, sem), [])
                if o["taken"] < o["cap"] and not any(_clash(o, c) for c in chosen)]
        return max(free, key=lambda o: o["cap"] - o["taken"]) if free else None

    def prereqs_met(catnum, passed, this_term):
        for p, kind in prereq.get(catnum, []):
            if p in passed or (kind == "coreq" and p in this_term):
                continue
            return False
        return True

    # Everyone's standing, carried from one semester to the next.
    state = {}
    for student_id, major, class_year in cur.execute(
            "SELECT student_id, cd_major, class_year FROM student ORDER BY student_id").fetchall():
        if major not in plan:
            continue
        passed = set()
        for term in range(1, 9):
            if class_year - 4 + (term - 1) // 2 < first_ay:
                # Before the record begins: it happened, it just isn't in here.
                passed.update(c for t, rtype, c, _ in plan[major] if t == term and rtype == "COURSE" and c)
        state[student_id] = {"major": major, "class_year": class_year, "passed": passed, "pending": [],
                             "required": {c for _, rtype, c, _ in plan[major] if rtype == "COURSE" and c},
                             "last_sem": None, "last_term": None}

    rows, misses, short_terms, total_terms = [], Counter(), 0, 0
    for ay, spring, sem in semesters:
        roster = []
        for student_id, st in state.items():
            term = (ay - (st["class_year"] - 4)) * 2 + 1 + spring
            # A fifth year, but only for someone who was here and still owes a
            # required course: usually a capstone that slipped behind its
            # prerequisites, since Senior Design I runs only in the fall.
            fifth_year = (term in (9, 10) and st["last_term"] is not None
                          and not st["required"] <= st["passed"])
            if 1 <= term <= 8 or fifth_year:
                roster.append((term, student_id))
        rng.shuffle(roster)
        roster.sort(key=lambda r: -r[0])        # seniors register first

        # Each term registers in three passes, the way priority registration works:
        # everyone's required courses first, then electives, then anything to fill a
        # gap. One pass per student let a senior's filler course take the seat a
        # freshman needed for Calculus I, and every course behind it slipped too.
        reg = {}
        for term, student_id in roster:
            st = state[student_id]
            want = list(st["pending"]) + [c for t, rtype, c, _ in plan[st["major"]]
                                          if t == term and rtype == "COURSE" and c]
            want = [c for c in dict.fromkeys(want) if c not in st["passed"]]
            if term > 8:
                want = [c for c in want if c in st["required"]]   # only what they still owe
            want.sort(key=lambda c: len(offerings.get((c, sem), [])))   # hardest to place first
            reg[student_id] = {
                "term": term, "named": want, "chosen": [], "catnums": set(), "rows": [], "pending": [],
                "electives": [pool for t, rtype, _, pool in plan[st["major"]] if t == term and rtype == "ELECTIVE"],
            }

        def take(student_id, catnum, offering):
            r = reg[student_id]
            offering["taken"] += 1
            r["chosen"].append(offering)
            r["catnums"].add(catnum)
            row = [student_id, catnum, sem, offering["id"]]
            rows.append(row)
            r["rows"].append(row)

        # Pass 1: what the plan names for this term, plus anything carried over.
        for term, student_id in roster:
            r, passed = reg[student_id], state[student_id]["passed"]
            for c in r["named"]:
                if len(r["chosen"]) >= 4:
                    r["pending"].append(c)
                    continue
                if not prereqs_met(c, passed, r["catnums"]):
                    misses["prerequisite not met"] += 1
                elif not offerings.get((c, sem)):
                    misses["not offered that term"] += 1
                else:
                    offering = seat(c, sem, r["chosen"])
                    if offering is not None:
                        take(student_id, c, offering)
                        continue
                    full = all(o["taken"] >= o["cap"] for o in offerings[(c, sem)])
                    misses["every section full" if full else "clashed with another class"] += 1
                r["pending"].append(c)                 # try again next term

        # Pass 2: the plan's elective slots.
        for term, student_id in roster:
            r, st = reg[student_id], state[student_id]
            passed = st["passed"]
            for pool_kind in r["electives"]:
                if len(r["chosen"]) >= 4:
                    break
                pool = gened_pool if pool_kind == "gened" else major_pool[st["major"]]
                candidates = [c for c in pool
                              if c not in passed and c not in r["catnums"]
                              and offerings.get((c, sem)) and prereqs_met(c, passed, r["catnums"])]
                rng.shuffle(candidates)
                candidates.sort(key=lambda c: -seats_left(c, sem))
                for c in candidates[:15]:
                    offering = seat(c, sem, r["chosen"])
                    if offering is not None:
                        take(student_id, c, offering)
                        break
                else:
                    misses["no elective with a free seat"] += 1

        # Pass 3: anyone still short takes something else they are eligible for.
        for term, student_id in roster:
            r, st = reg[student_id], state[student_id]
            if len(r["chosen"]) >= 4 or r["term"] > 8:
                continue                                   # a fifth-year student takes only what they owe
            passed = st["passed"]
            year_level = min(4, (term + 1) // 2)
            spare = [c for c in fallback_pool[st["major"]]
                     if c not in passed and c not in r["catnums"]
                     and level[c] <= year_level + 1
                     and offerings.get((c, sem)) and prereqs_met(c, passed, r["catnums"])]
            rng.shuffle(spare)
            spare.sort(key=lambda c: -seats_left(c, sem))
            for c in spare:
                if len(r["chosen"]) >= 4:
                    break
                offering = seat(c, sem, r["chosen"])
                if offering is not None:
                    take(student_id, c, offering)

        # Grades, and what carries into next term.
        for term, student_id in roster:
            r, st = reg[student_id], state[student_id]
            for row in r["rows"]:
                catnum = row[1]
                if sem == current_semester:
                    row.append(None)                   # in progress, no grade yet
                    st["passed"].add(catnum)
                    continue
                g = grade_rng.choices(grades, weights=weights)[0]
                row.append(g)
                if g == fail_code:
                    r["pending"].append(catnum)        # a real retake: they failed it
                else:
                    st["passed"].add(catnum)
            st["pending"] = [c for c in dict.fromkeys(r["pending"]) if c not in st["passed"]]
            if r["rows"]:
                st["last_sem"], st["last_term"] = sem, term
            if term <= 8:
                total_terms += 1
                if len(r["chosen"]) < 4:
                    short_terms += 1

    # Where each student ended up, read off their own transcript.
    cur_ay, cur_spring = next((ay, sp) for ay, sp, sid in semesters if sid == current_semester)
    status_rows, tally = [], Counter()
    for student_id, st in state.items():
        # Which of their own terms is "now". Anyone at or before term 10 who has
        # not finished is still working on it, even if they are not in a class
        # this semester: Senior Design II only runs in the spring.
        now_term = (cur_ay - (st["class_year"] - 4)) * 2 + 1 + cur_spring
        if st["last_sem"] == current_semester:
            status, grad_sem, active = "enrolled", None, 1
        elif st["last_sem"] is not None and st["required"] <= st["passed"]:
            status = "graduated late" if (st["last_term"] or 0) > 8 else "graduated"
            grad_sem, active = st["last_sem"], 0
        elif now_term <= 10:
            status, grad_sem, active = "enrolled", None, 1
        else:
            status, grad_sem, active = "did not complete", None, 0
        tally[status] += 1
        status_rows.append((status, grad_sem, active, student_id))
    conn.executemany(
        "UPDATE student SET degree_status = ?, graduated_semester_id = ?, active_flag = ? "
        "WHERE student_id = ?", status_rows)
    print("  degree status: " + " · ".join(f"{k} {v:,}" for k, v in tally.most_common()))

    rows.sort(key=lambda r: (r[0], r[2], r[1]))    # student, semester, course: reads like a transcript
    conn.executemany(
        "INSERT INTO student_enrollment (student_id, catnum, semester_id, offering_id, cd_grade) "
        "VALUES (?,?,?,?,?)", rows)
    conn.commit()
    if short_terms:
        print(f"  {short_terms:,} of {total_terms:,} student-terms came up short of four courses "
              f"({short_terms / total_terms:.1%}); plan slots that slipped:")
        for reason, n in misses.most_common():
            print(f"     {n:>6,}  {reason}")
    return len(rows)


def _clear_database(conn: sqlite3.Connection) -> None:
    """Drop every user table and view, including ones the schema script doesn't know about."""
    conn.execute("PRAGMA foreign_keys = OFF")
    objects = conn.execute(
        "SELECT type, name FROM sqlite_master "
        "WHERE type IN ('view', 'table') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type = 'table'"  # views first
    ).fetchall()
    for kind, name in objects:
        conn.execute(f'DROP {kind.upper()} IF EXISTS "{name}"')
    conn.commit()
    conn.execute("VACUUM")


def main():
    parser = argparse.ArgumentParser(description="Build the Kuromaku U SQLite database from the CSVs.")
    parser.add_argument("--data",  default=str(DEFAULT_DATA_DIR), help="Path to data directory")
    parser.add_argument("--db",    default=str(DEFAULT_DB_PATH),  help="Output SQLite file path")
    parser.add_argument("--seed",  type=int, default=1729,        help="RNG seed for synthetic enrollments")
    args = parser.parse_args()

    data_dir = Path(args.data)
    db_path  = Path(args.db)

    # Rebuild in place rather than deleting the file. A deleted-and-recreated
    # .db is a new inode, and a client already connected to it (RazorSQL) stays
    # on the old one and keeps showing old numbers until it reconnects. Emptying
    # the same file means a refresh is enough.
    print(f"Building {db_path} from {data_dir}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        _clear_database(conn)
    except sqlite3.OperationalError as e:
        sys.exit(f"Can't clear {db_path}: {e}. Close any open query or transaction in RazorSQL and rerun.")
    conn.execute("PRAGMA foreign_keys = ON")

    print(f"Applying schema {SCHEMA_SQL}")
    with open(SCHEMA_SQL) as f:
        conn.executescript(f.read())

    print("Loading tables:")
    total = 0
    for table, csv_name, cols in LOAD_PLAN:
        n = load_table(conn, data_dir, table, csv_name, cols)
        print(f"  {table:<22} {n:>7,} rows")
        total += n
    print(f"  ----------------------------")
    print(f"  loaded                {total:>7,} rows")

    print("Generating synthetic enrollments…")
    enrollments = generate_enrollments(conn, seed=args.seed)
    print(f"  student_enrollment    {enrollments:>7,} rows  (seed={args.seed})")

    print("Sanity checks…")
    problems = sanity_check(conn)
    if problems:
        print("  ⚠  THIS DATABASE WILL EMBARRASS YOU ON CAMERA:")
        for pr in problems:
            print(f"     - {pr}")
    else:
        print("  all clear — current semester, class ages and attendance windows agree")

    conn.execute("ANALYZE")
    conn.close()
    print(f"\n✓ Done. Database written to {db_path}")
    print(f"  Size: {db_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
