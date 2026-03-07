import json
import requests

PATH = r"grafana_dashboards/active/acm_master_complete.json"

with open(PATH, "r", encoding="utf-8") as f:
    dash = json.load(f)

patched = 0
for p in dash.get("panels", []):
    title = p.get("title", "")
    if title in ("Health Zone", "Defect Status"):
        ro = p.setdefault("options", {}).setdefault("reduceOptions", {})
        ro["fields"] = "/.+/"   # matches all non-empty field names incl. strings
        ro["calcs"] = ["last"]
        ro["values"] = False
        p["options"]["textMode"] = "value"
        p.setdefault("fieldConfig", {}).setdefault("defaults", {}).pop("noValue", None)
        print("Patched:", title, "  ->  fields =", ro["fields"])
        patched += 1

print("Patched", patched, "panels")

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)

resp = requests.post(
    "http://127.0.0.1:3000/api/admin/provisioning/dashboards/reload",
    auth=("admin", "admin")
)
print("Reload:", resp.status_code, resp.text)
