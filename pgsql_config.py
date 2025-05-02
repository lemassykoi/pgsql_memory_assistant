# POSTGRESQL INFOS
PG_USER = 'sql_user'
PG_PASS = 'password'
PG_HOST = '127.0.0.1'
PG_PORT = 5432
PG_DB   = 'memory_db'

# Database connection URI used by app.py
DB_URI = f"postgres://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}?sslmode=disable"
