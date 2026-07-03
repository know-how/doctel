import sqlite3

conn = sqlite3.connect('localai/db/app.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print('Tables:', tables)
for t in sorted(tables):
    c.execute(f"SELECT * FROM [{t}]")
    rows = c.fetchall()
    print(f'\n=== {t} ({len(rows)} rows) ===')
    # print column names
    c.execute(f"PRAGMA table_info([{t}])")
    cols = [r[1] for r in c.fetchall()]
    print('Columns:', cols)
    for r in rows:
        print(r)
conn.close()
