"""저장된 원본 응답을 화면용 data.json 으로 가공합니다. API 를 다시 호출하지 않습니다."""
import csv
import datetime as dt
import json
import os
import re
from collections import defaultdict

import config
from . import store
from .contentparse import extract

UNIT = {"백만원": 100.0, "천원": 0.1, "만원": 1.0, "원": 0.0001}
USED = defaultdict(dict)   # 소스별로 실제 사용된 응답 항목명 (진단용)


def pick(row, source, field):
    lower = {k.lower(): k for k in row}
    for cand in config.FIELDS[source].get(field, []):
        k = lower.get(cand.lower())
        if k is not None and str(row[k]).strip() != "":
            USED[source][field] = k
            return row[k]
    return None


def num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def norm_name(s):
    s = str(s or "")
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", s)
    s = re.sub(r"[\s\(\)\[\]·\.\-_,&']", "", s)
    return s.lower()


def brand_key(row, source):
    bid = pick(row, source, "brand_id")
    if bid:
        return "id:" + str(bid).strip()
    return "nm:" + norm_name(pick(row, source, "name"))


def _year(row, source, fallback):
    y = num(pick(row, source, "year"))
    if y:
        return int(y)
    try:
        return int(fallback)
    except (TypeError, ValueError):
        return None


def load_brands():
    """브랜드 목록 + 연도별 가맹점 현황을 브랜드 단위로 묶습니다."""
    brands = {}
    name_index = {}
    for y, r in sorted(store.rows("brand_list"), key=lambda x: str(x[0])):
        k = brand_key(r, "brand_list")
        b = brands.setdefault(k, {"stats": {}})
        b["name"] = pick(r, "brand_list", "name") or b.get("name")
        b["corp"] = pick(r, "brand_list", "corp") or b.get("corp")
        b["sector"] = pick(r, "brand_list", "sector") or b.get("sector")
        b["start"] = pick(r, "brand_list", "start_date") or b.get("start")
        name_index[norm_name(b["name"])] = k
    for y, r in store.rows("brand_stats"):
        k = brand_key(r, "brand_stats")
        if k not in brands:
            alt = name_index.get(norm_name(pick(r, "brand_stats", "name")))
            k = alt or k
        b = brands.setdefault(k, {"stats": {}})
        b["name"] = b.get("name") or pick(r, "brand_stats", "name")
        b["corp"] = b.get("corp") or pick(r, "brand_stats", "corp")
        b["sector"] = b.get("sector") or pick(r, "brand_stats", "sector")
        yr = _year(r, "brand_stats", y)
        if yr is None:
            continue
        b["stats"][yr] = {f: num(pick(r, "brand_stats", f)) for f in
                          ("stores", "direct", "new", "end", "cancel", "transfer", "avg_sales", "area_sales")}
    return brands


def ftc_index():
    """정보공개서 목록: 정규화한 브랜드명 → 가장 최근 일련번호."""
    idx = {}
    for y, r in store.rows("ftc_list"):
        sn = pick(r, "ftc_list", "sn")
        if not sn:
            continue
        nm = norm_name(pick(r, "ftc_list", "name"))
        yr = _year(r, "ftc_list", y) or 0
        prev = idx.get(nm)
        if not prev or yr >= prev[1]:
            idx[nm] = (str(sn), yr, pick(r, "ftc_list", "corp"))
    return idx


def _in_target(sector):
    return config.TARGET_SECTORS is None or (sector in config.TARGET_SECTORS)


def sector_counts():
    """업종 이름별 브랜드 수 (가맹점이 있는 브랜드만). 많은 순."""
    cnt = defaultdict(int)
    for b in load_brands().values():
        if b.get("sector") and b["stats"]:
            latest = b["stats"][max(b["stats"])]
            if latest.get("stores"):
                cnt[b["sector"]] += 1
    return sorted(cnt.items(), key=lambda kv: -kv[1])


def start_year(v):
    m = re.match(r"\s*((?:19|20)[0-9]{2})", str(v or ""))
    return int(m.group(1)) if m else None


def content_targets():
    """정보공개서 본문을 받아올 브랜드 목록 (업종별 가맹점 수 상위)."""
    brands, idx = load_brands(), ftc_index()
    by_sector = defaultdict(list)
    for k, b in brands.items():
        if not b.get("sector") or not _in_target(b["sector"]) or not b["stats"]:
            continue
        latest = b["stats"][max(b["stats"])]
        hit = idx.get(norm_name(b.get("name")))
        if hit:
            by_sector[b["sector"]].append((latest.get("stores") or 0, b["name"], hit[0]))
    out = []
    for s, lst in by_sector.items():
        lst.sort(reverse=True)
        lim = config.CONTENT_LIMIT_PER_SECTOR
        out.extend((s, n, sn) for _, n, sn in (lst[:lim] if lim else lst))
    return out


def load_industry():
    res = {}
    for y, r in store.rows("industry_stats"):
        s = pick(r, "industry_stats", "sector")
        yr = _year(r, "industry_stats", y)
        if not s or yr is None:
            continue
        cur = res.get(s)
        if cur and cur["year"] > yr:
            continue
        res[s] = {"year": yr,
                  "stores": num(pick(r, "industry_stats", "stores")),
                  "openRate": num(pick(r, "industry_stats", "open_rate")),
                  "closeRate": num(pick(r, "industry_stats", "close_rate"))}
    return res


def build():
    brands, idx = load_brands(), ftc_index()
    overrides = {}
    if os.path.exists(config.OVERRIDES):
        with open(config.OVERRIDES, encoding="utf-8") as f:
            overrides = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    this_year = dt.date.today().year
    sectors = defaultdict(list)
    review = []
    latest_years = []
    sales_f = UNIT[config.SALES_UNIT]

    for k, b in brands.items():
        name, sector = b.get("name"), b.get("sector")
        if not name or not sector or not b["stats"] or not _in_target(sector):
            continue
        ys = sorted(b["stats"])
        ly = ys[-1]
        cur, prev = b["stats"][ly], b["stats"].get(ly - 1)
        stores, sales = cur.get("stores"), cur.get("avg_sales")
        if not stores or not sales:
            continue
        latest_years.append(ly)
        closed = (cur.get("end") or 0) + (cur.get("cancel") or 0) if (cur.get("end") is not None or cur.get("cancel") is not None) else None
        # 공정위 업종 통계(종료해지율 = 종료·해지 가맹점 수 ÷ 그해 가맹점 수)와 같은 기준으로 계산합니다.
        base = stores
        close = round(closed / base * 100, 1) if closed is not None and base else None
        growth = round((stores - prev["stores"]) / prev["stores"] * 100, 1) if prev and prev.get("stores") else None
        transfer = round(cur["transfer"] / base * 100, 1) if cur.get("transfer") is not None and base else None
        flow = []
        for y in ys[-4:]:
            s = b["stats"][y]
            if s.get("new") is not None and (s.get("end") is not None or s.get("cancel") is not None):
                flow.append([int(s["new"]), int((s.get("end") or 0) + (s.get("cancel") or 0))])

        hit = idx.get(norm_name(name))
        sn = hit[0] if hit else None
        parsed, ev = ({}, {})
        body = store.get_content(sn) if sn else None
        if body:
            parsed, ev = extract(body)
        parts, partial = None, False
        if parsed.get("fee") is not None and parsed.get("interior") is not None:
            vals = [parsed.get(x) for x in ("fee", "edu", "deposit", "interior", "etc")]
            partial = any(v is None for v in vals)
            parts = [round(v or 0, 1) for v in vals]
        direct = cur.get("direct") if cur.get("direct") is not None else parsed.get("direct")
        sy = start_year(b.get("start")) or parsed.get("start_year")   # 브랜드 목록의 가맹사업개시일자를 우선 사용
        age = (this_year - sy) if sy else None

        item = {
            "id": k, "name": name, "corp": b.get("corp"), "year": ly,
            "parts": parts, "sales": round(sales * sales_f), "stores": int(stores),
            "direct": None if direct is None else int(direct), "age": age,
            "close": close, "growth": growth, "transfer": transfer,
            "viol": parsed.get("viol"), "flow": flow, "jngIfrmpSn": sn,
        }
        ov = overrides.get(name)
        if ov:
            item.update({kk: vv for kk, vv in ov.items() if kk != "sector"})
            sector = ov.get("sector", sector)
        sectors[sector].append(item)
        missing = [lab for lab, v in (("초기비용", item["parts"]), ("직영점", item["direct"]), ("업력", item["age"]),
                                       ("법위반", item["viol"]), ("폐점률", item["close"]), ("순증가율", item["growth"]),
                                       ("명의변경률", item["transfer"])) if v is None]
        review.append({
            "업종": sector, "브랜드": name, "가맹본부": b.get("corp") or "", "정보공개서번호": sn or "",
            "가맹금": parsed.get("fee"), "교육비": parsed.get("edu"), "보증금": parsed.get("deposit"),
            "인테리어": parsed.get("interior"), "기타": parsed.get("etc"), "비용_일부추정": "예" if partial else "",
            "직영점": item["direct"], "설립연도": sy, "법위반": item["viol"],
            "없는항목": ", ".join(missing), "override": "예" if ov else "",
            "근거_가맹금": ev.get("fee") or "", "근거_인테리어": ev.get("interior") or "",
            "근거_직영점": ev.get("direct") or "", "근거_설립": ev.get("start_year") or "", "근거_법위반": ev.get("viol") or "",
        })

    out_sectors = {s: sorted(v, key=lambda x: -x["stores"]) for s, v in sectors.items()
                   if len(v) >= config.MIN_BRANDS_PER_SECTOR}
    industry = {s: v for s, v in load_industry().items() if s in out_sectors}
    data = {
        "meta": {"generatedAt": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "latestYear": max(latest_years) if latest_years else None,
                 "salesUnit": "만원", "source": "공정거래위원회 가맹사업 정보 (공공데이터포털, 가맹사업정보제공시스템)"},
        "sectors": out_sectors,
        "industry": industry,
    }
    os.makedirs(os.path.dirname(config.SITE_DATA), exist_ok=True)
    with open(config.SITE_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    if review:
        with open(config.REVIEW_CSV, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(review[0].keys()))
            w.writeheader()
            w.writerows(review)
    return data, review
