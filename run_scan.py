"""Scan the SET100 and write a report.

    python run_scan.py              # report -> reports/set100_<date>.md, table -> .csv
    python run_scan.py --top 15
"""
import argparse
from pathlib import Path

from thai_stocks.data import INDEX_SYMBOL, download, load_universe
from thai_stocks.report import build_report
from thai_stocks.scanner import daily_metrics, intraday_profile, scan, sector_summary, signal_lists


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=10, help="rows per watchlist")
    p.add_argument("--out", default="reports")
    a = p.parse_args()

    universe = load_universe()
    symbols = universe["symbol"].tolist()
    daily = download(symbols + [INDEX_SYMBOL], period="1y", interval="1d")
    intraday = download(symbols + [INDEX_SYMBOL], period="60d", interval="15m")

    set_d, set_i = daily.pop("^SET", None), intraday.pop("^SET", None)
    res = scan(daily, intraday, universe)
    lists = signal_lists(res, a.top)
    as_of = res["date"].max()
    report = build_report(
        res, lists, sector_summary(res),
        intraday_profile(set_i) if set_i is not None else None,
        as_of, res["last_bar"].max() if "last_bar" in res else "-",
        daily_metrics(set_d) if set_d is not None else None,
    )

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"set100_{as_of}.md").write_text(report, encoding="utf-8")
    res.to_csv(out / f"set100_{as_of}.csv")
    print(report)
    print(f"\nScanned {len(res)}/{len(symbols)} stocks -> {out}/set100_{as_of}.md and .csv")


if __name__ == "__main__":
    main()
