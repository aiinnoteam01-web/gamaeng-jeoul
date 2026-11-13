"""가맹저울 수집 설정.

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
TARGET_SECTORS = ["치킨", "커피", "한식", "피자", "편의점"]

# 업종당 정보공개서 본문을 가져올 최대 브랜드 수 (가맹점 수가 많은 순). None 이면 제한 없음.
CONTENT_LIMIT_PER_SECTOR = 60

# 화면에 올릴 업종의 최소 브랜드 수
MIN_BRANDS_PER_SECTOR = 3

# API 호출 사이 대기 시간(초). 일일 트래픽 한도를 아끼려면 늘리세요.
SLEEP_SEC = 0.25

# ── 금액 단위 ────────────────────────────────────────────────
# 응답 금액의 단위. 명세서를 보고 "천원", "만원", "원", "백만원" 중 하나로 맞추세요.
SALES_UNIT = "천원"          # 브랜드별 가맹점 현황의 평균매출금액
INDUSTRY_SALES_UNIT = "천원"  # 업종 통계 금액 (사용하는 경우)

# ── 공정위 가맹사업정보제공시스템 (franchise.ftc.go.kr) ─────────────
FTC = {
    "base": "https://franchise.ftc.go.kr/api/search.do",
    "key": os.environ.get("FTC_FRANCHISE_KEY", ""),
    "per_page": 200,
}

# ── 공공데이터포털 (data.go.kr) ───────────────────────────────
# url 은 .env 에서 읽습니다. 요청변수 이름(year_param 등)은 각 API 명세서에 맞게 고치세요.
DATA_GO_KR = {
    "brand_list": {
        "title": "공정거래위원회_가맹정보_브랜드 목록 정보 제공 서비스",
        "url": os.environ.get("DGK_BRAND_LIST_URL", ""),
        "year_param": "yr",            # 명세서의 연도 요청변수명 (예: yr, jngBizCrtraYr)
        "extra": {},                   # 그 밖의 필수 요청변수 {"이름": "값"}
        "enabled": True,
    },
    "brand_stats": {
        "title": "공정거래위원회_가맹정보_브랜드별 가맹점 현황 제공 서비스",
        "url": os.environ.get("DGK_BRAND_STATS_URL", ""),
        "year_param": "yr",
        "extra": {},
        "enabled": True,
    },
    "industry_stats": {
        "title": "공정거래위원회_가맹정보 주요 업종별 가맹점수, 개폐점률 현황 제공 서비스",
        "url": os.environ.get("DGK_INDUSTRY_STATS_URL", ""),
        "year_param": "yr",
        "extra": {},
        "enabled": True,
    },
    "region_sales": {
        "title": "공정거래위원회_가맹정보_지역별 업종별 평균 매출액 현황 제공 서비스",
        "url": os.environ.get("DGK_REGION_SALES_URL", ""),
        "year_param": "yr",
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
        "sector": ["indutyMlsfcNm", "indutyMclasNm", "indutyNm"],
        "year": ["yr", "jngBizCrtraYr", "crtrYr"],
        "stores": ["frcsCnt", "frcsTotCnt"],
        "open_rate": ["newFrcsRt", "opbizRt", "newRt", "opnRt"],
        "close_rate": ["endCncltnRt", "clsbizRt", "clsRt", "closRt"],
    },
    "ftc_list": {
        "sn": ["jngIfrmpSn"],
        "name": ["brandNm", "brndNm", "brandName"],
        "corp": ["corpNm", "conmNm", "jnghdqrtrsConmNm"],
        "year": ["jngBizCrtraYr", "yr"],
    },
}

# 화면 데이터와 원본 DB 위치
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "raw.sqlite3")
SITE_DATA = os.path.join(os.path.dirname(__file__), "site", "data.json")
REVIEW_CSV = os.path.join(os.path.dirname(__file__), "data", "review.csv")
OVERRIDES = os.path.join(os.path.dirname(__file__), "overrides.json")
