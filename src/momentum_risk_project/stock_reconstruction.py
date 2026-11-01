"""Auditable monthly stock-level WML construction and source-quality handling.

This is a research return/holding model. It is not a claim that missing final
payoffs can be recovered from absent data or that unquoted stocks are tradable.
"""

import numpy as np
import pandas as pd
from .ranking import kf_ranking_signals


def price_gap_exclusions(points, intervals, date_column="date"):
    """Flag exact >200-trading-day exclusion intervals; reopening is exclusive.

    Intervals are derived from actual daily TR/BA prices and the independent
    CRSP trading calendar. Do not replace trading days with weekdays or months.
    """
    result = pd.Series(False, index=points.index)
    if intervals.empty:
        return result
    required = {"permno", "exclusion_start_date", "exclusion_end_exclusive"}
    if required - set(intervals):
        raise ValueError("Price intervals need stock, start and exclusive end")
    point_groups = points.groupby("permno", sort=False).groups
    for permno, group in intervals.groupby("permno", sort=False):
        ix = point_groups.get(permno, [])
        if len(ix) == 0:
            continue
        group = group.sort_values("exclusion_start_date")
        starts = pd.to_datetime(group.exclusion_start_date).to_numpy(dtype="datetime64[ns]")
        ends = pd.to_datetime(group.exclusion_end_exclusive).to_numpy(dtype="datetime64[ns]")
        dates = pd.to_datetime(points.loc[ix, date_column]).to_numpy(dtype="datetime64[ns]")
        loc = np.searchsorted(starts, dates, side="right") - 1
        valid = loc >= 0
        valid[valid] &= dates[valid] < ends[loc[valid]]
        result.loc[ix] = valid
    return result


def reconstruct_stock_wml(monthly, *, start="1963-01", end="2011-12", price_intervals=None, ciz_fallback_from="2025-01"):
    """Use point-in-time legacy codes, formation caps and calendar-aligned ranks.

    CIZ classification proxies are not substituted for observed historical
    share/exchange codes. Securities delisted in the formation month are not
    opened as new positions the next month. A holding-month delist is retained.
    Returns and their quality are separate outputs; incomplete payoffs are not
    silently declared complete merely because a numeric return is available.
    """
    required = {"permno", "mthcaldt", "mthcap", "mthprc", "mthret", "mthretx",
                "mthdelflg", "mthretflg", "legacy_shrcd", "legacy_exchcd"}
    if required - set(monthly):
        raise ValueError(f"Missing reconstruction fields: {sorted(required-set(monthly))}")
    m = monthly.copy()
    m["month"] = pd.to_datetime(m.mthcaldt).dt.to_period("M")
    if m.duplicated(["permno", "month"]).any():
        raise ValueError("Duplicate monthly stock records")
    signals = kf_ranking_signals(m)
    eligible = m.legacy_shrcd.isin([10, 11]) & m.legacy_exchcd.isin([1, 2, 3])
    # Legacy msenames stops at 2024. Use an explicitly identified CIZ screen
    # after that date only, never write synthetic codes into the source cache.
    fallback = m.legacy_shrcd.isna() & m.legacy_exchcd.isna() & m.month.ge(pd.Period(ciz_fallback_from, freq="M"))
    ciz_fields = {"securitytype", "securitysubtype", "sharetype", "usincflg", "issuertype", "primaryexch", "conditionaltype", "tradingstatusflg"}
    ciz_ok = pd.Series(False, index=m.index)
    if ciz_fields.issubset(m.columns):
        ciz_ok = (m.securitytype.eq("EQTY") & m.securitysubtype.eq("COM") & m.sharetype.eq("NS")
            & m.usincflg.eq("Y") & m.issuertype.isin(["ACOR", "CORP"]) & m.primaryexch.isin(["N", "A", "Q"])
            & m.conditionaltype.eq("RW") & m.tradingstatusflg.eq("A"))
    eligible |= fallback & ciz_ok
    m["eligibility_source"] = np.where(fallback, "CIZ post-2024 screen (not exact legacy equivalence)", "observed historical share/exchange codes")
    # Formation codes below are algorithmic categories; raw legacy fields remain
    # untouched. CIZ-only observations are tagged through every holding row.
    m["screen_shrcd"] = m.legacy_shrcd.where(~fallback, np.where(m.get("issuertype",pd.Series(index=m.index,dtype=str)).eq("ACOR"),10,11))
    m["screen_exchcd"] = m.legacy_exchcd.where(~fallback, m.get("primaryexch",pd.Series(index=m.index,dtype=str)).map({"N":1,"A":2,"Q":3}))
    # The month-end formation universe cannot include an already delisted issue.
    eligible &= m.mthdelflg.eq("N")
    f = m.loc[eligible, ["permno", "month", "mthcaldt", "mthcap", "screen_shrcd", "screen_exchcd", "eligibility_source"] + (["mthprcdt"] if "mthprcdt" in m else [])].copy()
    f = f.rename(columns={"month": "formation_month", "mthcaldt": "formation_date",
                          "mthcap": "formation_cap", "screen_shrcd": "formation_shrcd",
                          "screen_exchcd": "formation_exchcd", "mthprcdt": "formation_price_date"})
    f["month"] = f.formation_month + 1
    f = f.loc[f.month.between(pd.Period(start, freq="M"), pd.Period(end, freq="M"))]
    f = f.merge(signals, on=["permno", "month"], how="left", validate="one_to_one")
    prices = m[["permno", "month", "mthprc"]].rename(columns={"mthprc": "price_t13"})
    prices["month"] = prices.month + 13
    f = f.merge(prices, on=["permno", "month"], how="left", validate="one_to_one")
    f["excluded_price_gap"] = False
    if price_intervals is not None:
        f["excluded_price_gap"] = price_gap_exclusions(f, price_intervals, "formation_date")
    pre_gap_ok = (f.kf_ranking_valid.fillna(False).astype(bool) & np.isfinite(f.price_t13)
          & f.price_t13.gt(0) & np.isfinite(f.formation_cap) & f.formation_cap.gt(0)
          )
    ok = pre_gap_ok & ~f.excluded_price_gap
    audit = {"formation_candidates": len(f), "formation_candidates_in_price_gap": int(f.excluded_price_gap.sum()),
             "formation_price_gap_exclusions": int((pre_gap_ok & f.excluded_price_gap).sum()),
             "eligible_stock_months": int(ok.sum()),
             "ciz_fallback_eligible_stock_months": int((ok & f.eligibility_source.str.startswith("CIZ")).sum()),
             "admitted_with_missing_price_history": int((ok & ~f.complete_11_month_signal.fillna(False).astype(bool)).sum())}
    f = f.loc[ok].copy()
    bp = f.loc[f.formation_exchcd.eq(1)].groupby("month").momentum_signal.quantile(np.arange(.1, 1, .1)).unstack()
    bp.columns = [f"q{i}" for i in range(1, 10)]
    expected = pd.period_range(start, end, freq="M")
    if not bp.index.equals(expected):
        raise ValueError("Missing NYSE breakpoint month; inspect input history")
    f = f.merge(bp, left_on="month", right_index=True, validate="many_to_one")
    if not np.isfinite(f[bp.columns].to_numpy()).all():
        raise ValueError("Nonfinite NYSE breakpoints")
    f["momentum_decile"] = 1
    for col in bp.columns:
        f["momentum_decile"] += (f.momentum_signal > f[col]).astype(int)
    f = f.drop(columns=bp.columns)
    cols = [c for c in ("permno", "month", "mthcaldt", "mthret", "mthretx", "mthretflg",
                       "mthdelflg", "mthprc", "mthprcdt", "mthprcflg", "tradingstatusflg") if c in m]
    h = f.merge(m[cols], on=["permno", "month"], how="left", validate="one_to_one", indicator=True)
    h["holding_record_exists"] = h.pop("_merge").eq("both")
    h["leg_weight"] = h.formation_cap / h.groupby(["month", "momentum_decile"]).formation_cap.transform("sum")
    h["numeric_return_available"] = np.isfinite(h.mthret) & h.mthret.ge(-1)
    h["payoff_complete"] = h.mthdelflg.isin(["N", "A", "P"])
    h["return_as_published"] = h.mthret.where(h.numeric_return_available)
    h["return_strict"] = h.return_as_published.where(h.payoff_complete)
    h["return_resolution"] = np.select(
        [~h.holding_record_exists, ~h.numeric_return_available, ~h.payoff_complete],
        ["holding_record_absent", "numeric_return_missing", "incomplete_delisting_payoff"],
        default="published_return_complete_by_flags")
    audit["missing_numeric_wml_stock_months"] = int((h.momentum_decile.isin([1, 10]) & ~h.numeric_return_available).sum())
    return h, bp, audit


def attach_delisting_evidence(holdings, delists):
    """Recover recorded excluded payoffs once; never double-count A/P/V returns.

    For G/M, a finite recorded DelRet is compounded with a finite published
    pre-delisting aggregate, with attribution at the delisting month (DM-style
    research convention). DelRet already included under A/P is not added again.
    Missing terminal values and partial V payoffs stay unresolved in strict data.
    This does not simulate delayed cash settlement at DelAmtDt.
    """
    h = holdings.copy()
    d = delists.copy()
    d["month"] = pd.to_datetime(d.delistingdt).dt.to_period("M")
    if d.duplicated(["permno", "month"]).any():
        raise ValueError("Multiple delistings in a stock-month require event-level treatment")
    cols = [c for c in ["permno", "month", "delistingdt", "delret", "delretmisstype",
                        "delnextdt", "delnextprc", "delamtdt", "deldivamt", "deldlydt"] if c in d]
    h = h.merge(d[cols], on=["permno", "month"], how="left", validate="many_to_one")
    recoverable = h.mthdelflg.isin(["G", "M"]) & h.numeric_return_available & np.isfinite(h.delret) & h.delret.ge(-1)
    h.loc[recoverable, "return_strict"] = (1 + h.loc[recoverable, "mthret"]) * (1 + h.loc[recoverable, "delret"]) - 1
    h.loc[recoverable, "payoff_complete"] = True
    h.loc[recoverable, "return_resolution"] = "recorded_excluded_delisting_return_added_once"
    h["unresolved_final_payoff"] = h.mthdelflg.isin(["M", "G", "V"]) & ~h.payoff_complete
    return h


def portfolio_returns(holdings, return_column="return_strict"):
    """Strict full-denominator decile returns; unknown stocks invalidate a leg."""
    h = holdings.copy()
    good = np.isfinite(h[return_column]) & h[return_column].ge(-1)
    h["unknown_return"] = ~good
    h["contribution"] = h.leg_weight * h[return_column]
    p = h.groupby(["month", "momentum_decile"]).agg(
        portfolio_return=("contribution", "sum"), unknown_stocks=("unknown_return", "sum"),
        n_stocks=("permno", "size"))
    p["portfolio_return"] = p.portfolio_return.where(p.unknown_stocks.eq(0))
    w = p.portfolio_return.unstack().reindex(columns=range(1, 11))
    w.columns = [f"P{i}" for i in range(1, 11)]
    w["WML"] = w.P10 - w.P1
    return w, p


def scenario_returns(holdings, assumed_unresolved_return):
    """Explicit sensitivity for unobserved stock-month totals, never baseline data."""
    if not np.isfinite(assumed_unresolved_return) or assumed_unresolved_return < -1:
        raise ValueError("Scenario stock total return must be finite and >= -1")
    h = holdings.copy()
    h["return_scenario"] = h.return_strict.fillna(assumed_unresolved_return)
    h["scenario_imputed"] = h.return_strict.isna()
    return h
