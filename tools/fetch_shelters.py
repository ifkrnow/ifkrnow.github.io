"""전국 민방위 대피시설 → shelters.json (가벼운 배열)

데이터: 행정안전부_민방위대피시설 조회서비스 (data.go.kr 15155067). 응답에 WGS84 위경도가 들어 있음.
키는 환경변수 DATA_GO_KR_API_KEY 에서만 읽는다 (사이트·저장소에 키를 넣지 않음).
출력 행: [위도, 경도, 시설명, 주소, 최대수용인원, 지하=1/지상=0, 동네(지번 주소 앞부분)]  — 운영 중(사용중)인 시설만
사용: DATA_GO_KR_API_KEY=... python tools/fetch_shelters.py
"""
import json, os, sys, time, urllib.parse, urllib.request

API = "https://apis.data.go.kr/1741000/civil_defense_shelter_info/info"
OUT = os.path.join(os.path.dirname(__file__), "..", "shelters.json")


def get(page, key, rows=100):
    k = key if "%" in key else urllib.parse.quote(key, safe="")
    url = f"{API}?serviceKey={k}&pageNo={page}&numOfRows={rows}&returnType=json"
    for i in range(5):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))["response"]["body"]
        except Exception as e:
            print(f"  page {page} retry {i+1}: {type(e).__name__}", flush=True)
            if i == 4: raise
            time.sleep(3 * (i + 1))


def row(it):
    try:
        lat, lng = float(it.get("LAT_EPSG4326") or 0), float(it.get("LOT_EPST4326") or 0)  # (원본 필드명 오타 EPST 그대로)
    except ValueError:
        return None
    if not (33 < lat < 39 and 124 < lng < 132) or it.get("OPER_STTS") != "사용중":
        return None
    lot = (it.get("LCTN_WHOL_ADDR") or "").strip()
    addr = (it.get("ROAD_NM_WHOL_ADDR") or lot).strip()
    # 검색용 동네: 지번 주소에서 번지 앞까지 (도로명 주소엔 '화명동' 같은 동 이름이 없음)
    toks = lot.split()
    dong = " ".join(t for t in toks if not any(c.isdigit() for c in t))[:40]
    try: cap = int(float(it.get("MAX_ACTC_PERNE") or 0))
    except ValueError: cap = 0
    return [round(lat, 5), round(lng, 5), (it.get("FCLT_NM") or "").strip(), addr, cap, 1 if it.get("FCLTLOC_GRND_UDGD") == "지하" else 0, dong]


if __name__ == "__main__":
    key = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
    if not key: sys.exit("DATA_GO_KR_API_KEY 환경변수가 필요합니다")
    from concurrent.futures import ThreadPoolExecutor
    total = int(get(1, key, 1)["totalCount"])
    pages = list(range(1, total // 100 + 2))
    print("total", total, "pages", len(pages), flush=True)
    def fetch(p):
        items = get(p, key)["items"]["item"]
        return [items] if isinstance(items, dict) else items
    rows, seen, done = [], set(), 0
    with ThreadPoolExecutor(6) as ex:  # 6개씩 동시에 (한 번에 ~1.7초 걸려서 순서대로면 느림)
        for items in ex.map(fetch, pages):
            done += 1
            for it in items:
                r = row(it)
                if r and (r[0], r[1], r[2]) not in seen:
                    seen.add((r[0], r[1], r[2])); rows.append(r)
            if done % 20 == 0: print(f"{done}/{len(pages)} pages, rows {len(rows)}", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    print("saved", len(rows), "→", os.path.getsize(OUT) // 1024, "KB", flush=True)
