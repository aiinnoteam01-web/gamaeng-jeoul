"""정보공개서 본문에서 창업비용·직영점 수·업력·법 위반 이력을 뽑아냅니다.

공정위 표준 정보공개서의 '가맹점사업자의 부담' 부분은 표로 되어 있고, 금액 칸에는 숫자만 있으며
단위는 표 위의 '(단위: 천원 ...)' 에 따로 적혀 있습니다. 이 모양에 맞춰 뽑습니다.
  1) 최초 가맹금  : 가맹비, 최초교육비
  2) 보증금       : 계약이행보증금
  4) 그 밖의 비용 : 총계, 인테리어 (기타 = 총계 - 인테리어)

브랜드마다 표현이 조금씩 달라 틀릴 수 있으니, build 가 만드는 data/review.csv 의 근거 문장을 확인하고
틀린 값은 overrides.json 으로 바로잡으세요.
"""
import html
import re
import xml.etree.ElementTree as ET

UNIT = {"백만원": 100.0, "천원": 0.1, "만원": 1.0, "원": 0.0001}
NUM = r"([0-9][0-9,]*(?:\.[0-9]+)?|없음|해당\s*없음|-)"


def to_text(body):
    """XML/HTML 이 섞인 응답을 한 줄짜리 평문으로."""
    t = body
    try:
        root = ET.fromstring(body)
        t = " ".join(x for x in root.itertext())
    except ET.ParseError:
        pass
    t = html.unescape(t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def _unit_before(text, pos):
    """pos 앞쪽에서 가장 가까운 '(단위: ...)' 의 단위. 없으면 표준양식 기본값인 천원."""
    seg = text[max(0, pos - 1500): pos]
    found = list(re.finditer(r"단위\s*[:：]?\s*(백만원|천원|만원|원)", seg))
    return UNIT[found[-1].group(1)] if found else UNIT["천원"]


def _value(token):
    if token is None or not re.match(r"[0-9]", token):
        return 0.0          # 없음, 해당 없음, - 는 0
    return float(token.replace(",", ""))


def _find(text, labels, start=0, end=None, gap=30):
    """labels 중 하나 뒤(글자 gap 개 이내)에 처음 나오는 숫자. (값_만원, 근거문장)"""
    end = len(text) if end is None else end
    best = None
    for lab in labels:
        for m in re.finditer(re.escape(lab), text[start:end]):
            p = start + m.end()
            n = re.match(r"[^0-9]{0,%d}?\s%s" % (gap, NUM), text[p:p + gap + 20])
            if not n:
                n = re.match(r"\s*%s" % NUM, text[p:p + 30])
            if n:
                if best is None or start + m.start() < best[0]:
                    best = (start + m.start(), p + n.end(), n.group(1))
                break
    if not best:
        return None, None
    s, e, tok = best
    val = round(_value(tok) * _unit_before(text, s), 1)
    return val, text[max(0, s - 5): e + 5]


def extract(body):
    text = to_text(body)
    out, ev = {}, {}

    # 구간 나누기: '최초 가맹금' ~ '그 밖에 지급' ~ (그 뒤 2000자)
    a = text.find("최초 가맹금")
    if a < 0:
        a = text.find("최초가맹금")
    b = text.find("그 밖에 지급")
    if b < 0:
        b = text.find("그밖에 지급")
    a = 0 if a < 0 else a
    first_end = b if b > a else None

    out["fee"], ev["fee"] = _find(text, ["가맹비", "가입비"], a, first_end)
    out["edu"], ev["edu"] = _find(text, ["최초교육비", "교육비"], a, first_end)
    out["deposit"], ev["deposit"] = _find(text, ["계약이행보증금", "이행보증금"], a, first_end)

    interior = total = None
    if b >= 0:
        total, ev_total = _find(text, ["총계", "합계"], b, b + 800)
        interior, ev["interior"] = _find(text, ["인테리어"], b, b + 3000, gap=40)
        ev["etc"] = ev_total
    if total is not None and interior is None:
        interior = 0.0
    out["interior"] = interior
    out["etc"] = round(max(total - interior, 0), 1) if total is not None and interior is not None else None

    # 직영점 수: '가맹점 및 직영점의 총 수' 표의 '전체' 줄, 가장 최근 연도의 세 번째 값
    out["direct"], ev["direct"] = None, None
    i = text.find("직영점의 총 수")
    if i >= 0:
        m = re.search(r"전체((?:\s+[0-9,]+){3,})", text[i: i + 1500])
        if m:
            nums = [int(x.replace(",", "")) for x in m.group(1).split()]
            if len(nums) >= 3:
                k = (len(nums) // 3) * 3
                out["direct"] = nums[k - 1]
                ev["direct"] = text[i: i + m.end()][:200]

    m = re.search(r"(가맹사업\s*(?:개시|시작)일|법인\s*설립\s*(?:등기)?일|설립일|사업\s*개시일)[^0-9]{0,15}((?:19|20)[0-9]{2})", text)
    out["start_year"], ev["start_year"] = (int(m.group(2)), m.group(0)) if m else (None, None)

    viol, vev = None, None
    i = text.find("법 위반")
    if i < 0:
        i = text.find("법위반")
    if i >= 0:
        win = text[i: i + 400]
        if re.search(r"사실이\s*없습니다|해당\s*(?:사항|사실)?\s*없음|없습니다|없음", win[:250]):
            viol = 0
        else:
            viol = max(1, len(re.findall(r"시정조치|시정명령|과징금|과태료|벌금", win)))
        vev = win[:120]
    out["viol"], ev["viol"] = viol, vev
    return out, ev
