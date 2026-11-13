"""XML/JSON 응답을 [항목 dict] 로 바꿉니다. 응답 구조를 몰라도 동작하도록 일반적으로 처리합니다."""
import json
import xml.etree.ElementTree as ET
from collections import Counter

ERROR_HINTS = {
    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR": "등록되지 않은 인증키입니다. 키를 확인하거나 승인 후 1~2시간 기다려 보세요.",
    "SERVICE ERROR": "서비스 오류입니다. 요청주소와 요청변수를 확인하세요.",
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR": "일일 호출 한도를 넘었습니다. 내일 다시 시도하거나 운영계정을 신청하세요.",
    "APPLICATION_ERROR": "요청변수가 잘못되었을 수 있습니다. 명세서의 필수 요청변수를 확인하세요.",
}


def decode(raw):
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _find_key(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == key.lower() and not isinstance(v, (dict, list)):
                return v
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def _largest_dict_list(obj):
    best = []
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj) and len(obj) > len(best):
            best = obj
        for v in obj:
            c = _largest_dict_list(v)
            if len(c) > len(best):
                best = c
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == "item" and isinstance(v, dict):  # 결과가 1건이면 dict 로 오는 경우
                if len(best) < 1:
                    best = [v]
            c = _largest_dict_list(v)
            if len(c) > len(best):
                best = c
    return best


def _flat(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, (dict, list)):
            continue
        out[k] = v
    return out


def parse_payload(raw):
    """반환: (items, meta). meta = {totalCount, resultCode, resultMsg, error}"""
    text = decode(raw).strip()
    meta = {"totalCount": None, "resultCode": None, "resultMsg": None, "error": None}
    for code, hint in ERROR_HINTS.items():
        if code in text[:2000]:
            meta["error"] = "%s: %s" % (code, hint)
            return [], meta
    if text[:1] in "{[":
        obj = json.loads(text)
        meta["totalCount"] = _find_key(obj, "totalCount")
        meta["resultCode"] = _find_key(obj, "resultCode")
        meta["resultMsg"] = _find_key(obj, "resultMsg")
        items = [_flat(x) for x in _largest_dict_list(obj)]
    else:
        root = ET.fromstring(text)
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag in ("totalCount", "resultCode", "resultMsg") and (el.text or "").strip():
                meta[tag] = el.text.strip()
        # 자식이 모두 '잎' 인 원소 = 한 건의 레코드 후보. 가장 많이 반복되는 태그를 레코드로 봅니다.
        cands = []
        for el in root.iter():
            kids = list(el)
            if kids and all(len(list(k)) == 0 for k in kids):
                tag = el.tag.split("}")[-1]
                if tag.lower() != "header":
                    cands.append(el)
        cnt = Counter(e.tag for e in cands)
        items = []
        if cnt:
            tag = cnt.most_common(1)[0][0]
            for e in cands:
                if e.tag == tag:
                    items.append({k.tag.split("}")[-1]: (k.text or "").strip() for k in e})
    rc = str(meta["resultCode"] or "")
    if rc and rc not in ("00", "0", "000", "INFO-000", "200") and not items:
        meta["error"] = "resultCode=%s %s" % (rc, meta["resultMsg"] or "")
    try:
        meta["totalCount"] = int(str(meta["totalCount"]).replace(",", "")) if meta["totalCount"] is not None else None
    except ValueError:
        meta["totalCount"] = None
    return items, meta
