import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.sql_client import SQLClient
from utils.logger import Console

views = [
    'dbo.vw_AnomalyEvents',
    'dbo.vw_Scores',
    'dbo.vw_RunSummary',
]

tables = [
    'dbo.Equipments','dbo.RunLog','dbo.ScoresTS','dbo.DriftTS','dbo.AnomalyEvents',
    'dbo.RegimeEpisodes','dbo.PCA_Model','dbo.PCA_Components','dbo.PCA_Metrics','dbo.RunStats','dbo.ConfigLog'
]

c = SQLClient.from_ini('acm').connect()
cur = c.cursor()
cur.execute('SELECT DB_NAME(), @@SERVERNAME')
db, srv = cur.fetchone()
Console.ok(f'CONNECTED server={srv} db={db}', server=srv, database=db)

# Ensure we are using ACM database if it exists
try:
    cur.execute("IF DB_ID('ACM') IS NOT NULL SELECT 1 ELSE SELECT 0")
    exists = cur.fetchone()[0] == 1
    if exists and db != 'ACM':
        cur.execute('USE [ACM]')
        cur.execute('SELECT DB_NAME()')
        db = cur.fetchone()[0]
        Console.info(f'SWITCHED to db={db}', database=db)
except Exception as e:
    Console.warn(f'WARN: Could not switch DB automatically: {e}', error=str(e))

for v in views:
    cur.execute('SELECT 1 FROM sys.views WHERE object_id = OBJECT_ID(?)', (v,))
    exists = cur.fetchone() is not None
    Console.info(f'{v} exists={exists}', view=v, exists=exists)
    if exists:
        try:
            cur.execute(f'SELECT TOP 1 * FROM {v}')
            _ = cur.fetchall()
            Console.ok(f'{v} select_ok', view=v)
        except Exception as e:
            Console.error(f'{v} select_err={e}', view=v, error=str(e))

for t in tables:
    cur.execute('SELECT 1 FROM sys.tables WHERE object_id = OBJECT_ID(?)', (t,))
    texists = cur.fetchone() is not None
    Console.info(f'{t} exists={texists}', table=t, exists=texists)

c.close()
