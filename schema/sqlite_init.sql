-- Kuromaku University — SQLite schema
-- Translated from the canonical Postgres DDL in schema/postgres/create_all_tables.sql
-- SQLite uses TEXT for char/varchar/date/timestamp; INTEGER for bool (0/1); REAL for decimal.

DROP TABLE IF EXISTS student_enrollment;
DROP TABLE IF EXISTS building_distance;
DROP TABLE IF EXISTS student_address;
DROP TABLE IF EXISTS student;
DROP TABLE IF EXISTS program_requirement;
DROP TABLE IF EXISTS program;
DROP TABLE IF EXISTS course_prerequisite;
DROP TABLE IF EXISTS course_catalog;
DROP TABLE IF EXISTS department;
DROP TABLE IF EXISTS semester;
DROP TABLE IF EXISTS building;
DROP TABLE IF EXISTS class_year;
DROP TABLE IF EXISTS cd_building_type;
DROP TABLE IF EXISTS cd_country;
DROP TABLE IF EXISTS cd_state;
DROP TABLE IF EXISTS cd_ethnicity;
DROP TABLE IF EXISTS cd_major;
DROP TABLE IF EXISTS cd_minor;
DROP TABLE IF EXISTS cd_grade;

CREATE TABLE class_year (
  class_year        INTEGER PRIMARY KEY,
  class_short_name  TEXT NOT NULL,
  class_name        TEXT NOT NULL,
  is_alumni         INTEGER,
  sort_order        REAL
);

CREATE TABLE cd_building_type (
  cd_building_type   INTEGER PRIMARY KEY,
  name_building_type TEXT,
  sort_order         REAL
);

CREATE TABLE cd_ethnicity (
  cd_ethnicity   TEXT PRIMARY KEY,
  name_ethnicity TEXT,
  sort_order     REAL
);

CREATE TABLE cd_major (
  cd_major   TEXT PRIMARY KEY,
  name_major TEXT,
  sort_order REAL
);

CREATE TABLE cd_minor (
  cd_minor   TEXT PRIMARY KEY,
  name_minor TEXT,
  sort_order REAL
);

CREATE TABLE cd_grade (
  cd_grade      INTEGER PRIMARY KEY,
  letter_grade  TEXT,
  numeric_grade REAL
);

CREATE TABLE cd_country (
  cd_country   TEXT PRIMARY KEY,
  name_country TEXT,
  sort_order   REAL
);

CREATE TABLE cd_state (
  cd_state                TEXT PRIMARY KEY,
  name_state              TEXT,
  fips                    INTEGER,
  standard_federal_region TEXT,
  census_region           INTEGER,
  census_region_name      TEXT,
  census_division         INTEGER,
  census_division_name    TEXT,
  circuit_court           INTEGER,
  sort_order              REAL
);

CREATE TABLE building (
  building_id      TEXT PRIMARY KEY,
  name             TEXT,
  cd_building_type INTEGER,
  centroid_x       REAL,
  centroid_y       REAL,
  FOREIGN KEY (cd_building_type) REFERENCES cd_building_type(cd_building_type)
);

CREATE TABLE building_distance (
  row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id         TEXT NOT NULL,
  target_building_id  TEXT NOT NULL,
  distance_in_meters  REAL,
  FOREIGN KEY (building_id)        REFERENCES building(building_id),
  FOREIGN KEY (target_building_id) REFERENCES building(building_id)
);

CREATE TABLE semester (
  semester_id          INTEGER PRIMARY KEY,
  semester_name        TEXT NOT NULL,
  academic_year_start  INTEGER NOT NULL,
  academic_year_end    INTEGER NOT NULL,
  semester_start_date  TEXT NOT NULL,
  semester_end_date    TEXT NOT NULL,
  is_current           INTEGER NOT NULL
);

-- Departments that own courses. In v1 the catalog's department code pointed at
-- cd_major, so the eight CORE courses were the database's only orphaned key —
-- and the foundation subjects (math, physics, chemistry, humanities) had nowhere
-- to live, because they aren't majors.
CREATE TABLE department (
  cd_department     TEXT PRIMARY KEY,
  catnum_prefix     TEXT NOT NULL,
  name_department   TEXT NOT NULL,
  dept_kind         TEXT,     -- engineering | foundation | general education
  offers_major      INTEGER,  -- 1 if a student can major in it
  sort_order        REAL
);

CREATE TABLE course_catalog (
  catnum            TEXT PRIMARY KEY,
  cd_major_minor    TEXT REFERENCES department(cd_department),
  course_title      TEXT,
  course_desc       TEXT,
  course_type       TEXT,
  units             INTEGER,
  course_level      INTEGER,  -- 1-4: the year the course is pitched at, and the
                              -- first digit of catnum. In v1 the level was
                              -- arbitrary and the numbering alphabetical.
  active_flag       INTEGER
);

CREATE INDEX ix_course_catalog_dept  ON course_catalog(cd_major_minor);
CREATE INDEX ix_course_catalog_level ON course_catalog(course_level);

-- The degree each major grants, and the plan that gets a student there.
CREATE TABLE program (
  cd_major          TEXT PRIMARY KEY REFERENCES cd_major(cd_major),
  degree_name       TEXT NOT NULL,
  total_units       INTEGER,
  terms             INTEGER
);

-- One row per slot in the plan: 4 a term, 8 terms, 32 slots. A slot is either a
-- named course or an elective drawn from a pool. This is what the enrollment
-- generator walks, instead of picking courses at random the way v1 did.
CREATE TABLE program_requirement (
  cd_major          TEXT NOT NULL REFERENCES program(cd_major),
  term              INTEGER NOT NULL,   -- 1-8
  slot              INTEGER NOT NULL,   -- 1-4 within the term
  requirement_type  TEXT NOT NULL,      -- COURSE | ELECTIVE
  requirement_block TEXT NOT NULL,      -- engineering core | math and science |
                                        -- general education | major | major elective
  catnum            TEXT REFERENCES course_catalog(catnum),  -- COURSE only
  pool_kind         TEXT,               -- ELECTIVE only: gened | major_elective
  pool_min_level    INTEGER,
  units             INTEGER,
  PRIMARY KEY (cd_major, term, slot)
);

CREATE INDEX ix_program_requirement_catnum ON program_requirement(catnum);

-- What a student must have taken before (or alongside) a course. A lab is a
-- coreq of its lecture; everything else is a prereq.
CREATE TABLE course_prerequisite (
  catnum            TEXT NOT NULL REFERENCES course_catalog(catnum),
  prereq_catnum     TEXT NOT NULL REFERENCES course_catalog(catnum),
  requirement       TEXT NOT NULL,   -- prereq | coreq
  PRIMARY KEY (catnum, prereq_catnum)
);

CREATE TABLE student (
  student_id       INTEGER PRIMARY KEY,
  first_name       TEXT NOT NULL,
  last_name        TEXT NOT NULL,
  email            TEXT,
  school_email     TEXT,
  gender           TEXT,
  dob              TEXT,
  class_year       INTEGER NOT NULL,
  grad_year        INTEGER,
  cd_ethnicity     TEXT,
  cd_major         TEXT,
  cd_minor         TEXT,
  campus_phone     TEXT,
  cell_phone       TEXT,
  student_photo    TEXT,
  active_flag      INTEGER,
  FOREIGN KEY (class_year)   REFERENCES class_year(class_year),
  FOREIGN KEY (cd_ethnicity) REFERENCES cd_ethnicity(cd_ethnicity),
  FOREIGN KEY (cd_major)     REFERENCES cd_major(cd_major),
  FOREIGN KEY (cd_minor)     REFERENCES cd_minor(cd_minor)
);
CREATE INDEX ix_student_last_name  ON student(last_name);
CREATE INDEX ix_student_major      ON student(cd_major);
CREATE INDEX ix_student_class_year ON student(class_year);

CREATE TABLE student_address (
  row_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id  INTEGER NOT NULL,
  address_1   TEXT,
  address_2   TEXT,
  city        TEXT,
  cd_state    TEXT,
  province    TEXT,
  zip_code    TEXT,
  postal_code TEXT,
  cd_country  TEXT,
  active_flag INTEGER,
  FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (cd_state)   REFERENCES cd_state(cd_state),
  FOREIGN KEY (cd_country) REFERENCES cd_country(cd_country)
);
CREATE INDEX ix_student_address_student ON student_address(student_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- student_enrollment — synthetic. Generated by build_db.py with a fixed RNG seed
-- so the dataset is reproducible. Provides the student↔course join the rest of
-- the v1 schema was missing. Used by the MCP server demo for "who's in Econ 101"
-- style queries.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE student_enrollment (
  row_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id   INTEGER NOT NULL,
  catnum       TEXT NOT NULL,
  semester_id  INTEGER NOT NULL,
  cd_grade     INTEGER,        -- null if course is in-progress (current semester)
  FOREIGN KEY (student_id)  REFERENCES student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (catnum)      REFERENCES course_catalog(catnum),
  FOREIGN KEY (semester_id) REFERENCES semester(semester_id),
  FOREIGN KEY (cd_grade)    REFERENCES cd_grade(cd_grade)
);
CREATE INDEX ix_enrollment_student  ON student_enrollment(student_id);
CREATE INDEX ix_enrollment_catnum   ON student_enrollment(catnum);
CREATE INDEX ix_enrollment_semester ON student_enrollment(semester_id);
