"""KF-style 12-2 ranking eligibility with explicit missing-price classification."""

import numpy as np
import pandas as pd


def kf_ranking_signals(data: pd.DataFrame) -> pd.DataFrame:
    """Return holding-month-indexed ranking signals and missingness diagnostics.

    KF allows legacy -99.0 missing-price codes during t-12 through t-3,
    but requires a good numeric return at t-2. An optional
    legacy_return_missing_code column preserves those original codes separately
    from decimal returns. Other legacy codes are not allowed.

    CIZ does not preserve those legacy codes. In their absence, the explicitly
    labeled CIZ adapter identifies a missing-price observation only when return
    is missing, MthRetFlg=NT, MthPrcFlg=MP, price is missing, and MthDelFlg=N.
    This is a semantic missing-price classification, not a demonstrated
    one-to-one legacy -99 mapping. An unknown missing reason remains ineligible.

    Allowed missing observations are omitted from the cumulative product of
    observed returns, not converted into observed zero-return data. KF's public
    details page states eligibility but does not fully document that aggregation
    implementation. Absent calendar records are not inferred to be allowed gaps.
    """
    required = {"permno", "month", "mthret"}
    if required - set(data):
        raise ValueError(f"Missing ranking columns: {sorted(required - set(data))}")
    x = data.copy()
    x["month"] = pd.PeriodIndex(x["month"], freq="M")
    if x[["permno", "month"]].isna().any().any():
        raise ValueError("Stock and month identifiers must be nonmissing")
    if x.duplicated(["permno", "month"]).any():
        raise ValueError("Duplicate stock-month records")
    x = x.sort_values(["permno", "month"]).reset_index(drop=True)
    returns = pd.to_numeric(x["mthret"], errors="raise")
    valid = np.isfinite(returns) & returns.ge(-1)
    if "legacy_return_missing_code" in x:
        code = pd.to_numeric(x["legacy_return_missing_code"], errors="raise")
        valid &= code.isna()
        allowed = returns.isna() & code.eq(-99.0)
        adapter = "explicit legacy missing-return code"
    else:
        fields = {"mthretflg", "mthprcflg", "mthprc", "mthdelflg"}
        allowed = pd.Series(False, index=x.index)
        if fields.issubset(x.columns):
            allowed = (returns.isna() & x["mthretflg"].eq("NT")
                       & x["mthprcflg"].eq("MP") & x["mthprc"].isna()
                       & x["mthdelflg"].eq("N"))
        adapter = "CIZ flag-based missing-price classification (legacy equivalence unverified)"
    log_returns = pd.Series(0.0, index=x.index)
    positive_gross = valid & returns.gt(-1)
    log_returns.loc[positive_gross] = np.log1p(returns.loc[positive_gross])
    work = x[["permno", "month"]].copy()
    work["valid"] = valid.astype(int)
    work["allowed"] = allowed.astype(int)
    work["unresolved"] = (~valid & ~allowed).astype(int)
    work["total_loss"] = (valid & returns.eq(-1)).astype(int)
    work["log_return"] = log_returns
    g = work.groupby("permno", sort=False)
    sums = {}
    for col in ("valid", "allowed", "unresolved", "total_loss", "log_return"):
        sums[col] = g[col].transform(lambda s: s.rolling(11, min_periods=11).sum())
    first = g["month"].shift(10)
    consecutive = first.notna() & (work["month"].astype("int64") - first.astype("int64")).eq(10)
    eligible = consecutive & sums["unresolved"].eq(0) & valid
    signal = sums["log_return"].where(eligible)
    signal.loc[eligible & sums["total_loss"].gt(0)] = -np.inf
    out = work[["permno", "month"]].copy()
    out["month"] = out["month"] + 2
    out["momentum_log"] = signal
    out["momentum_signal"] = np.expm1(signal)
    out["complete_11_month_signal"] = consecutive & sums["valid"].eq(11)
    out["observed_ranking_returns"] = sums["valid"]
    out["allowed_missing_price_months"] = sums["allowed"]
    out["unresolved_ranking_months"] = sums["unresolved"]
    out["ranking_calendar_complete"] = consecutive
    out["kf_ranking_valid"] = eligible
    out["ranking_missing_adapter"] = adapter
    return out
