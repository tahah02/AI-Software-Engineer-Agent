import sqlite3

def wipe_all():
    con = sqlite3.connect('data/aaise.db')
    cur = con.cursor()
    tables = [
        t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if t[0] not in ('alembic_version', 'sqlite_sequence')
    ]
    cur.execute("PRAGMA foreign_keys = OFF;")
    for table in tables:
        cur.execute(f"DELETE FROM {table};")
    try:
        cur.execute("DELETE FROM sqlite_sequence;")
    except Exception:
        pass
    con.commit()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("VACUUM;")
    con.close()
    print("Database aaise.db completely wiped clean! (All tables reset to 0 rows)")

if __name__ == '__main__':
    wipe_all()
