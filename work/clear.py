import sqlite3
conn = sqlite3.connect('plays.db')
rows = conn.execute('SELECT COUNT(*) FROM plays WHERE game_id = "0042500403"').fetchone()
print(f"Total: {rows[0]}")
conn.close()