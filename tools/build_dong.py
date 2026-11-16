# 동(행정동) 단위 자료 만들기 → dong.json
# 입력(data_raw/, git 제외): hjd.geojson(행정동 경계, vuski/admdongkor ver20261001, 통계청 SGIS 원자료 CC BY)
#   pop.csv(행정안전부 행정동 주민등록 인구 2026-10-31), hosp/hospitals.csv(심평원 병의원 현황 2026.9)
#   ../shelters.json(행정안전부 민방위대피시설)
# 실행: python -I tools/build_dong.py  (프로젝트 폴더에서)
import json, csv, math, re, sys
sys.stdout.reconfigure(encoding='utf-8')
RAW = 'data_raw/'
REGIONS = re.findall(r'([가-힣]+):\[', open('index.html', encoding='utf-8').read().split('const R = {')[1].split('};')[0])
SIDO = {'서울': '서울특별시', '인천': '인천광역시', '부산': '부산광역시', '대구': '대구광역시', '광주': '광주광역시',
        '대전': '대전광역시', '울산': '울산광역시', '세종': '세종특별자치시', '제주': '제주특별자치도'}
def region_of(sido, sgg):
    for r, s in SIDO.items():
        if sido == s: return r
    if sido == '전남광주통합특별시' and sgg in ('동구', '서구', '남구', '북구', '광산구'): return '광주'
    if sgg == '울릉군': return '울릉도'
    if sgg == '창원시진해구': return '진해'
    for r in REGIONS:
        if r in SIDO: continue
        if sgg.startswith(r + '시') or sgg.startswith(r + '군'): return r
    return None

def area_km2(rings):  # 위경도 다각형 면적(근사, 바깥 고리 - 구멍)
    tot = 0
    for k, ring in enumerate(rings):
        lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
        a = 0
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            a += (x1 * y2 - x2 * y1)
        a = abs(a) / 2 * (111.32 * math.cos(lat0)) * 110.57
        tot += a if k == 0 else -a
    return tot
def inside(x, y, ring):
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def km(lat1, lon1, lat2, lon2):
    return math.hypot((lat1 - lat2) * 111, (lon1 - lon2) * 111 * math.cos(math.radians((lat1 + lat2) / 2)))

pop = {}
for row in csv.reader(open(RAW + 'pop.csv', encoding='cp949')):
    if row[0].isdigit(): pop[row[0]] = int(row[5])

D = []
for f in json.load(open(RAW + 'hjd.geojson', encoding='utf-8'))['features']:
    p = f['properties']; r = region_of(p['sidonm'], p['sggnm'])
    if not r: continue
    polys = f['geometry']['coordinates'] if f['geometry']['type'] == 'MultiPolygon' else [f['geometry']['coordinates']]
    pts = [q for poly in polys for q in poly[0]]
    D.append(dict(r=r, nm=p['adm_nm'].split()[-1], sgg=p['sggnm'], sido=p['sidonm'], code=p['adm_cd2'], polys=polys,
                  area=sum(area_km2(poly) for poly in polys), pop=pop.get(p['adm_cd2'], 0),
                  bb=(min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts)),
                  cx=sum(q[0] for q in pts) / len(pts), cy=sum(q[1] for q in pts) / len(pts), sn=0, sc=0))

# 대피소 → 그 좌표가 들어간 동
for lat, lon, name, addr, cap, under, jibun in json.load(open('shelters.json', encoding='utf-8')):
    for d in D:
        b = d['bb']
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and any(inside(lon, lat, poly[0]) for poly in d['polys']):
            d['sn'] += 1; d['sc'] += cap; break

# 가장 가까운 종합병원(상급종합·종합병원). 이름은 법인명 떼고 짧게: 학교법인 을지학원 대전을지대학교병원 → 대전을지대병원
def short(n):
    p = re.search(r'\(([^)]*(?:병원|의료원))\)', n)
    n = p.group(1) if p and not n.split('(')[0].endswith(('병원', '의료원')) else re.sub(r'\([^)]*\)', '', n).strip()
    n = re.sub(r'^(강원특별자치도|국민건강보험공단|미리내천주성삼성직수도회)', '', n)
    if ' ' in n: n = n.split()[-1]
    m = re.search(r'(?:재단|학원|법인)(?!.*(?:재단|학원|법인))(.+병원)$', n)
    if m and len(m.group(1)) >= 3: n = m.group(1)
    for a, b in (('대학교의과대학부속', '대'), ('대학교의과대학', '대'), ('의과대학부속', ''), ('대학교', '대')): n = n.replace(a, b)
    return n
H = []
for row in csv.reader(open(RAW + 'hosp/hospitals.csv', encoding='cp949')):
    if row[3] in ('상급종합', '종합병원') and row[28] and row[29]:
        H.append((float(row[29]), float(row[28]), short(row[1]), row[3] == '상급종합'))
hn = sorted({h[2] for h in H}); hi = {n: i for i, n in enumerate(hn)}

# 통계청 SGIS 「살고싶은 우리동네」 2022: 공동주택비율·노후주택비율 (10% 구간 → 가운데 값, 없으면 -1)
SG = {}
for row in list(csv.reader(open(RAW + 'sgis.csv', encoding='utf-8-sig')))[1:]:
    m = re.match(r'(\d+)', row[6]); v = 5 if row[6].startswith('10 미만') else int(m.group(1)) + 5
    SG[(row[3], row[4].replace(' ', ''), row[5], row[1])] = v
def sido22(s, sgg):
    if s == '전남광주통합특별시': return '광주광역시' if sgg in ('동구', '서구', '남구', '북구', '광산구') else '전라남도'
    return {'강원특별자치도': '강원도', '전북특별자치도': '전라북도'}.get(s, s)

out = {}; nsg = 0
for d in D:
    k, h = min((km(d['cy'], d['cx'], h[0], h[1]), h) for h in H)
    key = (sido22(d['sido'], d['sgg']), d['sgg'], d['nm'])
    apt, old = SG.get(key + ('공동주택비율',), -1), SG.get(key + ('노후주택비율',), -1); nsg += apt >= 0
    out.setdefault(d['r'], []).append([d['nm'], d['pop'], round(d['area'], 2), d['sn'], d['sc'], round(k, 1), hi[h[2]], d['sgg'], apt, old])
print('sgis matched', nsg, '/', len(D))
json.dump({'h': hn, 'd': out}, open('dong.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
miss = [r for r in REGIONS if r not in out]
print('regions', len(out), 'missing', miss, 'dongs', sum(map(len, out.values())), 'hosp', len(H))
