"""Sync merged columns in cells_master.geojson from the regenerated artifacts.

The backend (backend/main.py) merges environmental_health, planning fields,
FSI/IAI/burden into cell properties at load time, but the master file itself
kept stale copies from before the MMR retraining. This makes the file match.
"""
import json

master_path = 'data/cells_master.geojson'
g = json.load(open(master_path, encoding='utf-8'))

env = json.load(open('data/environmental_intelligence.json', encoding='utf-8'))
plans = json.load(open('data/planning_profiles.json', encoding='utf-8'))
fsi = json.load(open('data/flood_susceptibility.json', encoding='utf-8'))
iai = json.load(open('data/infrastructure_access_index.json', encoding='utf-8'))
bur = json.load(open('data/composite_burden.json', encoding='utf-8'))

n_synced = 0
for f in g['features']:
    p = f['properties']
    cid = p.get('cell_id')
    e = env.get(cid, {})
    pl = plans.get(cid, {})
    fl = fsi.get(cid, {})
    ia = iai.get(cid, {})
    bu = bur.get(cid, {})
    updates = {
        'environmental_health': e.get('environmental_health'),
        'flood_susceptibility_score': fl.get('flood_susceptibility_score'),
        'iai_score': ia.get('iai_score'),
        'burden_score': bu.get('burden_score'),
        'planning_priority_score': pl.get('priority_score'),
        'planning_priority': pl.get('planning_priority'),
    }
    changed = False
    for k, v in updates.items():
        if v is not None and p.get(k) != v:
            p[k] = v
            changed = True
    n_synced += changed

with open(master_path, 'w', encoding='utf-8') as f:
    json.dump(g, f)

print(f'Synced {n_synced} cells in {master_path}')
