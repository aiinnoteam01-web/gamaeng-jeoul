"""원본 응답 저장소 (SQLite). 수집과 가공을 분리해서, 가공 규칙을 바꿔도 다시 호출할 필요가 없게 합니다."""
import json
import os
import sqlite3
import time

import config


def conn():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS raw (source TEXT, year TEXT, rec TEXT, fetched_at REAL)")
    c.execute("CREATE INDEX IF NOT EXISTS raw_src ON raw(source, year)")
    c.execute("CREATE TABLE IF NOT EXISTS content (sn TEXT PRIMARY KEY, body TEXT, fetched_at REAL)")
    return c


def replace_rows(source, year, rows):
    with conn() as c:
        c.execute("DELETE FROM raw WHERE source=? AND year=?", (source, str(year)))
        c.executemany("INSERT INTO raw VALUES (?,?,?,?)",
                      [(source, str(year), json.dumps(r, ensure_ascii=False), time.time()) for r in rows])


def rows(source):
    with conn() as c:
        return [(y, json.loads(r)) for y, r in c.execute("SELECT year, rec FROM raw WHERE source=?", (source,))]


def put_content(sn, body):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO content VALUES (?,?,?)", (str(sn), body, time.time()))


def get_content(sn):
    with conn() as c:
        r = c.execute("SELECT body FROM content WHERE sn=?", (str(sn),)).fetchone()
        return r[0] if r else None
