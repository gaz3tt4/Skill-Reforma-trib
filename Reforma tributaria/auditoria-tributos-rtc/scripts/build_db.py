"""Aplica os scripts flyway da calculadora RTC num SQLite local."""
import re
import sqlite3
import sys
from pathlib import Path

repo = Path(sys.argv[1])
out = Path(sys.argv[2])
sql_dir = repo / "flyway" / "sql"
out.unlink(missing_ok=True)
con = sqlite3.connect(out)

def ver(p):
    m = re.match(r"[BV](\d+)__", p.name)
    return int(m.group(1)) if m else 0

files = [sql_dir / "criacao" / "beforeMigrate.sql"]
files += sorted(list((sql_dir / "criacao").glob("B0*.sql")) + list((sql_dir / "manutencao").glob("V*.sql")), key=ver)
files += [sql_dir / "criacao" / "afterMigrate.sql"]
for f in files:
    txt = f.read_text(encoding="utf-8-sig")
    txt = re.sub(r"\$\{[^}]+\}", "''", txt)
    txt = re.sub(r"(?i)PRAGMA\s+foreign_keys\s*=\s*ON\s*;", "", txt)
    con.execute("PRAGMA foreign_keys = OFF")
    try:
        con.executescript(txt)
        print("ok  ", f.name)
    except Exception as e:
        print("FAIL", f.name, e)
con.commit()
for (t,) in con.execute("select name from sqlite_master where type='table' order by name"):
    n = con.execute(f'select count(*) from "{t}"').fetchone()[0]
    print(f"{t}: {n}")
