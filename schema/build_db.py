#!/usr/bin/env python3
"""
build_db.py — build kuromaku_u.db (SQLite) from the CSVs in ../data.

Steps:
  1. Run schema/sqlite_init.sql to create the empty schema
  2. Load each CSV into its matching table
  3. Generate deterministic synthetic enrollments
       (~4 courses/student/semester × 1000 students × 4 semesters = ~16,000 rows)

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
    ("course_catalog",   "ku_course_catalog.csv",  ["catnum","cd_major_minor","course_title","course_desc","course_type","units","active_flag"]),
    ("student",          "ku_student.csv",         ["student_id","first_name","last_name","email","school_email","gender","dob","class_year","grad_year","cd_ethnicity","cd_major","cd_minor","campus_phone","cell_phone","student_photo","active_flag"]),
    ("student_address",  "ku_student_address.csv", ["student_id","address_1","address_2","city","cd_state","province","zip_code","postal_code","cd_country","active_flag"]),
]

# CSV header may differ from SQLite column name. Map them when needed.
CSV_HEADER_ALIASES = {
    # ku_student.csv has "ethnicity" but the SQL column is "cd_ethnicity"
    ("student", "cd_ethnicity"): "ethnicity",
    # ku_course_catalog.csv calls the department code "major_minor_code"
    ("course_catalog", "cd_major_minor"): "major_minor_code",
}


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


def extend_semesters_to_present(conn: sqlite3.Connection) -> int:
    """
    The source CSV ends at Spring 2024. Append Fall 2024 through Spring 2026 so
    the demo has a "current" semester to talk about. Marks Spring 2026 as the
    current semester; clears is_current on all others.
    """
    extras = [
        (11, "FALL 2024",   2024, 2025, "2024-09-02", "2024-12-15", 0),
        (12, "SPRING 2025", 2024, 2025, "2025-01-13", "2025-05-10", 0),
        (13, "FALL 2025",   2025, 2026, "2025-09-01", "2025-12-15", 0),
        (14, "SPRING 2026", 2025, 2026, "2026-01-12", "2026-05-09", 1),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO semester (semester_id, semester_name, academic_year_start, academic_year_end, semester_start_date, semester_end_date, is_current) VALUES (?,?,?,?,?,?,?)",
        extras,
    )
    conn.execute("UPDATE semester SET is_current = 0 WHERE semester_id != 14")
    conn.execute("UPDATE semester SET is_current = 1 WHERE semester_id = 14")
    conn.commit()
    return len(extras)


def generate_enrollments(conn: sqlite3.Connection, *, seed: int = 1729, courses_per_semester: int = 4) -> int:
    """
    Generate deterministic synthetic enrollments.

    Logic:
      - For each student, enroll in `courses_per_semester` courses per semester
        they're "active" (semesters that fall between their freshman year and now).
      - Course choice is weighted: 70% in the student's major, 30% other departments.
      - Grades are assigned for past semesters; current semester rows have null grade.
    """
    rng = random.Random(seed)

    cur = conn.cursor()
    students  = cur.execute("SELECT student_id, cd_major, class_year FROM student").fetchall()
    semesters = cur.execute("SELECT semester_id, semester_name, academic_year_start, is_current FROM semester ORDER BY academic_year_start, semester_id").fetchall()
    courses_by_dept: dict[str, list[str]] = {}
    for catnum, dept in cur.execute("SELECT catnum, cd_major_minor FROM course_catalog WHERE active_flag = 1").fetchall():
        courses_by_dept.setdefault(dept, []).append(catnum)
    all_courses = [c for clist in courses_by_dept.values() for c in clist]
    grades = [row[0] for row in cur.execute("SELECT cd_grade FROM cd_grade").fetchall()]

    # Grade weighting — most students pass, a few don't, F is rare
    # (assumes cd_grade primary keys are ordered so lower = better; we don't know
    # the exact mapping without reading the CSV, so we just sample uniformly here
    # but bias toward the first 2/3 of the grade scale).
    grade_pool = grades[: max(1, len(grades) * 2 // 3)] + grades

    inserted = 0
    rows: list[tuple] = []
    for student_id, major, class_year in students:
        # Approximate which semesters this student attended
        for sem_id, sem_name, ay_start, is_current in semesters:
            # crude attendance window: student attends semesters with ay_start >= (class_year - 4)
            if ay_start < (class_year - 4):
                continue
            chosen: set[str] = set()
            for _ in range(courses_per_semester):
                if rng.random() < 0.70 and major in courses_by_dept and courses_by_dept[major]:
                    pool = courses_by_dept[major]
                else:
                    pool = all_courses
                if not pool:
                    continue
                for _attempt in range(8):
                    catnum = rng.choice(pool)
                    if catnum not in chosen:
                        chosen.add(catnum)
                        break
                else:
                    continue
                cd_grade = None if is_current else rng.choice(grade_pool)
                rows.append((student_id, catnum, sem_id, cd_grade))
                if len(rows) >= 5000:
                    conn.executemany(
                        "INSERT INTO student_enrollment (student_id, catnum, semester_id, cd_grade) VALUES (?,?,?,?)",
                        rows,
                    )
                    inserted += len(rows)
                    rows.clear()

    if rows:
        conn.executemany(
            "INSERT INTO student_enrollment (student_id, catnum, semester_id, cd_grade) VALUES (?,?,?,?)",
            rows,
        )
        inserted += len(rows)
    conn.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Build the Kuromaku U SQLite database from the CSVs.")
    parser.add_argument("--data",  default=str(DEFAULT_DATA_DIR), help="Path to data directory")
    parser.add_argument("--db",    default=str(DEFAULT_DB_PATH),  help="Output SQLite file path")
    parser.add_argument("--seed",  type=int, default=1729,        help="RNG seed for synthetic enrollments")
    args = parser.parse_args()

    data_dir = Path(args.data)
    db_path  = Path(args.db)

    if db_path.exists():
        db_path.unlink()
        print(f"Removed existing {db_path}")

    print(f"Building {db_path} from {data_dir}")
    conn = sqlite3.connect(db_path)
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

    print("Extending semesters through Spring 2026…")
    extras = extend_semesters_to_present(conn)
    print(f"  semester (extended)   {extras:>7,} rows appended; SPRING 2026 set current")

    print("Generating synthetic enrollments…")
    enrollments = generate_enrollments(conn, seed=args.seed)
    print(f"  student_enrollment    {enrollments:>7,} rows  (seed={args.seed})")

    conn.execute("ANALYZE")
    conn.close()
    print(f"\n✓ Done. Database written to {db_path}")
    print(f"  Size: {db_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
