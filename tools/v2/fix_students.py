"""Tier 1 #4-7 on data/ku_student.csv and schema/postgres/ku_student.sql.

Row order, and every column generate_enrollments() reads, are left untouched.
Byte layout (BOM, LF endings, no trailing newline) is preserved.
"""
import csv, io, random, re, sys
from pathlib import Path

REPO = Path("/Users/jmilbery/Kuromaku-U")
CSV_PATH = REPO / "data/ku_student.csv"
SQL_PATH = REPO / "schema/postgres/ku_student.sql"

raw = CSV_PATH.read_bytes()
assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw
text = raw[3:].decode("utf-8")
trailing_nl = text.endswith("\n")
rows = list(csv.reader(io.StringIO(text)))
header, body = rows[0], rows[1:]
ix = {name: i for i, name in enumerate(header)}

MINORS = ["AER", "CHE", "CIV", "COM", "ENG", "MAN", "MAT", "MEC", "NUC"]
rng = random.Random(1729)

used_phones: set[str] = set()
email_map, phone_map = {}, {}
for r in body:
    sid = r[ix["student_id"]]
    # 5. grad_year: Kuromaku graduates in the spring of the class year.
    r[ix["grad_year"]] = r[ix["class_year"]]
    # 4. ~30% declare a minor, never their own major.
    if rng.random() < 0.30:
        r[ix["cd_minor"]] = rng.choice([m for m in MINORS if m != r[ix["cd_major"]]])
    # 6. email → RFC 2606 reserved domain, local part kept.
    local, domain = r[ix["email"]].split("@")
    tld = domain.rsplit(".", 1)[-1]
    reserved = {"com": "example.com", "net": "example.net", "org": "example.org"}.get(tld)
    if reserved is None:
        reserved = ["example.com", "example.net", "example.org"][sum(map(ord, domain)) % 3]
    new_email = f"{local}@{reserved}"
    email_map[sid] = (r[ix["email"]], new_email)
    r[ix["email"]] = new_email
    # 7. cell → fictional 555-0100..0199, area code kept, unique.
    old = r[ix["cell_phone"]]
    area, xx = old[:3], int(old[-2:])
    for bump in range(100):
        cand = f"{area}-555-01{(xx + bump) % 100:02d}"
        if cand not in used_phones:
            break
    else:
        sys.exit(f"area code {area} exhausted")
    used_phones.add(cand)
    phone_map[sid] = (old, cand)
    r[ix["cell_phone"]] = cand

out = io.StringIO()
csv.writer(out, lineterminator="\n").writerows([header] + body)
new_text = out.getvalue()
if not trailing_nl:
    new_text = new_text.rstrip("\n")
CSV_PATH.write_bytes(b"\xef\xbb\xbf" + new_text.encode("utf-8"))

# Postgres INSERTs: swap the same two fields in place, nothing else.
sql = SQL_PATH.read_text(encoding="utf-8")
lines = sql.split("\n")
hits = 0
for i, line in enumerate(lines):
    m = re.search(r"VALUES \((\d+), ", line)
    if not m:
        continue
    sid = m.group(1)
    (oe, ne), (op, np_) = email_map[sid], phone_map[sid]
    assert line.count(f"'{oe}'") == 1 and line.count(f"'{op}'") == 1, sid
    lines[i] = line.replace(f"'{oe}'", f"'{ne}'").replace(f"'{op}'", f"'{np_}'")
    hits += 1
SQL_PATH.write_text("\n".join(lines), encoding="utf-8")

minors = sum(1 for r in body if r[ix["cd_minor"]] != "UND")
print(f"students {len(body)} · minors {minors} ({minors/len(body):.1%}) · postgres rows {hits}")
