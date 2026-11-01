"""Formation-value checks; never change holding returns or raw source fields."""
import numpy as np
import pandas as pd


def screen_formation_values(monthly):
    """Reject stale/beginning/unknown prices as formation or t-13 values.

    BA bid-ask midpoint is a valid price type; it is not a missing-value fill.
    Completeness yellow/red flags alone do not justify deleting an observation.
    Returns are left unchanged. Use the result for formation/ranking only;
    retain original monthly observations for holding-return attachment.
    """
    x=monthly.copy()
    valid=np.isfinite(x.mthprc)&x.mthprc.gt(0)
    if 'mthprcflg' in x:valid &= x.mthprcflg.isin(['TR','BA'])
    if 'mthdtflg' in x:
        # The first database observation may be NS on the actual period-end
        # (December 1925). Date equality still establishes an end-date value.
        date_ok = pd.to_datetime(x.mthprcdt).eq(pd.to_datetime(x.mthcaldt)) if 'mthprcdt' in x else pd.Series(False,index=x.index)
        valid &= x.mthdtflg.eq('PE') | (x.mthdtflg.eq('NS') & date_ok)
    if 'mthprcdt' in x:
        valid &= pd.to_datetime(x.mthprcdt).eq(pd.to_datetime(x.mthcaldt))
    cap_valid=valid&np.isfinite(x.mthcap)&x.mthcap.gt(0)
    x['formation_value_usable']=cap_valid
    x.loc[~cap_valid,'mthcap']=np.nan
    x.loc[~valid,'mthprc']=np.nan
    return x
