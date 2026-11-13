"""HTTP 호출. 표준 라이브러리만 사용합니다."""
import time
import urllib.parse
import urllib.request
import urllib.error


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
    return url.split("serviceKey=")[0] + "serviceKey=***" if "serviceKey=" in url else url


def get(url, retries=3, timeout=40):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gamaeng-jeoul-collector/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # 네트워크 오류, 타임아웃
            last = e
        time.sleep(1.5 * (i + 1))
    raise ApiError("요청 실패: %s (%s)" % (mask(url), last))
