"""Stage C: rooms, instructors, and a conflict-free timetable of course offerings.

Demand is read off the degree plans: each cohort reaches plan term 1..8 in a
known semester, so what a term needs can be sized before any student enrolls.
Sections are then given a room, an instructor and a meeting pattern such that no
room and no instructor is ever double-booked.

Writes data/ku_room.csv, ku_instructor.csv, ku_course_offering.csv.
"""
import csv, json, math, random
from collections import defaultdict
from pathlib import Path

S = Path(__file__).resolve().parent
REPO = Path("/Users/jmilbery/Kuromaku-U/.claude/worktrees/v2")
D = REPO / "data"
rng = random.Random(1729)


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8-sig")))


cat = {r["catnum"]: r for r in rows("ku_course_catalog.csv")}
spec = json.loads((S / "catalog_spec.json").read_text())
depts = {r["cd_department"]: r for r in rows("ku_department.csv")}
semesters = sorted(rows("ku_semester.csv"), key=lambda r: (int(r["academic_year_start"]), r["semester_id"]))
plans = rows("ku_program_requirement.csv")
students = rows("ku_student.csv")
buildings = rows("ku_building.csv")
btypes = {int(r["cd_building_type"]): r["name_building_type"] for r in rows("ku_cd_building_type.csv")}
majors = sorted({r["cd_major"] for r in plans})

# One cohort's worth of each major. Sized per class year, not per student body,
# because only four cohorts are ever in residence at once however many the
# student table holds.
per_class = defaultdict(int)
for s in students:
    per_class[(s["cd_major"], s["class_year"])] += 1
years = {y for _, y in per_class}
cohort = defaultdict(int)
for (m, _), n in per_class.items():
    cohort[m] += n
cohort = {m: max(8, round(n / len(years))) for m, n in cohort.items()}

# ---------------------------------------------------------------- rooms
TEACHING = {"Academic Building", "Computer Lab", "Auditorium", "Library"}
room_rows, rooms = [], []
for b in buildings:
    kind = btypes.get(int(b["cd_building_type"]), "")
    if kind not in TEACHING:
        continue
    plan = []
    if kind == "Academic Building":
        plan = ([("lecture hall", rng.choice([80, 100, 120]))] +
                [("classroom", rng.choice([28, 32, 36, 40])) for _ in range(rng.randint(5, 7))] +
                [("teaching lab", rng.choice([16, 20, 24])) for _ in range(rng.randint(2, 4))])
    elif kind == "Computer Lab":
        plan = [("computer lab", rng.choice([24, 28, 30])) for _ in range(6)]
    elif kind == "Auditorium":
        plan = [("auditorium", rng.choice([150, 200, 250])) for _ in range(2)]
    elif kind == "Library":
        plan = [("seminar room", rng.choice([12, 16, 18])) for _ in range(4)]
    for i, (rtype, capacity) in enumerate(plan):
        floor, n = divmod(i, 6)
        number = f"{floor + 1}{n + 1:02d}"
        room_rows.append([b["building_id"], number, rtype, capacity])
        rooms.append({"b": b["building_id"], "n": number, "type": rtype, "cap": capacity})

# ---------------------------------------------------------------- demand
def parity(sem):          # fall terms carry plan terms 1,3,5,7; spring 2,4,6,8
    return 1 if "FALL" in sem["semester_name"].upper() else 0


# Senior Design I in the fall, II in the spring.
sorted_caps = {}
for m in majors:
    caps = sorted(c for c, v in spec.items() if v["dept"] == m and v["role"] == "capstone")
    if len(caps) == 2:
        sorted_caps[caps[0]], sorted_caps[caps[1]] = "I", "II"


def offered_fixed(catnum, sem):
    role = spec[catnum]["role"]
    if role == "capstone":
        return parity(sem) == (1 if sorted_caps.get(catnum) == "I" else 0)
    c = cat[catnum]
    dept_kind = depts[c["major_minor_code"]]["dept_kind"]
    h = sum(map(ord, catnum))
    if dept_kind in ("foundation", "general education") or role in ("required", "lab"):
        return True
    if int(c["course_level"]) >= 4 and h % 4 == 0:
        return h % 2 == parity(sem) and int(sem["academic_year_start"]) % 2 == h % 2
    return h % 2 == parity(sem)


named_by_major_term = defaultdict(list)
elective_slots = defaultdict(int)
for r in plans:
    t = int(r["term"])
    if r["requirement_type"] == "COURSE":
        named_by_major_term[(r["cd_major"], t)].append(r["catnum"])
    else:
        elective_slots[(r["cd_major"], t, r["pool_kind"])] += 1

gened_pool = [c for c in cat if cat[c]["major_minor_code"] in ("HUM", "SOC")]
major_pool = {}
for m in majors:
    named = {r["catnum"] for r in plans if r["cd_major"] == m and r["catnum"]}
    major_pool[m] = [c for c, v in spec.items()
                     if v["dept"] == m and int(cat[c]["course_level"]) >= 3 and c not in named]

TARGET = {"LEC": 30, "LAB": 18, "IND": 12}
ROOMS_FOR = {"LEC": ("classroom", "lecture hall", "auditorium"),
             "LAB": ("teaching lab", "computer lab"),
             "IND": ("seminar room", "classroom")}

# A term does not offer every elective in a pool - it offers as many as the
# students of that term actually need, and those fill up. Spreading demand across
# the whole pool instead made every elective look empty, so none of them ran and
# students had nothing to take.
GENED_SECTION, MAJEL_SECTION = 26, 20


def pick_pool(candidates, seats, sem_id, per_course):
    if not candidates:
        return []
    k = max(2, math.ceil(seats / per_course))
    ordered = sorted(candidates, key=lambda c: ((sum(map(ord, c)) * 7 + sem_id * 13) % 997, c))
    return ordered[:k]


demand_by_sem, runs_by_sem = {}, {}
for sem in semesters:
    p = parity(sem)
    sem_id = int(sem["semester_id"])
    demand = defaultdict(float)
    runs = {c for c in cat if offered_fixed(c, sem) and spec[c]["role"] != "elective"}
    for m in majors:
        for t in range(1, 9):
            if t % 2 != p:
                continue
            for c in named_by_major_term[(m, t)]:
                demand[c] += cohort[m]
    # General education: one pool, shared by every major.
    gened_seats = sum(cohort[m] * n for (m, t, k), n in elective_slots.items()
                      if k == "gened" and t % 2 == p)
    chosen = pick_pool([c for c in gened_pool if offered_fixed(c, sem)], gened_seats, sem_id, GENED_SECTION)
    for c in chosen:
        demand[c] += gened_seats / len(chosen)
        runs.add(c)
    # Each major's own elective pool.
    for m in majors:
        seats = sum(cohort[mm] * n for (mm, t, k), n in elective_slots.items()
                    if mm == m and k == "major_elective" and t % 2 == p)
        chosen = pick_pool([c for c in major_pool[m] if offered_fixed(c, sem)], seats, sem_id, MAJEL_SECTION)
        for c in chosen:
            demand[c] += seats / len(chosen)
            runs.add(c)
    demand_by_sem[sem_id] = demand
    runs_by_sem[sem_id] = runs

# ---------------------------------------------------------------- instructors
sections_needed = defaultdict(list)      # dept -> sections per semester
for sem in semesters:
    per_dept = defaultdict(int)
    for c in runs_by_sem[int(sem["semester_id"])]:
        d = demand_by_sem[int(sem["semester_id"])].get(c, 0)
        per_dept[cat[c]["major_minor_code"]] += max(1, math.ceil(d * 1.08 / TARGET[cat[c]["course_type"]]))
    for dept in depts:
        sections_needed[dept].append(per_dept.get(dept, 0))

FIRST = ["Alan","Beatrice","Carl","Dana","Edward","Frances","Gordon","Helena","Ian","Judith","Karl","Linda",
         "Martin","Nadia","Oliver","Patricia","Quentin","Rachel","Samuel","Teresa","Ulrich","Vera","Walter",
         "Yvonne","Zachary","Amara","Bogdan","Chiara","Devika","Emeka","Farid","Greta","Hiroshi","Ingrid",
         "Jonas","Kenji","Leilani","Mateo","Nils","Omar","Priya","Rosa","Sanjay","Tomas","Ursula","Viktor",
         "Wanda","Xiulan","Yusuf","Zofia","Clara","Desmond","Elena","Felix","Georgia","Hugo","Irina","Jacob",
         "Katya","Lorenzo","Miriam","Noor","Petra","Rafael","Simone","Tobias"]
LAST = ["Aldridge","Barrow","Castellano","Duffy","Ellington","Fairbanks","Grimaldi","Halloran","Ibarra",
        "Jarvis","Kowalczyk","Lindqvist","Marchetti","Nakagawa","Okonkwo","Pemberton","Quintero","Rasmussen",
        "Sandoval","Thackeray","Underhill","Vasquez","Whitfield","Yamada","Zieliński","Ashworth","Belmonte",
        "Chaudhry","Delacroix","Eriksen","Fontaine","Gallagher","Hargrove","Ivanova","Jorgensen","Kalinski",
        "Lombardi","Mbeki","Novotny","Oyelaran","Pruitt","Rasheed","Stavros","Tanaka","Ueda","Villanueva",
        "Westbrook","Xiong","Yeung","Zabala","Brennan","Cordova","Drummond","Escobar","Faulkner","Grantham",
        "Hollis","Ishikawa","Janowski","Kirkbride","Lefevre","Moreau","Nyberg","Oakes","Petrov","Rademacher",
        "Sorensen","Tillman","Vogel","Wexler"]
RANKS = [("Professor", 26), ("Associate Professor", 24), ("Assistant Professor", 20),
         ("Senior Lecturer", 12), ("Lecturer", 12), ("Adjunct", 6)]
LOAD = {"Professor": 2, "Associate Professor": 2, "Assistant Professor": 2,
        "Senior Lecturer": 3, "Lecturer": 3, "Adjunct": 1}

academic_buildings = [b["building_id"] for b in buildings
                      if btypes.get(int(b["cd_building_type"])) == "Academic Building"]
home_building = {d: academic_buildings[i % len(academic_buildings)] for i, d in enumerate(sorted(depts))}
FIRST_YEAR, LAST_YEAR = int(semesters[0]["academic_year_start"]), int(semesters[-1]["academic_year_start"])

instructors, used_names, used_emails = [], set(), set()
next_id = 5001
for dept in sorted(depts):
    peak = max(sections_needed[dept] or [0])
    base = max(3, math.ceil(peak / 2.2) + 1)   # sized so a typical load is ~2 sections
    extra = math.ceil(base * 0.35)             # the churn rides on top of that
    for k in range(base + extra):
        while True:
            first, last = rng.choice(FIRST), rng.choice(LAST)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break
        rank = rng.choices([r for r, _ in RANKS], weights=[w for _, w in RANKS])[0]
        # The base faculty are here for the whole window, so no term is ever short.
        # Everyone above that number is either a later hire or an earlier departure,
        # which is what makes 2019 look different from 2026.
        hire, end = rng.randint(1988, FIRST_YEAR), None
        if k >= base:
            if rng.random() < 0.5:
                hire = rng.randint(FIRST_YEAR + 1, LAST_YEAR)
            else:
                end = rng.randint(FIRST_YEAR + 1, LAST_YEAR)
        email = f"{first[0].lower()}{last.lower()}@kuromaku-u.org"
        email = email.replace("ń", "n").replace("é", "e")
        while email in used_emails:
            email = f"{first[0].lower()}{last.lower()}{rng.randint(2, 99)}@kuromaku-u.org"
        used_emails.add(email)
        instructors.append({"id": next_id, "first": first, "last": last, "email": email, "dept": dept,
                            "rank": rank, "hire": hire, "end": end,
                            "office_b": home_building[dept], "office_r": f"3{rng.randint(1, 40):02d}",
                            "active": 0 if end else 1})
        next_id += 1
by_dept = defaultdict(list)
for ins in instructors:
    by_dept[ins["dept"]].append(ins)

# ---------------------------------------------------------------- timetable
def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


MWF = [("MWF", t, f"{int(t[:2]):02d}:50") for t in ("08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00")]
TR = [("TR", a, b) for a, b in (("08:00", "09:15"), ("09:30", "10:45"), ("11:00", "12:15"),
                                ("12:30", "13:45"), ("14:00", "15:15"), ("15:30", "16:45"))]
LAB_SLOTS = [(d, a, b) for d in ("M", "T", "W", "R") for a, b in (("13:00", "16:00"),)] + \
            [(d, "09:00", "12:00") for d in ("T", "R")] + [("F", "13:00", "16:00")]
IND_SLOTS = [("F", "13:00", "14:50"), ("F", "15:00", "16:50"), ("W", "13:00", "14:50"),
             ("M", "16:00", "17:50"), ("T", "16:00", "17:50"), ("W", "16:00", "17:50"),
             ("R", "16:00", "17:50")]
SLOTS = {"LEC": MWF + TR, "LAB": LAB_SLOTS, "IND": IND_SLOTS}


def clash(a, b):
    if not set(a[0]) & set(b[0]):
        return False
    return mins(a[1]) < mins(b[2]) and mins(b[1]) < mins(a[2])


CONFLICTS = {}
ALL_SLOTS = MWF + TR + LAB_SLOTS + IND_SLOTS
for s1 in ALL_SLOTS:
    CONFLICTS[s1] = {s2 for s2 in ALL_SLOTS if clash(s1, s2)}

offering_rows, unplaced = [], []
offering_id = 100001
for sem in semesters:
    year = int(sem["academic_year_start"])
    room_busy = defaultdict(set)        # (building, room) -> slots
    instr_busy = defaultdict(set)       # instructor_id -> slots
    instr_load = defaultdict(int)
    demand = demand_by_sem[int(sem["semester_id"])]
    wanted = []
    for c in sorted(runs_by_sem[int(sem["semester_id"])]):
        d = demand.get(c, 0)
        ctype = cat[c]["course_type"]
        n = max(1, math.ceil(d * 1.08 / TARGET[ctype])) if d >= 3 else 1
        seats = max(12, math.ceil(max(d, 8) * 1.3 / n))
        wanted.append((c, n, seats, ctype))
    # Biggest first: the hard-to-place sections get the pick of the rooms.
    wanted.sort(key=lambda w: (-w[2], w[0]))
    for c, n, seats, ctype in wanted:
        dept = cat[c]["major_minor_code"]
        faculty = [i for i in by_dept[dept] if i["hire"] <= year and (i["end"] is None or i["end"] >= year)]
        if not faculty:
            faculty = [i for i in by_dept[dept]]
        candidates = [r for r in rooms if r["type"] in ROOMS_FOR[ctype] and r["cap"] >= seats]
        if ctype == "LAB":
            # Computer science labs in computer labs, everyone else's in teaching
            # labs: a physics lab does not belong in the computer lab building.
            want = "computer lab" if cat[c]["major_minor_code"] == "COM" else "teaching lab"
            candidates = [r for r in candidates if r["type"] == want] or candidates
        candidates.sort(key=lambda r: r["cap"])
        for sec in range(1, n + 1):
            slot_order = SLOTS[ctype][:]
            rng.shuffle(slot_order)
            placed = False
            for slot in slot_order:
                free_faculty = [i for i in faculty
                                if instr_load[i["id"]] < LOAD[i["rank"]]
                                and not (CONFLICTS[slot] & instr_busy[i["id"]])]
                if not free_faculty:
                    continue
                # Fill an instructor's load before starting another one, so the
                # roster reads like a real department: most carry two sections.
                free_faculty.sort(key=lambda i: (-instr_load[i["id"]], i["id"]))
                room = next((r for r in candidates
                             if not (CONFLICTS[slot] & room_busy[(r["b"], r["n"])])), None)
                if room is None:
                    continue
                ins = free_faculty[0]
                room_busy[(room["b"], room["n"])].add(slot)
                instr_busy[ins["id"]].add(slot)
                instr_load[ins["id"]] += 1
                offering_rows.append([offering_id, c, sem["semester_id"], f"{sec:02d}", ins["id"],
                                      room["b"], room["n"], min(seats, room["cap"]),
                                      slot[0], slot[1], slot[2]])
                offering_id += 1
                placed = True
                break
            if not placed:
                unplaced.append((sem["semester_name"], c, sec))

# ---------------------------------------------------------------- write
def write(name, header, data):
    with open(D / name, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(data)


write("ku_room.csv", ["building_id", "room_number", "room_type", "capacity"], room_rows)
write("ku_instructor.csv",
      ["instructor_id", "first_name", "last_name", "email", "cd_department", "rank_title",
       "hire_year", "end_year", "office_building_id", "office_room", "active_flag"],
      [[i["id"], i["first"], i["last"], i["email"], i["dept"], i["rank"], i["hire"],
        i["end"] or "", i["office_b"], i["office_r"], i["active"]] for i in instructors])
write("ku_course_offering.csv",
      ["offering_id", "catnum", "semester_id", "section_number", "instructor_id", "building_id",
       "room_number", "capacity", "meeting_days", "start_time", "end_time"], offering_rows)

per_sem = defaultdict(int)
for r in offering_rows:
    per_sem[r[2]] += 1
print(f"rooms {len(room_rows)} in {len({r[0] for r in room_rows})} buildings · "
      f"instructors {len(instructors)} · offerings {len(offering_rows)}")
print(f"sections per semester: min {min(per_sem.values())} max {max(per_sem.values())} "
      f"mean {sum(per_sem.values()) / len(per_sem):.0f}")
print(f"unplaced sections: {len(unplaced)}")
for u in unplaced[:10]:
    print("   ", u)
