#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import asdict, fields
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from regions import REGIONS, BY_CODE, require_code
from parse_krisha import (
    Listing, build_url, fetch, make_session, parse_page, polite_sleep,
    search_meta, PAGE_SIZE, MAX_PAGES, HARD_CAP,
)


AREA_EDGES = [25, 30, 35, 40, 45, 50, 60, 70, 85, 110]

EPS = 0.01


def _build_bins(edges: list[int], eps: float = EPS):
    bins: list[tuple[float | None, float | None]] = [(None, float(edges[0]))]
    for lo, hi in zip(edges, edges[1:]):
        bins.append((lo + eps, float(hi)))
    bins.append((edges[-1] + eps, None))
    return bins


AREA_BINS = _build_bins(AREA_EDGES)


PAGES_PER_BIN = 5


def pick_pages(pages_available: int, want: int) -> list[int]:
    if pages_available <= want:
        return list(range(1, pages_available + 1))
    step = pages_available / want
    return sorted({int(i * step) + 1 for i in range(want)})


def bin_label(lo, hi) -> str:
    lo_r = None if lo is None else round(lo)
    if lo_r is None:
        return f"до {hi:g}"
    if hi is None:
        return f"{lo_r:g}+"
    return f"{lo_r:g}–{hi:g}"


def probe(session, region_code: str, deal: str, lo, hi) -> int | None:
    url = build_url(region_code, deal=deal, page=1, area_from=lo, area_to=hi)
    soup = BeautifulSoup(fetch(session, url), "lxml")
    _, count = search_meta(soup)
    return count


def crawl_bin(session, region_code: str, deal: str, lo, hi, today: str,
              pages: list[int], seen: set[str]) -> tuple[list[Listing], int, bool, int]:
    rows: list[Listing] = []
    fetched, exhausted, filler = 0, False, 0
    for page in pages:
        url = build_url(region_code, deal=deal, page=page,
                        area_from=lo, area_to=hi)
        listings, stats, _ = parse_page(fetch(session, url), deal,
                                        region_code, today)
        fetched += 1
        filler += stats["filler"]

        if stats["no_meta"]:
            print("    ⚠ не удалось прочитать window.data — вёрстка изменилась, "
                  "фильтр добивки отключён. Останови прогон и скажи мне.")

        fresh = [x for x in listings if x.listing_id not in seen]
        seen.update(x.listing_id for x in fresh)
        rows.extend(fresh)

        if stats["ok"] == 0:
            exhausted = True
            break
        polite_sleep()
    return rows, fetched, exhausted, filler


def run_region(session, region_code: str, deal: str, out_dir: Path,
               pages_per_bin: int, plan_only: bool) -> dict:
    code = require_code(region_code)
    region = BY_CODE[code]
    today = date.today().isoformat()

    print(f"\n{region.short}  ({deal})")
    strata, rows, seen = [], [], set()
    req_estimate = 0

    for lo, hi in AREA_BINS:
        total = probe(session, code, deal, lo, hi)
        req_estimate += 1
        polite_sleep()

        pages_if_spread = 0 if not total else min(-(-total // PAGE_SIZE), MAX_PAGES)
        if pages_if_spread > pages_per_bin:
            pages = pick_pages(pages_if_spread, pages_per_bin)
        else:
            pages = list(range(1, pages_per_bin + 1))

        rows_before = len(rows)
        fetched, exhausted, filler = 0, False, 0
        if not plan_only:
            got, fetched, exhausted, filler = crawl_bin(
                session, code, deal, lo, hi, today, pages, seen)
            rows.extend(got)
        req_estimate += fetched if not plan_only else len(pages)

        collected = len(rows) - rows_before
        strata.append({
            "region_code": code, "deal": deal,
            "area_from": lo if lo is not None else "",
            "area_to": hi if hi is not None else "",
            "rows_collected": collected,
            "exhausted": exhausted,
            "pages_fetched": fetched,
            "pages_list": " ".join(map(str, pages)),
            "filler_dropped": filler,
            "total_found": total if total is not None else "",
            "scraped_at": today,
        })

        if plan_only:
            print(f"  {bin_label(lo, hi):>9} м² : всего {str(total or 0):>6} "
                  f"→ взяли бы {len(pages)} стр.")
            continue

        mark = " (всё)" if exhausted else ""
        pad = f"  добивки отброшено {filler}" if filler else ""
        print(f"  {bin_label(lo, hi):>9} м² : {collected:>4} из {total or 0} "
              f"за {fetched} стр.{mark}{pad}")

    if plan_only:
        return {"requests": req_estimate, "rows": 0}

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"krisha_{deal}_{code}_{stamp}"

    with (base.with_name(base.name + ".csv")).open(
            "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[fl.name for fl in fields(Listing)])
        w.writeheader()
        w.writerows(asdict(x) for x in rows)

    with (base.with_name(base.name + "_strata.csv")).open(
            "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(strata[0].keys()))
        w.writeheader()
        w.writerows(strata)

    by_rooms = {}
    for x in rows:
        by_rooms[x.rooms] = by_rooms.get(x.rooms, 0) + 1
    breakdown = " ".join(f"{k}к:{v}" for k, v in sorted(by_rooms.items()))
    n_exh = sum(1 for s in strata if s["exhausted"])
    weights = sum(s["total_found"] for s in strata
                  if isinstance(s["total_found"], int))
    print(f"  собрано {len(rows)} ({breakdown}) → {base.name}.csv")
    print(f"  полос выбрано целиком: {n_exh} из {len(strata)} "
          f"— для них вес точный")
    if n_exh == len(strata):
        delta = weights - len(rows)
        flag = "  ⚠ полосы перекрываются!" if abs(delta) > 2 else "  ✓"
        print(f"  сумма весов {weights} против {len(rows)} собранных{flag}")
    else:
        print(f"  сумма весов {weights} (часть полос не выбрана до конца)")

    return {"requests": req_estimate, "rows": len(rows)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Обход регионов на krisha.kz")
    ap.add_argument("--regions", default="all",
                    help="'all' или список кодов через запятую: sko,almaty")
    ap.add_argument("--deal", choices=["sale", "rent", "both"], default="both")
    ap.add_argument("--pages-per-bin", type=int, default=PAGES_PER_BIN)
    ap.add_argument("--plan-only", action="store_true",
                    help="только посчитать объёмы и веса, ничего не качать")
    ap.add_argument("--out", default="data/raw")
    args = ap.parse_args()

    codes = ([r.code for r in REGIONS] if args.regions == "all"
             else [require_code(c.strip()) for c in args.regions.split(",")])
    deals = ["sale", "rent"] if args.deal == "both" else [args.deal]

    session = make_session()
    t0 = time.time()
    total_req = total_rows = 0

    for deal in deals:
        for code in codes:
            try:
                res = run_region(session, code, deal, Path(args.out),
                                 args.pages_per_bin, args.plan_only)
                total_req += res["requests"]
                total_rows += res["rows"]
            except Exception as exc:
                print(f"  ✗ {code}/{deal}: {exc}", file=sys.stderr)

    mins = (time.time() - t0) / 60
    print(f"\n{'—' * 60}")
    if args.plan_only:
        jobs = len(codes) * len(deals)
        per_job = total_req / jobs if jobs else 0
        est_here = total_req * 2.0 / 60
        all_jobs = len(REGIONS) * 2
        est_all = per_job * all_jobs * 2.0 / 60
        print(f"Разведано заданий: {jobs} — {total_req} запросов, "
              f"{mins:.1f} мин (сбор занял бы ~{est_here:.0f} мин)")
        print(f"В среднем на задание: {per_job:.0f} запросов")
        print(f"ЭКСТРАПОЛЯЦИЯ на все {all_jobs} заданий (20 регионов × 2 сделки): "
              f"~{per_job * all_jobs:.0f} запросов ≈ {est_all:.0f} мин "
              f"({est_all / 60:.1f} ч)")
    else:
        print(f"{total_rows} объявлений, {total_req} запросов, {mins:.1f} мин")


if __name__ == "__main__":
    main()
