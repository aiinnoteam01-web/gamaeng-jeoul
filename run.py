"""가맹저울 수집기 실행 파일.

  python run.py check                       설정 점검
  python run.py inspect brand_stats --year 2024   응답 항목명 확인 (5건만 호출)
  python run.py inspect ftc_list --year 2024
  python run.py inspect ftc_content --sn 151420   정보공개서 본문 확인 + 추출 결과
  python run.py collect                     전체 수집 (원본을 data/raw.sqlite3 에 저장)
  python run.py collect --only brand_stats  특정 소스만 다시 수집
  python run.py build                       화면용 site/data.json 생성 + data/review.csv
  python run.py serve                       http://localhost:8000 에서 화면 확인
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_env():
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return True


has_env = load_env()
sys.path.insert(0, ROOT)
import config  # noqa: E402  (.env 를 읽은 뒤에 불러와야 합니다)
from collector import store  # noqa: E402
from collector.fetch import ApiError  # noqa: E402
from collector.sources import fetch_dgk, fetch_ftc_list, fetch_ftc_doc  # noqa: E402


def hide_key(v):
    """응답 안에 들어 있는 인증키(serviceKey=...)를 가립니다. 공개 저장소 실행 기록에 키가 찍히지 않게."""
    import re
    return re.sub(r"(serviceKey=)[^&\s]+", r"\1***", str(v), flags=re.I)


def cmd_check(_):
    print(".env 파일:", "있음" if has_env else "없음 (GitHub 에서는 Secrets 를 쓰므로 정상입니다)")
    print("FTC_FRANCHISE_KEY:", "설정됨" if config.FTC["key"] else "비어 있음")
    print("DATA_GO_KR_KEY:", "설정됨" if config.DGK_COMMON["key"] else "비어 있음")
    for name, cfg in config.DATA_GO_KR.items():
        state = "사용 안 함" if not cfg["enabled"] else ("요청주소 설정됨" if cfg["url"] else "요청주소 비어 있음")
        print(" - %-15s %s  (%s)" % (name, state, cfg["title"]))
    print("수집 연도:", config.YEARS, " 대상 업종:", config.TARGET_SECTORS or "전체")


def cmd_inspect(a):
    try:
        if a.source == "ftc_content":
            if not a.sn:
                sys.exit("--sn 정보공개서 일련번호가 필요해요 (ftc_list 의 jngIfrmpSn).")
            from collector.contentparse import extract, to_text
            body = fetch_ftc_doc(a.sn, "content")
            text = to_text(body)
            print("── 응답 원문 앞부분 (태그 포함) ──")
            print(hide_key(body[:600]))
            print("\n── 본문 글자 수:", len(text))
            print("── 본문 앞부분 ──")
            print(hide_key(text[:800]))
            for kw in ("가맹금", "가입비", "교육비", "보증금", "인테리어", "기타비용", "직영", "법 위반", "법위반"):
                pos, shown = 0, 0
                while shown < 2:
                    i = text.find(kw, pos)
                    if i < 0:
                        break
                    print("\n── [%s] 주변 ──" % kw)
                    print(hide_key(text[max(0, i - 60): i + 240]))
                    pos, shown = i + len(kw), shown + 1
                if shown == 0:
                    print("\n── [%s] 본문에 없음" % kw)
            vals, ev = extract(body)
            print("\n── 추출 결과 (만 원 단위) ──")
            for k, v in vals.items():
                print("%-10s %-10s 근거: %s" % (k, v, (ev.get(k) or "")[:80]))
            return
        if a.source == "ftc_list":
            items, meta = fetch_ftc_list(a.year or config.YEARS[-1], inspect=True)
        else:
            items, meta = fetch_dgk(a.source, a.year or config.YEARS[-1], inspect=True)
    except ApiError as e:
        sys.exit(str(e))
    print("totalCount:", meta.get("totalCount"), " resultCode:", meta.get("resultCode"), meta.get("resultMsg") or "")
    if meta.get("year_param"):
        print("동작한 연도 요청변수:", meta["year_param"])
    if not items:
        print("항목이 없어요. 연도나 요청변수(config.py 의 year_param, extra)를 확인하세요.")
        return
    print("\n응답 항목명:", ", ".join(items[0].keys()))
    for i, it in enumerate(items[:2], 1):
        print("\n── %d번째 레코드 ──" % i)
        for k, v in it.items():
            print("  %-28s %s" % (k, hide_key(v)))
    fields = config.FIELDS.get(a.source)
    if fields:
        keys = {k.lower() for k in items[0]}
        print("\n── config.FIELDS 매칭 결과 ──")
        for f, cands in fields.items():
            hit = next((c for c in cands if c.lower() in keys), None)
            print("  %-12s %s" % (f, hit or "없음 → 위 항목명 중 맞는 것을 config.FIELDS 에 추가하세요"))


def cmd_collect(a):
    only = set(a.only.split(",")) if a.only else None
    want = lambda s: only is None or s in only  # noqa: E731
    years = [int(y) for y in a.years.split(",")] if a.years else config.YEARS
    for name, cfg in config.DATA_GO_KR.items():
        if not cfg["enabled"] or not want(name):
            continue
        targets = years if cfg.get("year_param") else [None]
        for y in targets:
            try:
                rows, info = fetch_dgk(name, y)
                store.replace_rows(name, y if y is not None else "all", rows)
                print("[%s] %s년 %d건 저장" % (name, y or "전체", len(rows)))
            except ApiError as e:
                print("오류:", e)
    if want("ftc_list"):
        import datetime as _dt
        # 정보공개서 목록의 연도는 '그해에 등록·변경된 문서'라서 올해까지 모두 받습니다.
        for y in range(min(years), _dt.date.today().year + 1):
            try:
                rows, _ = fetch_ftc_list(y)
                if rows:
                    store.replace_rows("ftc_list", y, rows)
                print("[ftc_list] %d년 정보공개서 %d건" % (y, len(rows)))
            except ApiError as e:
                print("오류:", e)
    if want("ftc_content") and not a.skip_content:
        from collector.build import content_targets
        tg = content_targets()
        if not tg:
            print("[ftc_content] 대상 브랜드가 없어요. 브랜드 목록·현황·정보공개서 목록 수집과 업종명(TARGET_SECTORS)을 확인하세요.")
        done = 0
        for i, (sector, name, sn) in enumerate(tg, 1):
            if store.get_content(sn) and not a.refresh:
                continue
            try:
                store.put_content(sn, fetch_ftc_doc(sn, "content"))
                done += 1
                print("[ftc_content] %d/%d %s · %s" % (i, len(tg), sector, name))
                time.sleep(config.SLEEP_SEC)
            except ApiError as e:
                print("오류:", e)
        print("[ftc_content] 새로 받은 본문 %d건 (대상 %d건)" % (done, len(tg)))


def cmd_build(_):
    from collector.build import build, USED
    data, review = build()
    print("site/data.json 생성: 기준연도", data["meta"]["latestYear"])
    if not data["sectors"]:
        print("화면에 올릴 업종이 없어요. collect 결과와 config.FIELDS / TARGET_SECTORS 를 확인하세요.")
    for s, lst in data["sectors"].items():
        noc = sum(1 for b in lst if b["parts"] is None)
        print(" - %-8s 브랜드 %3d개 (초기비용 없음 %d개)%s" % (s, len(lst), noc, " · 업종 통계 있음" if s in data["industry"] else ""))
    from collector.build import sector_counts
    print("\n수집된 업종 이름과 브랜드 수 (TARGET_SECTORS 에 이 이름 그대로 적어야 화면에 나옵니다):")
    print("  " + ", ".join("%s(%d)" % kv for kv in sector_counts()))
    print("\n실제로 사용된 응답 항목명:")
    for src, m in USED.items():
        print(" ", src, dict(m))
    print("\n검토 파일: data/review.csv  (정보공개서에서 추출한 값과 근거 문장을 꼭 확인하세요)")


def cmd_serve(a):
    import http.server
    import functools
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(ROOT, "site"))
    print("http://localhost:%d 에서 확인하세요 (종료: Ctrl+C)" % a.port)
    http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler).serve_forever()


def main():
    p = argparse.ArgumentParser(description="가맹저울 수집기")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check").set_defaults(f=cmd_check)
    i = sp.add_parser("inspect")
    i.add_argument("source", choices=list(config.DATA_GO_KR) + ["ftc_list", "ftc_content"])
    i.add_argument("--year", type=int)
    i.add_argument("--sn")
    i.set_defaults(f=cmd_inspect)
    c = sp.add_parser("collect")
    c.add_argument("--only", help="쉼표로 구분: brand_list,brand_stats,industry_stats,region_sales,ftc_list,ftc_content")
    c.add_argument("--years", help="예: 2022,2023,2024")
    c.add_argument("--skip-content", action="store_true")
    c.add_argument("--refresh", action="store_true", help="이미 받은 정보공개서 본문도 다시 받기")
    c.set_defaults(f=cmd_collect)
    sp.add_parser("build").set_defaults(f=cmd_build)
    s = sp.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(f=cmd_serve)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
