#!/usr/bin/env python3
"""Hourly MARKET PULSE companion feed, independent of Gemini and daily forecasts.

Only writes site/data/hourly.json. It never imports update_report.py or opens
site/data/latest.json. No FRED/Yahoo data is fetched or copied into this feed.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "site" / "data" / "hourly.json"
TREASURY_SOURCE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "TextView?type=daily_treasury_yield_curve"
)
TOPICS = {
    "stocks_kr": ["국내증시 코스피 코스닥 오늘", "반도체 외국인 기관 코스피 오늘"],
    "stocks_us": ["미국 증시 나스닥 S&P500 오늘", "뉴욕증시 빅테크 연준 오늘"],
    "bonds": ["미국 국채 수익률 채권시장 오늘", "국고채 기준금리 채권시장 오늘"],
}


def now_kst() -> datetime:
    return datetime.now(timezone.utc).astimezone(KST)


def fetch_bytes(url: str, attempts: int = 2) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MARKET-PULSE/1.0 (hourly public data refresh)",
            "Accept": "text/csv,application/rss+xml,application/xml,text/xml,*/*",
        },
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("원본 자료 크기 제한 초과")
            return data
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 >= attempts:
                raise RuntimeError(f"원본 연결 실패: {type(exc).__name__}") from None
            time.sleep(1.2)
    raise RuntimeError("원본 연결 실패")


def parse_news(xml_bytes: bytes, cutoff: datetime) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    output = []
    for item in root.findall("./channel/item"):
        raw_title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        if not raw_title or not link.startswith("https://") or not pub_date:
            continue
        try:
            published = parsedate_to_datetime(pub_date)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except (ValueError, TypeError, IndexError, OverflowError):
            continue
        if published < cutoff or published > datetime.now(timezone.utc) + timedelta(hours=2):
            continue
        source = item.find("source")
        publisher = (source.text or "").strip() if source is not None else ""
        if not publisher and " - " in raw_title:
            publisher = raw_title.rsplit(" - ", 1)[-1].strip()
        title = raw_title[:-len(" - " + publisher)] if publisher and raw_title.endswith(" - " + publisher) else raw_title
        output.append({
            "title": title[:190],
            "publisher": (publisher or "Google 뉴스")[:70],
            "url": link,
            "published_at": published.isoformat(),
        })
    return output


def collect_news(now: datetime, errors: list[str]) -> tuple[dict, dict]:
    news = {}
    status = {}
    cutoff = now.astimezone(timezone.utc) - timedelta(days=3)
    for key, searches in TOPICS.items():
        found, seen, successes = [], set(), 0
        for term in searches:
            params = urllib.parse.urlencode({
                "q": term + " when:3d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"
            })
            try:
                items = parse_news(fetch_bytes("https://news.google.com/rss/search?" + params), cutoff)
                successes += 1
            except (RuntimeError, ET.ParseError, ValueError):
                errors.append(f"뉴스 {key}: 일부 RSS 피드 조회 실패")
                continue
            for item in items:
                title_key = re.sub(r"\W+", "", item["title"]).lower()
                if title_key not in seen:
                    seen.add(title_key)
                    found.append(item)
        found.sort(key=lambda x: x["published_at"], reverse=True)
        news[key] = [dict(item, id=f"{key}-{i}") for i, item in enumerate(found[:8])]
        status[key] = "ok" if found else ("empty" if successes else "failed")
    return news, status


def treasury_csv_url(year: int) -> str:
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
        f"&field_tdr_date_value={year}&page&_format=csv"
    )


def parse_treasury_csv(csv_bytes: bytes, now: datetime) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig", errors="replace")))
    fields = reader.fieldnames or []
    normalized = {re.sub(r"\s+", "", field).lower(): field for field in fields}
    date_field = normalized.get("date")
    y2_field = normalized.get("2yr")
    y10_field = normalized.get("10yr")
    if not date_field or not y2_field or not y10_field:
        raise ValueError("미 재무부 CSV 열 구성이 변경됨")
    max_day = now.astimezone(NY).date()
    records = []
    for record in reader:
        raw_date = (record.get(date_field) or "").strip()
        try:
            day = datetime.strptime(raw_date, "%m/%d/%Y").date()
        except ValueError:
            try:
                day = date.fromisoformat(raw_date)
            except ValueError:
                continue
        if day > max_day:
            continue
        try:
            y2 = float((record.get(y2_field) or "").strip())
            y10 = float((record.get(y10_field) or "").strip())
        except ValueError:
            continue
        if 0 < y2 < 30 and 0 < y10 < 30:
            records.append((day, y2, y10))
    records.sort(key=lambda x: x[0])
    if not records:
        raise ValueError("미 재무부 국채금리 관측값 없음")
    cur, prev = records[-1], records[-2] if len(records) > 1 else None
    collected = now.isoformat()
    result = []
    for idx, symbol, label in ((1, "UST2Y", "미국 국채 2년"), (2, "UST10Y", "미국 국채 10년")):
        value = cur[idx]
        result.append({
            "id": symbol,
            "name": label,
            "value": value,
            "unit": "%",
            "change": round(value - prev[idx], 3) if prev is not None else None,
            "change_unit": "pp",
            "as_of": cur[0].isoformat(),
            "fetched_at": collected,
            "price_type": "official_daily_par_yield",
            "source": "U.S. Department of the Treasury",
            "source_url": TREASURY_SOURCE_URL,
            "freshness_note": "미 재무부 공식 일별 공시 수익률(실시간 시세 아님)",
        })
    return result


def collect_treasury(now: datetime, errors: list[str]) -> list[dict]:
    year = now.astimezone(NY).year
    try:
        return parse_treasury_csv(fetch_bytes(treasury_csv_url(year)), now)
    except (RuntimeError, ValueError) as exc:
        errors.append(f"미국 국채금리 수집 실패: {type(exc).__name__}")
        return []


def safe_previous(target: Path) -> dict:
    if not target.exists():
        return {}
    try:
        obj = json.loads(target.read_text(encoding="utf-8"))
        if obj.get("mode") != "hourly_public_data" or not isinstance(obj.get("market"), list):
            raise ValueError("기존 hourly.json 구조가 잘못됨")
        return obj
    except (OSError, json.JSONDecodeError, UnicodeError, ValueError) as exc:
        raise RuntimeError(f"기존 hourly.json을 해석할 수 없어 보존을 위해 실행 중단: {type(exc).__name__}") from exc


def produce(target: Path, now: datetime | None = None) -> dict:
    now = now or now_kst()
    errors = []
    previous = safe_previous(target)
    news, status = collect_news(now, errors)
    market = collect_treasury(now, errors)
    fresh_news_count = sum(len(items) for items in news.values())
    fresh_market_count = len(market)
    if not market and previous.get("market"):
        market = [dict(item, data_status="previous_snapshot") for item in previous["market"]]
    for topic in TOPICS:
        if status[topic] == "failed" and previous.get("news", {}).get(topic):
            news[topic] = previous["news"][topic]
            status[topic] = "previous_snapshot"
    if not fresh_market_count and not fresh_news_count:
        raise RuntimeError("뉴스·국채금리 수집 모두 실패: 기존 hourly.json 보존")
    return {
        "mode": "hourly_public_data",
        "data_updated_at": now.isoformat(),
        "market": market,
        "news": news,
        "news_status": status,
        "refresh_summary": {
            "fresh_market_items": fresh_market_count,
            "fresh_news_items": fresh_news_count,
            "market_items_visible": len(market),
            "news_items_visible": sum(len(v) for v in news.values()),
            "gemini_called": False,
            "market_source_note": "미 국채 2·10년: 미국 재무부 일별 공시. 국내외 주가지수: 기존 TradingView 위젯 사용(본 파일에서 재게시하지 않음).",
        },
        "errors": errors[:10],
        "source_note": "뉴스: Google 뉴스 RSS 기사 제목·발행처·링크, 원문 분석 아님. 금리: 미국 재무부 공시.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MARKET PULSE hourly non-AI feed")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = produce(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print("hourly refresh:", report["data_updated_at"],
          "treasury=", report["refresh_summary"]["fresh_market_items"],
          "news=", report["refresh_summary"]["fresh_news_items"],
          "gemini_called=false")
    if report["errors"]:
        print("partial source errors:", "; ".join(report["errors"]))


if __name__ == "__main__":
    main()
