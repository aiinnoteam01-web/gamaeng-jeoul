"""HTTP 호출. 표준 라이브러리만 사용합니다."""
import gzip
import io
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib


class ApiError(Exception):
    pass


def build_url(base, params, key, key_param="serviceKey"):
    """인증키는 다시 인코딩하지 않도록 따로 붙입니다(인코딩 키에 % 가 들어 있음)."""
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    k = key if "%" in key else urllib.parse.quote(key, safe="")
    sep = "&" if "?" in base else "?"
    return base + sep + (q + "&" if q else "") + key_param + "=" + k


def mask(url):
    """로그에 키가 찍히지 않게 가립니다."""
    import re
    return re.sub(r"([Ss]erviceKey=)[^&]+", r"\1***", url)


def unpack(raw, encoding_header=""):
    """압축된 응답을 풉니다. 정보공개서 본문은 gzip 으로 압축되어 오는 경우가 있습니다."""
    for _ in range(3):  # 겹겹이 압축된 경우까지
        if raw[:2] == b"\x1f\x8b":                       # gzip
            raw = gzip.decompress(raw)
        elif "deflate" in (encoding_header or "").lower():
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            encoding_header = ""
        elif raw[:2] == b"PK":                           # zip (hwpx, docx 등): 안의 xml/html 글자를 모읍니다
            parts = []
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for n in sorted(z.namelist()):
                    if n.lower().endswith((".xml", ".html", ".htm", ".txt")):
                        parts.append(z.read(n))
            raw = b"\n".join(parts)
        else:
            break
    return raw


def get(url, retries=3, timeout=40):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gamaeng-jeoul-collector/1.0",
                                                       "Accept-Encoding": "gzip, deflate"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return unpack(r.read(), r.headers.get("Content-Encoding", ""))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # 네트워크 오류, 타임아웃
            last = e
        time.sleep(1.5 * (i + 1))
    raise ApiError("요청 실패: %s (%s)" % (mask(url), last))
