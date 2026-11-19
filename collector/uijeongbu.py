"""의정부 상가정보와 프랜차이즈 브랜드를 짝지어 의정부 매장 수·동별 분포를 계산합니다.

짝짓는 규칙 (오차를 줄이기 위한 규칙)
  1) 이름 다듬기: 띄어쓰기·괄호·특수문자·(주) 를 빼고 소문자로 비교
  2) 한글·영문 이름 모두 사용: "메가엠지씨커피(MEGA MGC COFFEE)" → 메가엠지씨커피, megamgccoffee
  3) 상호명이 브랜드명으로 '시작'할 때만 인정 (중간에 들어간 경우는 다른 가게로 봄)
  4) 두 글자 브랜드명은 상호명과 완전히 같을 때만 인정
  5) 업종 확인: 편의점은 '소매', 나머지 외식 업종은 '음식' 가게만 인정
  6) 별명 파일(uj_aliases.json): 브랜드명과 간판 이름이 다를 때 직접 짝을 적어 둠
결과 확인용으로 data/uj_review.csv(브랜드별로 센 가게), data/uj_unmatched.csv(지점명이 있는데 못 짝지은 가게)를 만듭니다.
"""
import csv
import json
import os
import re
from collections import Counter, defaultdict

import config
from . import store
from .build import pick

ROOT = os.path.dirname(config.OVERRIDES)
ALIASES = os.path.join(ROOT, "uj_aliases.json")
REVIEW = os.path.join(ROOT, "data", "uj_review.csv")
UNMATCHED = os.path.join(ROOT, "data", "uj_unmatched.csv")


def _norm(s):
    s = str(s or "")
    s = re.sub(r"\(주\)|㈜|주식회사", "", s)
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", s).lower()


def _variants(name, aliases):
    name = str(name or "")
    out = {_norm(re.sub(r"\(.*?\)", "", name))}
    for inner in re.findall(r"\((.*?)\)", name):
        out.add(_norm(inner))
    main = re.sub(r"\(.*?\)", "", name).strip()
    for key in (name, main):
        for a in aliases.get(key, []):
            out.add(_norm(a))
    return {v for v in out if len(v) >= 2}


def _load_aliases():
    if not os.path.exists(ALIASES):
        return {}
    with open(ALIASES, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def compute(sectors):
    """sectors: {업종: [브랜드 item, ...]} (상위 30개로 줄이기 전 전체). item 에 'uj' 를 붙이고 요약을 돌려줍니다."""
    rows = [r for _, r in store.rows("uj_stores")]
    if not rows:
        return None
    aliases = _load_aliases()

    # 브랜드 이름 사전: 다듬은 이름 → (업종, item). 같은 이름이 겹치면 전국 가맹점이 많은 브랜드를 씁니다.
    index = {}
    for sector, items in sectors.items():
        for it in items:
            for v in _variants(it["name"], aliases):
                cur = index.get(v)
                if cur is None or it["stores"] > cur[1]["stores"]:
                    index[v] = (sector, it)

    matched = defaultdict(list)          # item id → [store row]
    unmatched = Counter()
    unmatched_cat = {}
    all_dongs = set()
    for r in rows:
        nm = _norm(pick(r, "uj_stores", "name"))
        large = pick(r, "uj_stores", "large") or ""
        dong = pick(r, "uj_stores", "dong")
        if dong:
            all_dongs.add(dong)
        hit = None
        for L in range(min(len(nm), 40), 1, -1):
            cand = index.get(nm[:L])
            if not cand:
                continue
            if L < 3 and L != len(nm) and not (nm.endswith("점") or pick(r, "uj_stores", "branch")):
                continue
            sector, it = cand
            want = "소매" if sector.replace(" ", "") == "편의점" else "음식"
            if want not in large:
                continue
            hit = it
            break
        if hit:
            place = r.get("bldMngNo") or r.get("rdnmAdr")
            if place and any((x.get("bldMngNo") or x.get("rdnmAdr")) == place for x in matched[hit["id"]]):
                continue   # 같은 건물에 같은 브랜드가 두 번 등록된 경우 한 곳으로 셈
            matched[hit["id"]].append(r)
        elif pick(r, "uj_stores", "branch") and ("음식" in large or "소매" in large):
            key = pick(r, "uj_stores", "name")
            unmatched[key] += 1
            unmatched_cat[key] = pick(r, "uj_stores", "small")

    # 브랜드별 결과
    review = []
    sector_stats = {}
    small_by_sector = defaultdict(Counter)
    for sector, items in sectors.items():
        ranked = sorted((it for it in items if matched.get(it["id"])), key=lambda it: -len(matched[it["id"]]))
        rank = {it["id"]: i + 1 for i, it in enumerate(ranked)}
        for it in items:
            st = matched.get(it["id"], [])
            dongs = Counter(pick(r, "uj_stores", "dong") for r in st)
            for r in st:
                small_by_sector[sector][pick(r, "uj_stores", "small")] += 1
            it["uj"] = {"n": len(st), "rank": rank.get(it["id"]),
                        "dongs": [[d, n] for d, n in dongs.most_common() if d]}
            if st:
                review.append({"업종": sector, "브랜드": it["name"], "의정부매장수": len(st),
                               "동별": " · ".join("%s %d" % (d, n) for d, n in dongs.most_common() if d),
                               "센 가게(상호명 지점명 / 행정동)": " | ".join(
                                   "%s %s / %s" % (pick(r, "uj_stores", "name") or "", pick(r, "uj_stores", "branch") or "",
                                                   pick(r, "uj_stores", "dong") or "") for r in st[:15])})
        # 업종 전체 매장 수: 짝지은 가게들이 주로 속한 상가 업종(소분류)의 의정부 전체 점포 수
        cnt = small_by_sector[sector]
        total_m = sum(cnt.values())
        cats, acc = [], 0
        for cat, n in cnt.most_common(3):
            cats.append(cat)
            acc += n
            if acc >= total_m * 0.8:
                break
        total = sum(1 for r in rows if pick(r, "uj_stores", "small") in cats) if cats else None
        sector_stats[sector] = {"total": total, "cats": cats,
                                "top": [[it["name"], len(matched[it["id"]])] for it in ranked[:3]],
                                "brands": len(ranked)}

    os.makedirs(os.path.dirname(REVIEW), exist_ok=True)
    with open(REVIEW, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["업종", "브랜드", "의정부매장수", "동별", "센 가게(상호명 지점명 / 행정동)"])
        w.writeheader()
        w.writerows(sorted(review, key=lambda x: (x["업종"], -x["의정부매장수"])))
    with open(UNMATCHED, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["상호명", "지점명이 있는 매장 수", "상가 업종", "안내"])
        for name, n in unmatched.most_common(300):
            w.writerow([name, n, unmatched_cat.get(name, ""), "프랜차이즈라면 uj_aliases.json 에 브랜드명과 짝을 적어 주세요"])

    return {"dongs": sorted(all_dongs), "sectors": sector_stats, "stores": len(rows),
            "matched": sum(len(v) for v in matched.values())}
