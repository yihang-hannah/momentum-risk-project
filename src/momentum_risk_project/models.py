"""Paper equations and four-strategy gross comparison, independent of notebooks."""
import numpy as np
import pandas as pd
from .volatility import historical_volatility
from .strategies import volatility_managed_momentum


def paper_strategies(daily,monthly, *, start,end,annual_target=.12,window=126,trading_days_per_month=21,leverage_cap=2.,fixed_weight=None):
    sigma_d=historical_volatility(daily,window=window,trading_days_per_month=trading_days_per_month)
    sigma_m=sigma_d.groupby(sigma_d.index.to_period("M")).agg(lambda s:s.iloc[-1])
    strategy=volatility_managed_momentum(monthly,sigma_m,target_volatility=annual_target)
    idx=pd.period_range(start,end,freq="M")
    block=strategy.reindex(idx)
    if not np.isfinite(block[["mom","weight","managed"]]).all().all():
        raise ValueError("Requested comparison requires complete contiguous return/risk coverage")
    average=float(block.weight.mean()) if fixed_weight is None else float(fixed_weight)
    if not np.isfinite(average) or average<0:raise ValueError("Invalid fixed leverage")
    returns=pd.DataFrame({"unmanaged":block.mom,"fixed_leverage":block.mom*average,
        "managed":block.managed,"managed_cap_2x":block.mom*block.weight.clip(upper=leverage_cap)})
    returns.index.name="month";sigma_m.index.name="month"
    return returns,block.weight.rename("weight"),sigma_m,average
