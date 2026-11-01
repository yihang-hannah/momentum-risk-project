"""Reported return statistics and factor/timing tests; no notebook state."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from .metrics import performance_metrics


def describe(returns):
    return {**performance_metrics(returns).to_dict(),"Worst month":returns.min(),
            "Skewness":returns.skew(),"Excess kurtosis":returns.kurt()}


def factor_tests(returns,ff3, *, hac_lags=6):
    if returns.empty or returns.isna().any().any():raise ValueError("Strategy returns must be complete")
    columns=["Mkt-RF","SMB","HML","RF"]
    block=pd.concat([returns,ff3[columns]],axis=1,join="inner").dropna()
    if block.empty:raise ValueError("No complete common factor observations")
    X3=sm.add_constant(block[["Mkt-RF","SMB","HML"]])
    three={}
    for name in returns:
        m=sm.OLS(block[name],X3).fit()
        three[name]={"Alpha (monthly)":m.params["const"],"Alpha t-stat":m.tvalues["const"],
            "Market Beta":m.params["Mkt-RF"],"SMB Beta":m.params["SMB"],"HML Beta":m.params["HML"],"R-squared":m.rsquared}
    block["WML"]=block.unmanaged
    X4=sm.add_constant(block[["Mkt-RF","SMB","HML","WML"]])
    four={}
    for name in ["managed","managed_cap_2x"]:
        m=sm.OLS(block[name],X4).fit(cov_type="HAC",cov_kwds={"maxlags":hac_lags})
        four[name]={"Alpha (monthly)":m.params["const"],"Alpha t-stat (HAC)":m.tvalues["const"],
            "WML Beta":m.params["WML"],"Market Beta":m.params["Mkt-RF"],"SMB Beta":m.params["SMB"],
            "HML Beta":m.params["HML"],"R-squared":m.rsquared}
    timing=sm.OLS(block.managed-block.fixed_leverage,pd.DataFrame({"const":1.},index=block.index)).fit(cov_type="HAC",cov_kwds={"maxlags":hac_lags})
    attribution=pd.DataFrame([{"monthly_timing_return":timing.params["const"],"HAC_t":timing.tvalues["const"],"HAC_p":timing.pvalues["const"],"observations":len(block)}])
    coverage=pd.DataFrame([{"strategy_months":len(returns),"factor_months":len(block),
        "excluded_months":len(returns.index.difference(block.index)),"start":str(block.index[0]),"end":str(block.index[-1]),"hac_lags":hac_lags}])
    return {"ff3_regressions":pd.DataFrame(three).T,"ff4_HAC_regressions":pd.DataFrame(four).T,
            "timing_HAC":attribution,"factor_coverage":coverage}


def reconstruction_errors(rebuilt,kf,windows):
    rows=[]
    for name,(a,b) in windows.items():
        idx=pd.period_range(a,b,freq="M");pair=pd.concat([rebuilt.reindex(idx).rename("rebuilt"),kf.reindex(idx).rename("KF")],axis=1)
        known=pair.dropna();e=known.rebuilt-known.KF
        rows.append({"window":name,"calendar_months":len(idx),"known_paired_months":len(known),
            "correlation":known.corr().iloc[0,1],"MAE_bps":e.abs().mean()*10000,"RMSE_bps":np.sqrt(e.pow(2).mean())*10000})
    return pd.DataFrame(rows)
