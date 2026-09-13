"""Stage D, part 1: the classes of 2020-2026, so the seven-year history has people in it.

1,750 alumni across seven cohorts, drawn from the same name, ethnicity, major and
geography pools as the current students. Appends to ku_student.csv,
ku_student_address.csv and ku_class_year.csv; existing rows are untouched.
"""
import csv, random, re, sys
from collections import Counter
from pathlib import Path

REPO = Path("/Users/jmilbery/Kuromaku-U/.claude/worktrees/v2")
D = REPO / "data"
# Cohorts come from the command line (default 2020-2026). Re-running is safe:
# a class year already in the student table is skipped, never duplicated.
COHORTS = [int(y) for y in sys.argv[1:]] or list(range(2020, 2027))
rng = random.Random(90210 + min(COHORTS))
PER_COHORT = 250


def read(name):
    with open(D / name, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        return next(r), list(r)


shdr, srows = read("ku_student.csv")
ahdr, arows = read("ku_student_address.csv")
chdr, crows = read("ku_class_year.csv")
si = {c: i for i, c in enumerate(shdr)}
ai = {c: i for i, c in enumerate(ahdr)}

firsts = [r[si["first_name"]] for r in srows]
lasts = [r[si["last_name"]] for r in srows]
genders = [r[si["gender"]] for r in srows]
ethn = [r[si["ethnicity"]] for r in srows]
majors = [r[si["cd_major"]] for r in srows]
minors = sorted({r[si["cd_minor"]] for r in srows} - {"UND"})
area_codes = [r[si["cell_phone"]][:3] for r in srows]
used_cells = {r[si["cell_phone"]] for r in srows}
used_emails = {r[si["email"]] for r in srows}
used_names = {(r[si["first_name"]], r[si["last_name"]]) for r in srows}

# Street names without their numbers, kept with the city/state/zip they belong to.
streets = []
for r in arows:
    st = re.sub(r"^\d+\s+", "", r[ai["address_1"]])
    streets.append((st, r[ai["city"]], r[ai["cd_state"]], r[ai["province"]],
                    r[ai["zip_code"]], r[ai["postal_code"]], r[ai["cd_country"]]))

next_id = max(int(r[si["student_id"]]) for r in srows) + 1
campus = 6000
present = {int(r[si["class_year"]]) for r in srows}
campus = 6000 + sum(1 for r in srows if r[si["campus_phone"]].startswith("970-111-") and int(r[si["campus_phone"]][-4:]) >= 6000)
new_students, new_addresses = [], []
for klass in [k for k in COHORTS if k not in present]:
    for _ in range(PER_COHORT):
        for _try in range(50):
            first, last = rng.choice(firsts), rng.choice(lasts)
            if (first, last) not in used_names:
                break
        used_names.add((first, last))
        sid = next_id
        next_id += 1
        major = rng.choice(majors)
        minor = rng.choice([m for m in minors if m != major]) if rng.random() < 0.28 else "UND"
        local = f"{first[0].lower()}{last.lower()}{sid}"
        local = re.sub(r"[^a-z0-9]", "", local)
        email = f"{local}@{rng.choice(['example.com', 'example.net', 'example.org'])}"
        while email in used_emails:
            email = f"{local}{rng.randint(2, 99)}@example.com"
        used_emails.add(email)
        area = rng.choice(area_codes)
        for n in range(100):
            cell = f"{area}-555-01{rng.randint(0, 99):02d}"
            if cell not in used_cells:
                break
        used_cells.add(cell)
        born = klass - 22
        dob = f"{rng.randint(1, 12)}/{rng.randint(1, 28)}/{born % 100:02d}"
        row = [""] * len(shdr)
        row[si["student_id"]] = sid
        row[si["first_name"]], row[si["last_name"]] = first, last
        row[si["email"]] = email
        row[si["school_email"]] = f"{last}{sid}@kuromaku-u.org"
        row[si["gender"]] = rng.choice(genders)
        row[si["dob"]] = dob
        row[si["class_year"]] = klass
        row[si["grad_year"]] = klass
        row[si["ethnicity"]] = rng.choice(ethn)
        row[si["cd_major"]], row[si["cd_minor"]] = major, minor
        row[si["campus_phone"]] = f"970-111-{campus}"
        campus += 1
        row[si["cell_phone"]] = cell
        row[si["student_photo"]] = f"{sid}.png"
        row[si["active_flag"]] = "f"          # graduated and gone
        row[si["create_date"]] = f"8/20/{(klass - 4) % 100:02d}"
        row[si["last_update_date"]] = f"5/31/{klass % 100:02d}"
        new_students.append(row)

        st, city, state, province, zipc, postal, country = rng.choice(streets)
        arow = [""] * len(ahdr)
        arow[ai["student_id"]] = sid
        arow[ai["address_1"]] = f"{rng.randint(100, 9899)} {st}"
        arow[ai["city"]], arow[ai["cd_state"]], arow[ai["province"]] = city, state, province
        arow[ai["zip_code"]], arow[ai["postal_code"]], arow[ai["cd_country"]] = zipc, postal, country
        arow[ai["active_flag"]] = "t"
        new_addresses.append(arow)


def append(name, header, rows):
    with open(D / name, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


append("ku_student.csv", shdr, srows + new_students)
append("ku_student_address.csv", ahdr, arows + new_addresses)

ci = {c: i for i, c in enumerate(chdr)}
existing_years = {int(r[ci["class_year"]]) for r in crows}
for klass in sorted(COHORTS, reverse=True):
    if klass in existing_years:
        continue
    row = [""] * len(chdr)
    row[ci["class_year"]] = klass
    row[ci["class_short_name"]] = "AL"
    row[ci["class_name"]] = f"Class of {klass}"
    row[ci["is_alumni"]] = "t"
    row[ci["sort_order"]] = 2031 - klass      # 2026 -> 5 ... 2017 -> 14, after SR=1..FR=4
    row[ci["create_date"]] = "2020-02-05"
    row[ci["last_updated_date"]] = "2020-02-05"
    crows.append(row)
append("ku_class_year.csv", chdr, crows)

if not new_students:
    sys.exit("no new cohorts - every requested class year already exists")
print(f"alumni added {len(new_students)} (ids {new_students[0][si['student_id']]}-{new_students[-1][si['student_id']]}) · "
      f"addresses {len(new_addresses)} · class years now {len(crows)}")
print("by cohort:", dict(sorted(Counter(r[si['class_year']] for r in new_students).items())))
