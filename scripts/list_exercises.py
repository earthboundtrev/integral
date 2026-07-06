import json
from pathlib import Path

for f in sorted(Path("progression/seed/v1").glob("*.json")):
    if f.name == "cross_links.json":
        continue
    d = json.loads(f.read_text(encoding="utf-8"))
    for e in d["exercises"]:
        print(f"{e['key']}|{d['source_book']}|{d['family']}|{e.get('step')}|{e['name']}")
