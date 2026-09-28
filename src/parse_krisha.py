#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from dataclasses import dataclass, asdict, fields
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from regions import BY_CODE, require_code


SECTIONS = {"sale": "prodazha", "rent": "arenda"}
BASE = "https://krisha.kz/{section}/kvartiry/{slug}/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

MIN_DELAY, MAX_DELAY = 1.2, 2.8
TIMEOUT = 25
MAX_RETRIES = 4

PAGE_SIZE = 20
MAX_PAGES = 50
HARD_CAP = PAGE_SIZE * MAX_PAGES


@dataclass
class Listing:
    listing_id: str
    deal: str
    region_code: str
    city: str
    address: str
    rooms: int
    area_m2: float
    floor: int | None
    floors_total: int | None
    price_kzt: int
    price_per_m2: int
    url: str
    scraped_at: str


TITLE_RE = re.compile(
    r"(\d+)\s*-\s*комнатн\w*\s+кварти\w*"
    r"\s*·\s*([\d.,]+)\s*м²"
    r"(?:\s*·\s*(\d+)\s*/\s*(\d+)\s*этаж)?",
    re.IGNORECASE,
)

CITY_RE = re.compile(r"^(.*?)\s+(?:\d{1,2}\s|сегодня|вчера)", re.IGNORECASE)

TOTAL_RE = re.compile(r"Найдено\s+(\d[\d\s]*)")

DAILY_RE = re.compile(r"за\s+сутк", re.IGNORECASE)


def page_data(soup) -> dict:
    tag = soup.find("script", id="jsdata")
    text = tag.string if tag else None
    if not text:
        return {}
    m = re.search(r"window\.data\s*=\s*", text)
    if not m:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[m.end():])
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}


def search_meta(soup) -> tuple[set[str], int | None]:
    d = page_data(soup).get("search") or {}
    ids = {str(i) for i in (d.get("ids") or [])}
    count = ((d.get("analytics") or {}).get("default") or {}).get("count")
    return ids, count


def _text(node) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def is_complex_promo(card) -> bool:
    if card.select_one(".a-card__complex-label"):
        return True
    price = _text(card.select_one(".a-card__price"))
    return price.startswith("от ")


def is_daily_rent(card) -> bool:
    return bool(DAILY_RE.search(_text(card.select_one(".a-card__price"))))


def parse_card(card, deal: str, region_code: str, today: str) -> Listing | None:
    if is_complex_promo(card) or is_daily_rent(card):
        return None

    listing_id = card.get("data-id")
    title = _text(card.select_one(".a-card__title"))
    m = TITLE_RE.search(title)
    if not m or not listing_id:
        return None

    rooms = int(m.group(1))
    area = float(m.group(2).replace(",", "."))
    floor = int(m.group(3)) if m.group(3) else None
    floors_total = int(m.group(4)) if m.group(4) else None

    price_digits = re.sub(r"\D", "", _text(card.select_one(".a-card__price")))
    if not price_digits or area <= 0:
        return None
    price = int(price_digits)

    stats = _text(card.select_one(".a-card__stats"))
    cm = CITY_RE.match(stats)
    city = (cm.group(1) if cm else stats.split(" ")[0]).strip()

    return Listing(
        listing_id=listing_id,
        deal=deal,
        region_code=region_code,
        city=city,
        address=_text(card.select_one(".a-card__subtitle")),
        rooms=rooms,
        area_m2=area,
        floor=floor,
        floors_total=floors_total,
        price_kzt=price,
        price_per_m2=round(price / area),
        url=f"https://krisha.kz/a/show/{listing_id}",
        scraped_at=today,
    )


def parse_page(html: str, deal: str, region_code: str, today: str):
    soup = BeautifulSoup(html, "lxml")
    real_ids, count = search_meta(soup)

    cards = soup.select("div.a-card[data-id]")

    listings, n_complex, n_daily, n_failed, n_filler = [], 0, 0, 0, 0
    for card in cards:
        if count is not None and card.get("data-id") not in real_ids:
            n_filler += 1
            continue
        if is_complex_promo(card):
            n_complex += 1
            continue
        if is_daily_rent(card):
            n_daily += 1
            continue
        item = parse_card(card, deal, region_code, today)
        if item is None:
            n_failed += 1
        else:
            listings.append(item)

    stats = {"cards": len(cards), "filler": n_filler, "complex": n_complex,
             "daily": n_daily, "failed": n_failed, "ok": len(listings),
             "no_meta": count is None}
    return listings, stats, count


def build_url(region_code: str, deal: str = "sale", page: int = 1,
              rooms: int | None = None, area_from: float | None = None,
              area_to: float | None = None) -> str:
    if deal not in SECTIONS:
        raise ValueError(f"deal должен быть sale или rent, а не {deal!r}")
    region = BY_CODE[require_code(region_code)]
    url = BASE.format(section=SECTIONS[deal], slug=region.krisha_oblast)
    params = []
    if rooms:
        params.append(f"das[live.rooms]={rooms}")
    if area_from:
        params.append(f"das[live.square][from]={area_from:g}")
    if area_to:
        params.append(f"das[live.square][to]={area_to:g}")
    if page > 1:
        params.append(f"page={page}")
    return url + ("?" + "&".join(params) if params else "")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch(session: requests.Session, url: str) -> str:
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        resp = session.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        last = resp.status_code
        if resp.status_code in (429, 500, 502, 503, 504):
            wait = 2 ** attempt + random.uniform(0, 1.5)
            print(f"    HTTP {resp.status_code}, жду {wait:.1f}с "
                  f"(попытка {attempt}/{MAX_RETRIES})", file=sys.stderr)
            time.sleep(wait)
            continue
        break
    raise RuntimeError(f"Не удалось получить {url} (последний статус {last})")


def polite_sleep() -> None:
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def warn_cap(total: int | None, region_code: str) -> None:
    if total and total > HARD_CAP:
        print(f"  ⚠️  {region_code}: найдено {total}, а Krisha отдаст максимум "
              f"{HARD_CAP}. Нужна нарезка по площади — см. warn_cap() в коде.")


DEAL_LABEL = {"sale": "продажа", "rent": "аренда (помесячно)"}


def dry_run(region_code: str, deal: str, rooms: int | None) -> None:
    code = require_code(region_code)
    region = BY_CODE[code]
    url = build_url(code, deal=deal, page=1, rooms=rooms)
    today = date.today().isoformat()

    print(f"Регион : {region.name_ru}  (krisha: {region.krisha_oblast})")
    print(f"Раздел : {DEAL_LABEL[deal]}")
    print(f"URL    : {url}\n")

    session = make_session()
    t0 = time.time()
    html = fetch(session, url)
    listings, stats, total = parse_page(html, deal, code, today)

    print(f"Ответ  : {len(html):,} байт за {time.time() - t0:.1f}с")
    print(f"Найдено по запросу : {total if total else '—'}")
    print(f"Карточек на странице: {stats['cards']}")
    print(f"  из них реклама ЖК : {stats['complex']}")
    print(f"  посуточная аренда : {stats['daily']}")
    print(f"  добивка не по запросу: {stats['filler']}")
    print(f"  не распарсилось   : {stats['failed']}")
    print(f"  годных объявлений : {stats['ok']}\n")
    warn_cap(total, code)

    if not listings:
        print("Ни одного объявления не разобрано — вёрстка изменилась. "
              "Пришли мне этот вывод.")
        return

    unit = "₸/мес" if deal == "rent" else "₸"
    print(f"{'комн':<5} {'м²':>7} {'этаж':>7} {unit:>14} {'₸/м²':>10}  адрес")
    print("-" * 78)
    for x in listings[:10]:
        fl = f"{x.floor}/{x.floors_total}" if x.floor else "—"
        print(f"{x.rooms:<5} {x.area_m2:>7.1f} {fl:>7} "
              f"{x.price_kzt:>14,} {x.price_per_m2:>10,}  {x.address[:28]}")

    prices = sorted(x.price_kzt for x in listings)
    mid = prices[len(prices) // 2]
    print(f"\nМедиана по этой странице: {mid:,} {unit}  "
          f"(разброс {prices[0]:,} – {prices[-1]:,})")
    print("Это одна страница из выдачи, а не рынок региона. "
          "Медиана здесь — только проверка, что цифры осмысленные.")


def crawl(region_code: str, deal: str, rooms: int | None,
          pages: int, out_dir: Path) -> None:
    code = require_code(region_code)
    today = date.today().isoformat()
    session = make_session()

    all_rows: list[Listing] = []
    seen: set[str] = set()
    for page in range(1, min(pages, MAX_PAGES) + 1):
        url = build_url(code, deal=deal, page=page, rooms=rooms)
        html = fetch(session, url)
        listings, stats, total = parse_page(html, deal, code, today)
        if page == 1:
            warn_cap(total, code)

        fresh = [x for x in listings if x.listing_id not in seen]
        seen.update(x.listing_id for x in fresh)
        all_rows.extend(fresh)

        print(f"  стр. {page:>2}: +{len(fresh):>2} новых "
              f"(ЖК {stats['complex']}, сутки {stats['daily']}, "
              f"добивка {stats['filler']}, брак {stats['failed']}) "
              f"— всего {len(all_rows)}")

        if stats["ok"] == 0:
            print("  пустая страница — выдача кончилась")
            break
        polite_sleep()

    if not all_rows:
        print("Ничего не собрано.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    suffix = f"_r{rooms}" if rooms else ""
    path = out_dir / f"krisha_{deal}_{code}{suffix}_{stamp}.csv"

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[fl.name for fl in fields(Listing)])
        writer.writeheader()
        writer.writerows(asdict(x) for x in all_rows)

    print(f"\n{len(all_rows)} объявлений -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Парсер krisha.kz")
    ap.add_argument("--region", required=True,
                    help="код региона из regions.py (sko, almaty, atyrau …)")
    ap.add_argument("--deal", choices=["sale", "rent"], default="sale",
                    help="продажа или помесячная аренда")
    ap.add_argument("--rooms", type=int, choices=[1, 2, 3, 4, 5],
                    help="фильтр по числу комнат")
    ap.add_argument("--dry-run", action="store_true",
                    help="одна страница, подробный отчёт, ничего не сохранять")
    ap.add_argument("--pages", type=int, default=3,
                    help="сколько страниц собрать в обычном режиме (по 20 объявлений)")
    ap.add_argument("--out", default="data/raw", help="куда положить CSV")
    args = ap.parse_args()

    if args.dry_run:
        dry_run(args.region, args.deal, args.rooms)
    else:
        crawl(args.region, args.deal, args.rooms, args.pages, Path(args.out))


if __name__ == "__main__":
    main()
