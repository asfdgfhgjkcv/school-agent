import re
import time
from datetime import datetime
from typing import Optional
import httpx

BASE_URL = "https://www.cuit.edu.cn"
NOTICE_URL = f"{BASE_URL}/index/tzgg.htm"
NEWS_URL = f"{BASE_URL}/index/cxyw.htm"

_cache = {"notices": [], "news": [], "expire": 0}
CACHE_TTL = 300


def _fetch_html(url: str) -> str | None:
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"[Notice] fetch failed: {e}")
    return None


def _parse_notices(html: str, source: str = "notice") -> list[dict]:
    items = []
    # Find the notice list container first
    list_start = html.find('<ul class="list">')
    if list_start < 0:
        return items
    list_html = html[list_start:]
    pattern = re.compile(
        r'<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>.*?<span>(\d{4}-\d{2}-\d{2})</span>',
        re.DOTALL,
    )
    for m in pattern.finditer(list_html):
        href, title, h3_text, date_str = m.groups()
        if not href.startswith(".."):
            continue
        full_url = BASE_URL + href[2:]
        items.append({
            "id": abs(hash(full_url)) % (2**31),
            "title": title.strip(),
            "date": date_str.strip(),
            "url": full_url,
            "typeLabel": "通知公告" if source == "notice" else "成信要闻",
        })
    return items


def _ensure_cache():
    now = time.time()
    if now < _cache["expire"]:
        return
    html = _fetch_html(NOTICE_URL)
    news_html = _fetch_html(NEWS_URL)
    notices = _parse_notices(html) if html else []
    news = _parse_notices(news_html, source="news") if news_html else []
    _cache["notices"] = notices
    _cache["news"] = news
    _cache["expire"] = now + CACHE_TTL


def get_notices(notice_type: str = "", page: int = 1, page_size: int = 20) -> dict:
    _ensure_cache()
    all_items = _cache["notices"]
    if notice_type == "news":
        all_items = _cache["news"]
    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "success": True,
        "notices": all_items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total,
    }


def search_notices(keyword: str) -> dict:
    _ensure_cache()
    kw = keyword.lower()
    results = [
        n for n in _cache["notices"]
        if kw in n["title"].lower()
    ]
    results.sort(key=lambda x: x["date"], reverse=True)
    return {"success": True, "notices": results[:50], "total": len(results)}


def get_notice_detail(notice_id: int) -> dict:
    _ensure_cache()
    for n in _cache["notices"] + _cache["news"]:
        if n["id"] == notice_id:
            html = _fetch_html(n["url"])
            content = ""
            if html:
                m = re.search(
                    r'class="(content|article|maintext|v_news_content)"[^>]*>([\s\S]*?)</div>',
                    html,
                )
                if m:
                    content = re.sub(r"<[^>]+>", "", m.group(2))
                    content = re.sub(r"\s+", " ", content).strip()[:2000]
            return {
                "success": True,
                "notice": {**n, "content": content or "暂无详细内容"},
            }
    return {"success": False, "message": "通知不存在"}


def get_student_notices(username: str) -> dict:
    _ensure_cache()
    return {"success": True, "notices": _cache["notices"][:10], "total": min(10, len(_cache["notices"]))}
