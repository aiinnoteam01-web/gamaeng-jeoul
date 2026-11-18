"""API 별 수집 로직."""
import time

import config
from .fetch import build_url, get, ApiError
from .parse import parse_payload


def _check(meta, name):
    if meta.get("error"):
        raise ApiError("[%s] %s" % (name, meta["error"]))


YEAR_PARAM_FOUND = {}   # API 별로 실제 동작한 연도 요청변수 이름


def _year_candidates(name, cfg, year):
    yp = cfg.get("year_param")
    if year is None or not yp:
        return [None]
    if name in YEAR_PARAM_FOUND:
        return [YEAR_PARAM_FOUND[name]]
    return yp if isinstance(yp, list) else [yp]


def _call_dgk(cfg, com, page, per, year_param, year):
    params = dict(cfg.get("extra") or {})
    if year_param:
        params[year_param] = year
    params[com["page_param"]] = page
    params[com["rows_param"]] = per
    fmt = cfg.get("format_param", com.get("format_param"))
    if fmt:
        params[fmt[0]] = fmt[1]
    return parse_payload(get(build_url(cfg["url"], params, com["key"], cfg.get("key_param", "serviceKey"))))

def fetch_dgk(name, year=None, inspect=False, max_pages=500):
    """공공데이터포털 API 를 페이지 끝까지 가져옵니다. 연도 요청변수 이름은 후보를 차례로 시도합니다."""
    cfg = config.DATA_GO_KR[name]
    com = config.DGK_COMMON
    if not cfg["url"]:
        raise ApiError("[%s] 요청주소가 비어 있어요." % name)
    if not com["key"]:
        raise ApiError("DATA_GO_KR_KEY 가 비어 있어요. GitHub Secrets 를 확인하세요.")
    per = 5 if inspect else com["per_page"]

    # 1쪽: 연도 요청변수 후보를 차례로 시도
    items, meta, used, last_err = [], {}, None, None
    for yp in _year_candidates(name, cfg, year):
        try:
            items, meta = _call_dgk(cfg, com, 1, per, yp, year)
        except ApiError as e:
            last_err = str(e)
            continue
        if meta.get("error"):
            last_err = meta["error"]
            continue
        if items:
            used = yp
            break
        time.sleep(config.SLEEP_SEC)
    if not items:
        if last_err:
            raise ApiError("[%s] %s" % (name, last_err))
        return [], {"pages": 1, "year_param": None, "totalCount": meta.get("totalCount")}
    if used:
        YEAR_PARAM_FOUND[name] = used
    if inspect:
        meta["year_param"] = used
        return items, meta

    out, page = list(items), 1
    total = meta.get("totalCount")
    while page < max_pages and len(items) >= per and (total is None or len(out) < total):
        page += 1
        time.sleep(config.SLEEP_SEC)
        items, meta = _call_dgk(cfg, com, page, per, used, year)
        _check(meta, name)
        if not items:
            break
        out.extend(items)
    return out, {"pages": page, "year_param": used}


def _env_name(name):
    return {"brand_list": "DGK_BRAND_LIST_URL", "brand_stats": "DGK_BRAND_STATS_URL",
            "industry_stats": "DGK_INDUSTRY_STATS_URL", "region_sales": "DGK_REGION_SALES_URL"}[name]


def _ftc_key():
    if not config.FTC["key"]:
        raise ApiError("FTC_FRANCHISE_KEY 가 비어 있어요. GitHub Secrets 를 확인하세요.")
    return config.FTC["key"]


def fetch_ftc_list(year, inspect=False, max_pages=500):
    """정보공개서 공개본 목록 (type=list)."""
    key, per = _ftc_key(), (5 if inspect else config.FTC["per_page"])
    out, page = [], 1
    while page <= max_pages:
        url = build_url(config.FTC["base"], {"type": "list", "yr": year, "pageNo": page,
                                             "numOfRows": per, "viewType": "xml"}, key)
        items, meta = parse_payload(get(url))
        _check(meta, "ftc_list")
        out.extend(items)
        if inspect:
            return out, meta
        total = meta.get("totalCount")
        if not items or len(items) < per or (total is not None and len(out) >= total):
            break
        page += 1
        time.sleep(config.SLEEP_SEC)
    return out, {"pages": page}


def fetch_ftc_doc(sn, kind="content"):
    """정보공개서 목차(type=title) 또는 본문(type=content) 원문 텍스트."""
    url = build_url(config.FTC["base"], {"type": kind, "jngIfrmpSn": sn}, _ftc_key())
    raw = get(url, timeout=90)
    from .parse import decode, ERROR_HINTS
    text = decode(raw)
    for code, hint in ERROR_HINTS.items():
        if code in text[:2000]:
            raise ApiError("[ftc_%s] %s: %s" % (kind, code, hint))
    return text
