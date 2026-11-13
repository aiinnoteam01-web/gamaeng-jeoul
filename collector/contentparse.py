"""정보공개서 본문에서 창업비용·직영점 수·업력·법 위반 이력을 뽑아냅니다.

주의: 정보공개서 본문은 브랜드마다 표 형식과 문장이 달라서, 이 추출은 '최선의 추정'입니다.
build 단계에서 data/review.csv 에 근거 문장(evidence)을 함께 남기니, 반드시 확인하고
틀린 값은 overrides.json 으로 바로잡으세요.
"""
import html
import re
import xml.etree.ElementTree as ET

UNIT = {"백만원": 100.0, "천원": 0.1, "만원": 1.0, "원": 0.0001}
NUM = r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(백만원|천원|만원|원)"
COST_LABELS = {
    "fee": ["가입비", "가맹비", "가맹금"],
    "edu": ["교육비"],
    "deposit": ["계약이행보증금", "보증금"],
    "interior": ["인테리어"],
    "etc": ["기타비용", "기타 비용"],
}


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


def _money_after(text, labels, window=60):
    for lab in labels:
        for m in re.finditer(re.escape(lab), text):
            seg = text[m.end(): m.end() + window]
            n = re.search(NUM, seg)
            if n:
                v = float(n.group(1).replace(",", "")) * UNIT[n.group(2)]
                ev = text[max(0, m.start() - 10): m.end() + n.end() + 5]
                return round(v, 1), ev
    return None, None


def extract(body):
    text = to_text(body)
    out, ev = {}, {}
    for k, labs in COST_LABELS.items():
        out[k], ev[k] = _money_after(text, labs)

    m = re.search(r"직영점[^0-9]{0,25}?([0-9]{1,4})\s*(?:개|곳|점)", text)
    out["direct"], ev["direct"] = (int(m.group(1)), m.group(0)) if m else (None, None)

    m = re.search(r"(가맹사업\s*(?:개시|시작)일|법인\s*설립\s*(?:등기)?일|설립일|사업\s*개시일)[^0-9]{0,15}((?:19|20)[0-9]{2})", text)
    out["start_year"], ev["start_year"] = (int(m.group(2)), m.group(0)) if m else (None, None)

    viol, vev = None, None
    i = text.find("법 위반")
    if i < 0:
        i = text.find("법위반")
    if i >= 0:
        win = text[i: i + 400]
        if re.search(r"해당\s*(?:사항|사실)?\s*없음|없습니다|없음", win[:200]):
            viol = 0
        else:
            viol = max(1, len(re.findall(r"시정조치|시정명령|과징금|과태료|벌금", win)))
        vev = win[:120]
    out["viol"], ev["viol"] = viol, vev
    return out, ev
