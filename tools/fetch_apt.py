# 국토교통부 공동주택 단지 목록(K-apt 등록 단지) 전체 → data_raw/apt.json
# 키는 환경변수 DATA_GO_KR_API_KEY (출력·저장하지 않음). 실행: python -I tools/fetch_apt.py
import json, os, sys, time, urllib.parse, urllib.request
k = os.environ['DATA_GO_KR_API_KEY']
url = 'https://apis.data.go.kr/1613000/AptListService4/getTotalAptList4?serviceKey=' + urllib.parse.quote(k, safe='') + '&numOfRows=1000&_type=json&pageNo='
items, page = [], 1
while True:
    b = json.loads(urllib.request.urlopen(url + str(page), timeout=60).read().decode('utf-8'))['response']['body']
    items += b['items'] or []
    if page * 1000 >= b['totalCount']: break
    page += 1; time.sleep(0.3)
json.dump(items, open('data_raw/apt.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('apt', len(items), 'of', b['totalCount'])
