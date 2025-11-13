import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.sql_client import SQLClient

views = [
    'dbo.vw_AnomalyEvents',
    'dbo.vw_Scores',
    'dbo.vw_RunSummary',
]

tables = [
    'dbo.Equipments','dbo.RunLog','dbo.ScoresTS','dbo.DriftTS','dbo.AnomalyEvents',
    'dbo.RegimeEpisodes','dbo.PCA_Model','dbo.PCA_Components','dbo.PCA_Metrics','dbo.RunStats','dbo.ConfigLog'
]

c = SQLClient({}).connect()
cur = c.cursor()
cur.execute('SELECT DB_NAME(), @@SERVERNAME')
db, srv = cur.fetchone()
print(f'CONNECTED server={srv} db={db}')

# Ensure we are using ACM database if it exists
try:
    cur.execute("IF DB_ID('ACM') IS NOT NULL SELECT 1 ELSE SELECT 0")
    exists = cur.fetchone()[0] == 1
    if exists and db != 'ACM':
        cur.execute('USE [ACM]')
        cur.execute('SELECT DB_NAME()')
        db = cur.fetchone()[0]
        print(f'SWITCHED to db={db}')
except Exception as e:
    print(f'WARN: Could not switch DB automatically: {e}')

for v in views:
    cur.execute('SELECT 1 FROM sys.views WHERE object_id = OBJECT_ID(?)', (v,))
    exists = cur.fetchone() is not None
    print(f'{v} exists={exists}')
    if exists:
        try:
            cur.execute(f'SELECT TOP 1 * FROM {v}')
            _ = cur.fetchall()
            print(f'{v} select_ok')
        except Exception as e:
            print(f'{v} select_err={e}')

for t in tables:
    cur.execute('SELECT 1 FROM sys.tables WHERE object_id = OBJECT_ID(?)', (t,))
    texists = cur.fetchone() is not None
    print(f'{t} exists={texists}')

c.close()
