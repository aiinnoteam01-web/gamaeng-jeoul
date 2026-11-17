"""가맹저울 수집 설정.

2024년 점검 결과를 반영했습니다 (브랜드 목록·가맹점 현황·정보공개서 목록 항목명 확인 완료).
이 파일에서 바꿀 곳은 세 군데뿐입니다.
1) YEARS, TARGET_SECTORS        : 수집할 연도와 업종
2) DATA_GO_KR 의 year_param 등   : 각 API 명세서의 요청변수 이름
3) FIELDS                        : 응답 항목 이름 후보

FIELDS 의 후보 이름은 아직 실제 응답을 보지 못하고 넣은 '추정값'입니다.
`python run.py inspect <소스이름>` 으로 실제 항목명을 확인한 뒤,
맞는 이름을 각 목록의 맨 앞에 추가해 주세요. 목록 중 처음 발견되는 이름을 사용합니다.
"""
import os

# ── 수집 범위 ────────────────────────────────────────────────
# 개점·폐점 흐름과 폐점률 계산에 최근 4~5개 연도가 필요합니다. (가장 최근 연도가 화면 기준 연도)
YEARS = [2020, 2021, 2022, 2023, 2024]

# 정보공개서 본문(창업비용 등)을 수집할 업종. None 이면 전 업종(호출 수가 매우 많아짐).
# 브랜드 목록 API의 업종명과 똑같이 적어야 합니다. inspect 로 확인하세요.
TARGET_SECTORS = ["한식", "기타 외식", "커피", "치킨", "분식", "주점", "일식", "제과제빵", "중식", "서양식", "피자", "기타 외국식", "패스트푸드", "음료 (커피 외)", "아이스크림/빙수", "편의점"]

# 업종당 정보공개서 본문을 가져올 최대 브랜드 수 (가맹점 수가 많은 순). None 이면 제한 없음.
CONTENT_LIMIT_PER_SECTOR = 30

# 화면에 올릴 업종의 최소 브랜드 수
MIN_BRANDS_PER_SECTOR = 3

# API 호출 사이 대기 시간(초). 일일 트래픽 한도를 아끼려면 늘리세요.
SLEEP_SEC = 0.25

# ── 금액 단위 ────────────────────────────────────────────────
# 응답 금액의 단위. 명세서를 보고 "천원", "만원", "원", "백만원" 중 하나로 맞추세요.
SALES_UNIT = "천원"          # 브랜드별 가맹점 현황의 평균매출금액
INDUSTRY_SALES_UNIT = "천원"  # 업종 통계 금액 (사용하는 경우)
COST_UNIT = "천원"           # 브랜드별 창업 금액 현황의 금액

# ── 공정위 가맹사업정보제공시스템 (franchise.ftc.go.kr) ─────────────
FTC = {
    "base": "https://franchise.ftc.go.kr/api/search.do",
    "key": os.environ.get("FTC_FRANCHISE_KEY", ""),
    "per_page": 200,
}

# ── 공공데이터포털 (data.go.kr) ───────────────────────────────
# 요청주소는 공공데이터포털 활용신청 상세기능정보에서 확인한 주소입니다 (공개 정보라 코드에 넣어 둠).
DATA_GO_KR = {
    "brand_list": {
        "title": "공정거래위원회_가맹정보_브랜드 목록 정보 제공 서비스",
        "url": os.environ.get("DGK_BRAND_LIST_URL") or "https://apis.data.go.kr/1130000/FftcBrandRlsInfo2_Service/getBrandinfo",
        # 연도 요청변수 이름 후보. 앞에서부터 차례로 시도해 데이터가 나오는 이름을 자동으로 씁니다.
        "year_param": ["jngBizCrtraYr"],   # 점검으로 확인됨
        "extra": {},                   # 그 밖의 필수 요청변수 {"이름": "값"}
        "enabled": True,
    },
    "brand_stats": {
        "title": "공정거래위원회_가맹정보_브랜드별 가맹점 현황 제공 서비스",
        "url": os.environ.get("DGK_BRAND_STATS_URL") or "https://apis.data.go.kr/1130000/FftcBrandFrcsStatsService/getBrandFrcsStats",
        "year_param": ["yr"],   # 점검으로 확인됨
        "extra": {},
        "enabled": True,
    },
    "industry_stats": {
        "title": "공정거래위원회_가맹정보 주요 업종별 가맹점수, 개폐점률 현황 제공 서비스",
        "url": os.environ.get("DGK_INDUSTRY_STATS_URL") or "https://apis.data.go.kr/1130000/FftcIndutyFrcsCntOpclStatsService/getIndutyFrcsCntOpclStats",
        "year_param": ["jngBizCrtrYr"],   # 미리보기 화면으로 확인됨 (2017년부터)
        "extra": {},
        "enabled": True,
    },
    "brand_costs": {
        "title": "공정거래위원회_가맹정보_브랜드별 창업 금액 현황 제공 서비스",
        "url": os.environ.get("DGK_BRAND_COSTS_URL") or "https://apis.data.go.kr/1130000/FftcBrandFntnStatsService/getBrandFntnStats",
        "year_param": ["yr"],   # 미리보기 화면으로 확인됨
        "extra": {},
        "enabled": True,
    },
    "region_sales": {
        "title": "공정거래위원회_가맹정보_지역별 업종별 평균 매출액 현황 제공 서비스",
        "url": os.environ.get("DGK_REGION_SALES_URL", ""),
        "year_param": ["jngBizCrtraYr", "yr"],
        "extra": {},                   # 업종 대분류코드가 필수라면 여기에 넣으세요 (예: {"indutyLclasCd": "..."})
        "enabled": False,              # 지역 기능을 만들 때 True 로
    },
}
DGK_COMMON = {
    "key": os.environ.get("DATA_GO_KR_KEY", ""),
    "page_param": "pageNo",
    "rows_param": "numOfRows",
    "per_page": 1000,
    # JSON 으로 받기 위한 요청변수. 명세서에 따라 ("resultType", "json") 또는 ("type", "json").
    # XML 만 되는 API 라면 None 으로 두세요. 어느 쪽이든 자동으로 해석합니다.
    "format_param": ("resultType", "json"),
}

# ── 응답 항목 이름 후보 (추정값: inspect 로 확인 후 수정) ──────────────
FIELDS = {
    "brand_list": {
        "brand_id": ["brandMnno", "brandMngNo", "brandNo", "brandSn", "brndMnno"],
        "name": ["brandNm", "brndNm", "brandName"],
        "corp": ["jnghdqrtrsConmNm", "corpNm", "conmNm", "jnghdqrtrsNm"],
        "sector": ["indutyMlsfcNm", "indutyMclasNm", "indutyNm", "induty"],
        "biz_no": ["brno", "bizrno", "jnghdqrtrsBrno"],
        "start_date": ["jngBizStrtDate", "jngBizBgngDate", "jngBizStrtDe", "bizStrtDate"],
    },
    "brand_stats": {
        "brand_id": ["brandMnno", "brandMngNo", "brandNo", "brandSn", "brndMnno"],
        "name": ["brandNm", "brndNm", "brandName"],
        "corp": ["jnghdqrtrsConmNm", "corpNm", "conmNm"],
        "sector": ["indutyMlsfcNm", "indutyMclasNm", "indutyNm"],
        "year": ["yr", "jngBizCrtraYr", "crtrYr", "baseYr"],
        "stores": ["frcsCnt", "frcsTotCnt", "jngStorCnt"],
        "direct": ["drctStorCnt", "drctmngStorCnt"],
        "new": ["newFrcsRgsCnt", "newFrcsCnt", "frcsNewCnt"],
        "end": ["ctrtEndCnt", "frcsCtrtEndCnt"],
        "cancel": ["ctrtCncltnCnt", "frcsCtrtCncltnCnt"],
        "transfer": ["nmChgCnt", "frcsNmChgCnt"],
        "avg_sales": ["avrgSlsAmt", "frcsAvrgSlsAmt", "avgSlsAmt"],
        "area_sales": ["arUnitAvrgSlsAmt", "unitArAvrgSlsAmt"],
    },
    "industry_stats": {
        "sector": ["indutyMlsfcNm", "tpbizMclsfNm", "indutyMclasNm", "indutyNm", "tpbizNm"],
        "year": ["jngBizCrtrYr", "yr", "jngBizCrtraYr"],
        "stores": ["frcsCnt", "frcsTotCnt"],
        "open_rate": ["newFrcsRt", "opbizRt", "newRt", "opnRt"],
        "close_rate": ["endCncltnRt", "clsbizRt", "clsRt", "closRt"],
    },
    "brand_costs": {
        "name": ["brandNm", "brndNm", "brandName"],
        "corp": ["corpNm", "jnghdqrtrsConmNm", "conmNm"],
        "year": ["yr", "jngBizCrtraYr"],
        "fee": ["jngBzmnJngAmt", "frcsJngAmt", "jngAmt"],
        "edu": ["jngBzmnEduAmt", "frcsEduAmt", "eduAmt"],
        "deposit": ["jngBzmnAssrncAmt", "frcsAssrncAmt", "assrncAmt", "grntyAmt"],
        "etc": ["jngBzmnEtcAmt", "frcsEtcAmt", "etcAmt"],
        "interior": ["intrrAmt", "jngBzmnIntrrAmt", "itrrAmt"],
        "total": ["smtnAmt", "jngBzmnTotAmt", "totAmt", "sumAmt"],
    },
    "ftc_list": {
        "sn": ["jngIfrmpSn"],
        "name": ["brandNm", "brndNm", "brandName"],
        "corp": ["corpNm", "conmNm", "jnghdqrtrsConmNm"],
        "year": ["jngBizCrtraYr", "yr"],   # 응답에 연도 항목이 없어 수집한 연도를 씁니다
    },
}

# 화면 데이터와 원본 DB 위치
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "raw.sqlite3")
SITE_DATA = os.path.join(os.path.dirname(__file__), "site", "data.json")
REVIEW_CSV = os.path.join(os.path.dirname(__file__), "data", "review.csv")
OVERRIDES = os.path.join(os.path.dirname(__file__), "overrides.json")
