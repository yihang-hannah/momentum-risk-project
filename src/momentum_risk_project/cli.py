"""Reproducible local-data CLI: python -m momentum_risk_project.cli."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .backtest import run_backtest
from .data import clean_momentum, load_wml_decile_returns


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily", type=Path, help="Parquet with decimal mom column")
    parser.add_argument("--monthly", type=Path, help="Parquet with decimal mom column")
    parser.add_argument("--raw-deciles", action="store_true",
                        help="Input Parquets are raw percent-unit ten-decile tables")
    parser.add_argument("--transaction-cost-bps", type=float, default=0)
    parser.add_argument("--financing-cost-bps", type=float, default=0)
    parser.add_argument("--target-volatility", type=float, default=0.12)
    parser.add_argument("--leverage-cap", type=float)
    parser.add_argument("--window", type=int, default=126)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New directory; existing directories are never overwritten")
    args = parser.parse_args(argv)
    if bool(args.daily) != bool(args.monthly):
        parser.error("--daily and --monthly must be supplied together")
    if args.raw_deciles and not args.daily:
        parser.error("--raw-deciles requires --daily and --monthly")
    if args.output_dir.exists():
        parser.error("output directory already exists; choose a new path")
    if args.daily:
        daily_frame = pd.read_parquet(args.daily)
        monthly_frame = pd.read_parquet(args.monthly)
        if args.raw_deciles:
            daily_frame = clean_momentum(daily_frame, "daily")
            monthly_frame = clean_momentum(monthly_frame, "monthly")
        daily = daily_frame["mom"]
        monthly = monthly_frame["mom"]
    else:
        daily, monthly = load_wml_decile_returns()
    kwargs = {key: getattr(args, key) for key in (
        "transaction_cost_bps", "financing_cost_bps", "target_volatility",
        "leverage_cap", "window", "start", "end")}
    ledger, summary = run_backtest(daily, monthly, **kwargs)
    metadata = dict(kwargs)
    metadata["raw_deciles"] = args.raw_deciles
    metadata["inputs"] = {}
    for label, series in (("daily", daily), ("monthly", monthly)):
        metadata["inputs"][label] = {
            "path": str(getattr(args, label)) if getattr(args, label) else "data.py loader",
            "sha256": hashlib.sha256(series.to_csv().encode()).hexdigest(),
            "count": len(series), "first": str(series.index[0]), "last": str(series.index[-1]),
        }
    metadata["evaluation"] = {"first": str(ledger.loc["managed"].index[0]),
                              "last": str(ledger.loc["managed"].index[-1])}
    metadata["pandas_version"] = pd.__version__
    args.output_dir.mkdir(parents=True, exist_ok=False)
    ledger.to_csv(args.output_dir / "monthly_ledger.csv")
    summary.to_csv(args.output_dir / "summary.csv")
    (args.output_dir / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(summary.to_string())
    print(f"Saved results to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
