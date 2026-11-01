"""Appendix B leg-normalized turnover, separate from funded account trades.

The local paper prints inverse L in equation 10 despite scaling returns by L.
Expose that literal convention and economically scaled positions separately.
Neither diagnostic is the self-funded NAV account in stock_backtest.py.
"""
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import t as student_t


def appendix_b_turnover(holdings, weights, *, return_column="return_reference"):
    """Return stock transitions and monthly turnover; total-return leg drift.

    Timing: prior holding-month returns drift into current start-of-month trade.
    Include the union of old/new members, including leg switches as exit+entry.
    Charge initial establishment from zero; do not charge terminal liquidation.
    Unknown prior returns invalidate that transition, never become zero.
    Literal eq10 uses 1/L; scaled_positions uses L, matching return exposure.
    """
    if (not isinstance(weights.index, pd.PeriodIndex) or weights.index.freqstr != "M"
        or not weights.index.is_unique or not weights.index.is_monotonic_increasing
        or weights.empty or not weights.index.equals(pd.period_range(weights.index[0], weights.index[-1], freq="M"))):
        raise ValueError("Weights need unique consecutive monthly periods")
    if not np.isfinite(weights).all() or weights.le(0).any():
        raise ValueError("Appendix inverse-L convention needs positive finite weights")
    h=holdings.loc[holdings.momentum_decile.isin([1,10]) & holdings.month.isin(weights.index),
        ["month","permno","momentum_decile","leg_weight",return_column]].copy()
    if h.duplicated(["month","permno"]).any():raise ValueError("Duplicate stock-month")
    sums=h.groupby(["month","momentum_decile"]).leg_weight.sum().unstack()
    if not sums.index.equals(weights.index) or set(sums.columns)!={1,10} or not np.allclose(sums,1):
        raise ValueError("Both complete normalized legs required in every month")
    if not np.isfinite(h.leg_weight).all() or h.leg_weight.le(0).any():raise ValueError("Invalid leg weights")
    r=h[return_column]
    valid=np.isfinite(r)&r.ge(-1)
    h["drift_value"]=(h.leg_weight*(1+r)).where(valid)
    denom=h.groupby(["month","momentum_decile"]).drift_value.transform(lambda x:x.sum(min_count=len(x)))
    h["prior_weight"]=h.drift_value/denom.where(denom.gt(0))
    prior=h[["month","permno","momentum_decile","prior_weight"]].copy()
    prior["month"]+=1
    cur=h[["month","permno","momentum_decile","leg_weight"]]
    trades=cur.merge(prior,on=["month","permno","momentum_decile"],how="outer",indicator=True)
    trades=trades.loc[trades.month.isin(weights.index)].copy()
    # Only absent membership is zero. Unknown weights on existing holdings remain unknown.
    trades.loc[trades._merge.eq("right_only"),"leg_weight"]=0.
    trades.loc[trades._merge.eq("left_only"),"prior_weight"]=0.
    trades["L"]=trades.month.map(weights)
    trades["previous_L"]=trades.month.map(weights.shift()).fillna(weights.iloc[0])
    trades["unmanaged_half_trade"]=.5*(trades.leg_weight-trades.prior_weight).abs()
    trades["scaled_positions_half_trade"]=.5*(trades.leg_weight*trades.L-trades.prior_weight*trades.previous_L).abs()
    trades["literal_eq10_half_trade"]=.5*(trades.leg_weight/trades.L-trades.prior_weight/trades.previous_L).abs()
    cols=["unmanaged_half_trade","scaled_positions_half_trade","literal_eq10_half_trade"]
    monthly=trades.groupby("month")[cols].agg(lambda x:x.sum(min_count=len(x)))
    # A missing return anywhere in a previous leg invalidates even newly entering stock transitions.
    leg_known=h.groupby(["month","momentum_decile"]).prior_weight.agg(lambda x:x.notna().all()).unstack()
    known=leg_known.all(axis=1).shift(fill_value=True)
    monthly.loc[~known,cols]=np.nan
    monthly["initial_establishment"]=monthly.index==weights.index[0]
    return trades.drop(columns="_merge"),monthly


def cutoff_roundtrip_bps(returns, turnover, *, confidence=.95):
    """IID two-sided Student-t cutoff for r_net=r-c*x, not a paper-exact SE claim.

    Return NaN for incomplete data; zero if already insignificant. Costs scale
    monthly turnover, not its average, so their effect on volatility is retained.
    """
    if not returns.index.equals(turnover.index):raise ValueError("Mismatched calendars")
    if len(returns)<3 or not np.isfinite(returns).all() or not np.isfinite(turnover).all():return np.nan
    if turnover.lt(0).any() or not turnover.gt(0).any():return np.nan
    if not 0<confidence<1:raise ValueError("Invalid confidence")
    critical=student_t.ppf((1+confidence)/2,len(returns)-1)
    def f(c):
        n=returns-c*turnover
        s=n.std(ddof=1)
        return n.mean()*np.sqrt(len(n))/s-critical if s>0 else (np.inf if n.mean()>0 else -critical)
    if f(0)<=0:return 0.
    hi=max(returns.mean()/turnover.mean(),1e-8)
    return brentq(f,0,hi)*10000
