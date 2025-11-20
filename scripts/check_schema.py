import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='arbitrage', user='arbitrage', password='arbitrage')
cursor = conn.cursor()
cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='session_snapshots'")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")
