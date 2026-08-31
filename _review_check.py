import json

d = json.load(open('data/cell_explanations.json', encoding='utf-8'))
k = next(iter(d))
print('explanations sample:', k, json.dumps(d[k])[:400])
print('explanations count:', len(d))

g = json.load(open('data/cells_master.geojson', encoding='utf-8'))
p = g['features'][0]['properties']
print('master props:', sorted(p.keys()))
print('has top_positive_driver:', 'top_positive_driver' in p, type(p.get('top_positive_driver')))
print('has explanation_text:', 'explanation_text' in p,
      'has cluster:', 'cluster' in p, 'has risk_score:', 'risk_score' in p)

b = json.load(open('data/composite_burden.json', encoding='utf-8'))
kb = next(iter(b))
print('burden sample:', kb, json.dumps(b[kb])[:300])

e = json.load(open('data/environmental_intelligence.json', encoding='utf-8'))
ke = next(iter(e))
print('env sample:', ke, json.dumps(e[ke])[:300])

pl = json.load(open('data/planning_profiles.json', encoding='utf-8'))
kp = next(iter(pl))
print('planning sample:', kp, json.dumps(pl[kp])[:300])

f = json.load(open('data/flood_susceptibility.json', encoding='utf-8'))
kf = next(iter(f))
print('flood sample:', kf, json.dumps(f[kf])[:300])

ia = json.load(open('data/infrastructure_access_index.json', encoding='utf-8'))
ki = next(iter(ia))
print('iai sample:', ki, json.dumps(ia[ki])[:300])
