"""
extract_inserts.py
Reads each SQL file and writes a new file containing ONLY the INSERT statements.
Uses INSERT IGNORE so duplicate primary keys are silently skipped.
"""
import os

# (src_file, dest_file, table_name)
files = [
    ("safety_resources.sql",      "safety_resources_inserts.sql",   "safety_device"),
    ("equipment_complaint.sql",   "equipment_complaint_inserts.sql", "equipment_complaint"),
    ("facility_resources.sql",    "facility_resources_inserts.sql",  "resources"),
]

eqp_file = "eqp-process_resources.sql"
if os.path.exists(eqp_file):
    files.append((eqp_file, "eqp_process_resources_inserts.sql", "resources"))

for src, dst, table in files:
    if not os.path.exists(src):
        print(f"[SKIP] {src} not found")
        continue

    with open(src, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    out_lines = []
    inside_insert = False

    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("INSERT INTO"):
            inside_insert = True
            # KEY CHANGE: INSERT IGNORE skips rows whose primary key already exists
            new_line = line.replace("INSERT INTO", "INSERT IGNORE INTO", 1)
            out_lines.append(new_line)
        elif inside_insert:
            out_lines.append(line)
            if stripped.endswith(";"):
                inside_insert = False
                out_lines.append("\n")

    with open(dst, "w", encoding="utf-8") as f:
        f.write(f"-- INSERT-only import for `{table}`\n")
        f.write("-- INSERT IGNORE: duplicate primary keys are silently skipped.\n\n")
        f.write("SET NAMES utf8mb4;\n")
        f.write("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';\n\n")
        f.writelines(out_lines)

    count = sum(1 for l in out_lines if "INSERT IGNORE" in l.upper())
    print(f"[OK]  {src}  ->  {dst}  ({count} INSERT IGNORE blocks)")

print("\nDone! Re-import the *_inserts.sql files -- no more duplicate key errors.")
