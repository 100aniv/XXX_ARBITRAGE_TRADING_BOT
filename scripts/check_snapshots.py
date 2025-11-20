import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='arbitrage', user='arbitrage', password='arbitrage')
cursor = conn.cursor()
cursor.execute("SELECT snapshot_id, session_id, created_at, loop_count, status FROM session_snapshots ORDER BY created_at DESC LIMIT 10")
print("Recent snapshots:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} @ {row[2]} (loop={row[3]}, status={row[4]})")
