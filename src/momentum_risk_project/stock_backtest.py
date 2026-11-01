"""Monthly stock account with self-funded trading fees and explicit unknown states."""
import numpy as np
import pandas as pd
from scipy.optimize import brentq


def simulate_stock_account(holdings, factor_weights, *, return_column="return_strict",
                           transaction_cost_bps=0.0, financing_cost_bps=0.0):
    """Return monthly account and stock trades without bridging unknown NAV.

    Targets are weights of AFTER-trading-cost NAV. Solve x + fee*sum|x*q-p|=1,
    where x is post-cost/pre-cost NAV and p is the drifted pretrade stock weight.
    Total returns drive P&L; ex-distribution returns drive stock price drift.
    Their difference is assigned to cash (monthly approximation to distribution
    timing). Known/sensitivity terminal payoffs settle at the delisting month;
    delayed payment timing and intra-month reinvestment trades are not modeled.
    An incomplete input stops account evaluation rather than restarting it.
    """
    for value in (transaction_cost_bps, financing_cost_bps):
        if not np.isfinite(value) or value < 0:
            raise ValueError("Costs must be finite and nonnegative")
    h = holdings.loc[holdings.momentum_decile.isin([1,10])].copy()
    h["month"] = pd.PeriodIndex(h.month, freq="M")
    if h.duplicated(["permno","month"]).any():
        raise ValueError("Duplicate stock-month holdings")
    months = pd.PeriodIndex(sorted(h.month.unique()),freq="M")
    if months.empty or not months.equals(pd.period_range(months[0],months[-1],freq="M")):
        raise ValueError("Holdings need consecutive months")
    w = factor_weights.reindex(months)
    if not np.isfinite(w).all() or w.lt(0).any():
        raise ValueError("Applied factor weights must be complete, finite and nonnegative")
    fee=transaction_cost_bps/10000
    previous_positions=pd.Series(dtype=float)
    nav=1.0
    state="ok"
    account=[];trades=[]
    for month,group in h.groupby("month",sort=True):
        group=group.set_index("permno")
        target=(group.leg_weight*np.where(group.momentum_decile.eq(10),1.,-1.)*w.loc[month])
        active=target.ne(0)
        result={"month":month,"factor_weight":float(w.loc[month]),"pretrade_nav":nav,
                "state":state,"gross_factor_return":np.nan,"net_return":np.nan,
                "turnover":np.nan,"transaction_cost":np.nan,"financing_cost":np.nan,
                "postcost_nav":np.nan,"end_nav":np.nan}
        if state!="ok":
            result["state"]="account_not_evaluable_after_gap" if state!="insolvent" else state
            account.append(result);continue
        ids=target.index.union(previous_positions.index)
        q=target.reindex(ids,fill_value=0.)
        pre=previous_positions.reindex(ids,fill_value=0.)/nav
        if fee*pre.abs().sum()>=1:
            state="insolvent";result["state"]=state;nav=np.nan;account.append(result);continue
        x=1. if fee==0 else brentq(lambda z:z+fee*(z*q-pre).abs().sum()-1,0.,1.)
        signed_trade=x*q-pre
        turnover=float(signed_trade.abs().sum())
        result.update(turnover=turnover,transaction_cost=fee*turnover,postcost_nav=nav*x)
        tr=pd.DataFrame({"month":month,"permno":ids,"pretrade_weight":pre.to_numpy(),
             "target_weight_after_cost":q.to_numpy(),"executed_weight_before_cost":(x*q).to_numpy(),
             "trade_weight":signed_trade.to_numpy(),"absolute_trade":signed_trade.abs().to_numpy()})
        trades.append(tr.loc[(tr.pretrade_weight!=0)|(tr.target_weight_after_cost!=0)])
        total=group[return_column]
        price=group.mthretx.copy()
        imputed=group.get("scenario_imputed",pd.Series(False,index=group.index)).astype(bool)
        # Scenario returns replace unobserved price drift too, explicitly.
        price=price.where(~imputed,total)
        settled=group.get("delistingdt",pd.Series(pd.NaT,index=group.index)).notna()
        valid_total=np.isfinite(total)&total.ge(-1)
        valid_price=(np.isfinite(price)&price.ge(-1))|settled
        if not (valid_total[active]&valid_price[active]).all():
            state="unresolved_price_or_payoff";result["state"]=state
            nav=np.nan;account.append(result);continue
        gross=float((target[active]*total[active]).sum())
        financing=max(abs(w.loc[month])-1,0)*financing_cost_bps/10000/12
        net=x*(1+gross-financing)-1
        end_nav=nav*(1+net)
        result.update(gross_factor_return=gross,financing_cost=x*financing,
                      net_return=net,end_nav=end_nav)
        if end_nav<=0 or not np.isfinite(end_nav):
            state="insolvent";result["state"]=state;nav=np.nan;account.append(result);continue
        post_positions=(nav*x*target*(1+price)).where(active,0.)
        post_positions=post_positions.where(~settled,0.)
        previous_positions=post_positions[post_positions.ne(0)]
        nav=end_nav
        account.append(result)
    monthly=pd.DataFrame(account).set_index("month")
    stock_trades=pd.concat(trades,ignore_index=True) if trades else pd.DataFrame()
    return monthly,stock_trades
