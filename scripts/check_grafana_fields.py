"""
Queries the MSSQL datasource via Grafana API to see exactly what field types
are returned for the Health Zone stat panel query. This reveals why the stat
panel shows 'No data' even though SQL returns a row.
"""
import requests
import json

payload = {
    "queries": [{
        "refId": "A",
        "datasource": {"type": "mssql", "uid": "mssql-ds"},
        "rawSql": "SELECT TOP 1 HealthZone FROM dbo.ACM_HealthTimeline WHERE EquipID = 5000 ORDER BY Timestamp DESC",
        "format": "table",
        "rawQuery": True,
    }],
    "from": "1659292200000",
    "to": "1693506600000"
}

resp = requests.post(
    "http://127.0.0.1:3000/api/ds/query?ds_type=mssql&requestId=Q1",
    auth=("admin", "admin"),
    headers={"Content-Type": "application/json"},
    json=payload,
    timeout=15
)

print("Status:", resp.status_code)
result = resp.json()
frames = result.get("results", {}).get("A", {}).get("frames", [])
print("Frames returned:", len(frames))
for i, fr in enumerate(frames):
    schema = fr.get("schema", {})
    data = fr.get("data", {})
    fields = schema.get("fields", [])
    print(f"Frame {i}:")
    for f in fields:
        print(f"  field name={f['name']!r} type={f.get('type')!r} typeInfo={f.get('typeInfo')!r}")
    print(f"  values: {data.get('values')}")
