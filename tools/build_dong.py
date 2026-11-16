# 동(행정동) 단위 자료 만들기 → dong.json
# 입력(data_raw/, git 제외): hjd.geojson(행정동 경계, vuski/admdongkor ver20261001, 통계청 SGIS 원자료 CC BY)
#   pop.csv(행정안전부 행정동 주민등록 인구 2026-10-31), hosp/hospitals.csv(심평원 병의원 현황 2026.9)
#   ../shelters.json(행정안전부 민방위대피시설)
# 실행: python -I tools/build_dong.py  (프로젝트 폴더에서)
import json, csv, math, re, sys
from collections import Counter
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
    m = re.match(r'^(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|경기도의료원|충청남도|충청북도|경상북도|경상남도|전라남도|전북특별자치도|제주특별자치도)(.{2,}(?:병원|의료원))$', n)
    if m and m.group(2) != '의료원': n = m.group(2)  # 서울특별시서울의료원 → 서울의료원
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

# 연령(65세 이상·12세 이하 비율, 주민등록 인구) · 1인 세대 비율(행정동 세대원수별 세대수)
AGE = {}
rows = list(csv.reader(open(RAW + 'pop.csv', encoding='cp949'))); hdr = rows[0]
ages = [(i, int(re.match(r'(\d+)', c).group(1))) for i, c in enumerate(hdr) if re.match(r'\d+세', c)]
for row in rows[1:]:
    t = int(row[5]) or 1
    AGE[row[0]] = (round(100 * sum(int(row[i]) for i, a in ages if a >= 65) / t), round(100 * sum(int(row[i]) for i, a in ages if a <= 12) / t))
SOLO = {}
for row in list(csv.reader(open(RAW + 'hh.csv', encoding='cp949')))[1:]:
    if int(row[5]): SOLO[row[0]] = round(100 * int(row[6]) / int(row[5]))

# 지형: AWS Terrain Tiles(terrarium, z10 ≈ 픽셀 120m, USGS SRTM 등 원자료) → 동 안 픽셀의 고도
import numpy as np
from PIL import Image, ImageDraw
Z = 10; NPX = 256 * 2 ** Z; TILE = {}
def gpx(lon, lat):
    la = math.radians(lat)
    return (lon + 180) / 360 * NPX, (1 - math.log(math.tan(la) + 1 / math.cos(la)) / math.pi) / 2 * NPX
def tile(x, y):
    if (x, y) not in TILE:
        try:
            a = np.asarray(Image.open(f'{RAW}terrain/{x}_{y}.png').convert('RGB'), dtype=np.float32)
            TILE[(x, y)] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
        except FileNotFoundError: TILE[(x, y)] = None
    return TILE[(x, y)]
def mosaic(x0, y0, x1, y1):  # 픽셀 범위 [x0,x1)×[y0,y1) 고도, 없는 타일은 nan
    m = np.full((y1 - y0, x1 - x0), np.nan, np.float32)
    for ty in range(y0 // 256, (y1 - 1) // 256 + 1):
        for tx in range(x0 // 256, (x1 - 1) // 256 + 1):
            t = tile(tx, ty)
            if t is None: continue
            ax0, ay0 = max(x0, tx * 256), max(y0, ty * 256); ax1, ay1 = min(x1, tx * 256 + 256), min(y1, ty * 256 + 256)
            m[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0] = t[ay0 - ty * 256:ay1 - ty * 256, ax0 - tx * 256:ax1 - tx * 256]
    return m
for d in D:
    rings = [[gpx(*q) for q in ring] for poly in d['polys'] for ring in poly]
    x0 = int(min(p[0] for r in rings for p in r)); y0 = int(min(p[1] for r in rings for p in r))
    x1 = int(max(p[0] for r in rings for p in r)) + 2; y1 = int(max(p[1] for r in rings for p in r)) + 2
    img = Image.new('L', (x1 - x0, y1 - y0), 0); dr = ImageDraw.Draw(img)
    for poly in d['polys']:
        for k, ring in enumerate(poly):
            dr.polygon([(gpx(*q)[0] - x0, gpx(*q)[1] - y0) for q in ring], fill=0 if k else 1)
    mask = np.asarray(img, bool); el = mosaic(x0, y0, x1, y1)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:  # 픽셀보다 작은 동 → 꼭짓점 평균 위치 한 점
        cx, cy = gpx(d['cx'], d['cy']); xs, ys = np.array([int(cx) - x0]), np.array([int(cy) - y0])
    v = el[ys, xs]; v = v[~np.isnan(v)]
    pcx, pcy = xs.mean() + x0, ys.mean() + y0  # 동 면적의 무게중심(픽셀)
    lon = pcx / NPX * 360 - 180; lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * pcy / NPX))))
    d['cx'], d['cy'] = lon, lat
    mpp = 156543.03 * math.cos(math.radians(lat)) / 2 ** Z  # 픽셀 1칸 m
    if len(v):
        d['ele'] = int(round(float(np.mean(np.clip(v, 0, None)))))
        d['rel'] = int(round(float(np.percentile(v, 90) - np.percentile(v, 10))))
        d['low'] = int(round(100 * float(np.mean(v < 10))))
    else: d['ele'] = d['rel'] = d['low'] = -1
print('terrain tiles', sum(1 for t in TILE.values() if t is not None))
# 바다까지 거리: 전국 행정동 경계를 z10 픽셀로 칠함 → 안 칠해진 곳 = 바다(휴전선 북쪽은 뺌) → 25km 안 최단거리
GX0, GY0 = map(int, gpx(124.0, 38.9)); GX1, GY1 = map(int, gpx(132.0, 32.8))
land = Image.new('L', (GX1 - GX0, GY1 - GY0), 0); ld = ImageDraw.Draw(land)
for f in json.load(open(RAW + 'hjd.geojson', encoding='utf-8'))['features']:
    g = f['geometry']
    for poly in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]):
        ld.polygon([(gpx(*q)[0] - GX0, gpx(*q)[1] - GY0) for q in poly[0]], fill=1)
LAND = np.asarray(land, bool).copy()
MDL = [(126.10, 37.70), (126.55, 37.76), (126.68, 37.93), (126.85, 37.96), (127.0, 38.10), (127.2, 38.28), (127.5, 38.30), (127.8, 38.32), (128.1, 38.27), (128.3, 38.35), (128.40, 38.55), (128.36, 38.62)]
for x in range(LAND.shape[1]):  # 휴전선 북쪽(북한 땅)은 바다로 치지 않게 땅으로 채움
    lon = (x + GX0) / NPX * 360 - 180
    if 126.5 < lon < 128.4:
        lat = float(np.interp(lon, [p[0] for p in MDL], [p[1] for p in MDL])); y = int(gpx(lon, lat)[1]) - GY0
        LAND[:max(0, y), x] = True
print('land px', int(LAND.sum()))
for d in D:
    px, py = gpx(d['cx'], d['cy']); px, py = int(px) - GX0, int(py) - GY0
    mpp = 156543.03 * math.cos(math.radians(d['cy'])) / 2 ** Z; R0 = int(25000 / mpp)
    w = LAND[max(0, py - R0):py + R0, max(0, px - R0):px + R0]; sy, sx = np.nonzero(~w)
    oy, ox = py - max(0, py - R0), px - max(0, px - R0)
    d['sea'] = round(float(np.min(np.hypot(sx - ox, sy - oy))) * mpp / 1000, 1) if len(sx) else -1

# 역·고속도로 나들목: OpenStreetMap(© OpenStreetMap contributors, ODbL) — 없으면 건너뜀
ST, IC = [], []
try:
    for e in json.load(open(RAW + 'osm.json', encoding='utf-8'))['elements']:
        t = e.get('tags', {}); nm = t.get('name')
        if not nm: continue
        if t.get('highway') == 'motorway_junction':
            nm = re.sub(r'\s*\([^)]*\)', '', nm).strip()  # 동둔내IC(하이패스) → 동둔내IC
            if re.search(r'(JC|JCT|분기점|교차로)$', nm): continue  # 고속도로끼리 갈라지는 곳은 나가는 길이 아님
            IC.append((e['lat'], e['lon'], nm if re.search(r'(IC|나들목|TG)$', nm) else nm + ' 나들목'))
        elif t.get('railway') == 'station' and (t.get('station') in ('subway', 'light_rail') or t.get('subway') == 'yes' or t.get('train') == 'yes' or 'station' not in t):
            nm = re.sub(r'\([^)]*[一-鿿][^)]*\)', '', nm).strip()  # 오현역(梧峴驛) → 오현역
            ST.append((e['lat'], e['lon'], nm if nm.endswith('역') else nm + '역', t.get('station') in ('subway', 'light_rail') or t.get('subway') == 'yes'))
except FileNotFoundError: pass
print('stations', len(ST), 'ic', len(IC))
names = sorted({h[2] for h in H} | {s[2] for s in ST} | {i[2] for i in IC}); ni = {n: i for i, n in enumerate(names)}

# 아파트 단지 수: 국토교통부 공동주택 단지 목록(K-apt 등록 단지, tools/fetch_apt.py) — 법정동 이름으로 행정동에 연결
# 관저동(법정동) → 관저1동·관저2동(행정동)처럼 나눠 쓰면 「관저동 일대」로 같은 수를 보여 줌
APT = Counter()
try:
    for a in json.load(open(RAW + 'apt.json', encoding='utf-8')):
        if a['as1'] and a['as3']: APT[(a['as1'], (a['as2'] or '세종시').replace(' ', ''), a['as3'])] += 1  # 세종은 시군구 칸이 비어 있음
except FileNotFoundError: pass
core = lambda n: re.sub(r'(제)?[\d·]*(가)?[\d·]*(동|읍|면|가)$', '', n)
sggN = lambda s: re.sub(r'^(\S+?)시(\S+구)$', r'\1\2', s)
BJ = {}  # (시도, 시군구) → [(법정동, 단지 수)]
for (s1, s2, s3), n in APT.items(): BJ.setdefault((s1, s2), []).append((s3, n))
claim = Counter(); AM = {}
for d in D:
    c = core(d['nm']); hits = [(b, n) for b, n in BJ.get((d['sido'], sggN(d['sgg'])), []) if len(core(b)) >= 2 and (core(b) == c or (len(c) > len(core(b)) and core(b) in c))]
    AM[d['code']] = hits
    for b, n in hits: claim[(d['sido'], d['sgg'], b)] += 1
print('apt matched dongs', sum(1 for h in AM.values() if h), '/', len(D))

out = {}; nsg = 0
def near(d, L):
    return min((km(d['cy'], d['cx'], p[0], p[1]), p) for p in L) if L else (-1, None)
for d in D:
    k, h = near(d, H)
    key = (sido22(d['sido'], d['sgg']), d['sgg'], d['nm'])
    apt, old = SG.get(key + ('공동주택비율',), -1), SG.get(key + ('노후주택비율',), -1); nsg += apt >= 0
    sk, s = near(d, ST); ik, ic = near(d, IC); e65, kid = AGE.get(d['code'], (-1, -1))
    out.setdefault(d['r'], []).append([d['nm'], d['pop'], round(d['area'], 2), d['sn'], d['sc'], round(k, 1), ni[h[2]], d['sgg'], apt, old,
        e65, kid, SOLO.get(d['code'], -1), d['ele'], d['rel'], d['low'], d['sea'],
        ni[s[2]] if s else -1, round(sk, 1), (1 if s and s[3] else 0), ni[ic[2]] if ic else -1, round(ik, 1),
        sum(n for _, n in AM[d['code']]) if AM[d['code']] else (0 if (d['sido'], sggN(d['sgg'])) in BJ else -1),  # 그 시군구 목록에 없으면 0곳
        '·'.join(b for b, _ in AM[d['code']] if claim[(d['sido'], d['sgg'], b)] > 1), round(d['cy'], 5), round(d['cx'], 5), d['code']])
print('sgis matched', nsg, '/', len(D))
# 행: [0동 1인구 2면적 3대피소수 4수용 5병원km 6병원 7구 8공동주택% 9노후% 10고령% 11어린이% 12 1인세대% 13평균고도m 14고저차m 15저지대% 16바다km 17역 18역km 19지하철? 20나들목 21나들목km 22아파트단지수(K-apt, 없으면 -1) 23나눠 쓰는 법정동 이름(있으면 「○○동 일대」) 24위도 25경도(동 면적 무게중심) 26행정동코드(결과 링크용)]
json.dump({'h': names, 'd': out}, open('dong.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
miss = [r for r in REGIONS if r not in out]
print('regions', len(out), 'missing', miss, 'dongs', sum(map(len, out.values())), 'hosp', len(H))
