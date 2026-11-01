import numpy as np
import pandas as pd
import pytest
from momentum_risk_project.paper_turnover import appendix_b_turnover, cutoff_roundtrip_bps


def example():
    h=pd.DataFrame({"month":pd.PeriodIndex(["2020-01"]*3+["2020-02"]*3,freq="M"),
        "permno":[1,2,3,1,4,3],"momentum_decile":[10,10,1,10,10,1],
        "leg_weight":[.5,.5,1,.5,.5,1],"return_reference":[1.,0.,0.,0.,0.,0.]})
    w=pd.Series([1.,2.],index=pd.period_range("2020-01",periods=2,freq="M"))
    return h,w


def test_leg_normalization_exit_entry_and_scaling_conventions():
    h,w=example();tr,m=appendix_b_turnover(h,w)
    # Prior long weights 2/3, 1/3; new 1/2, 1/2. Short unchanged.
    assert m.iloc[1].unmanaged_half_trade==pytest.approx(.5)
    # Actual factor scales double: long .5*(1/3+1/3+1)=5/6, short .5.
    assert m.iloc[1].scaled_positions_half_trade==pytest.approx(4/3)
    # Literal inverse L shrinks current legs: long .5*(5/12+1/3+1/4)=.5, short .25.
    assert m.iloc[1].literal_eq10_half_trade==pytest.approx(.75)
    assert m.iloc[0].unmanaged_half_trade==pytest.approx(1.)
    assert set(tr.loc[tr.month.eq(w.index[1]),"permno"])=={1,2,3,4}


def test_same_month_returns_do_not_change_current_turnover():
    h,w=example();_,a=appendix_b_turnover(h,w)
    h.loc[h.month.eq(w.index[-1]),"return_reference"]=.9
    _,b=appendix_b_turnover(h,w)
    pd.testing.assert_frame_equal(a,b)


def test_unknown_prior_returns_are_not_zero_or_partial_sums():
    h,w=example();h.loc[0,"return_reference"]=np.nan
    _,m=appendix_b_turnover(h,w)
    assert m.iloc[1,:3].isna().all()
    assert m.iloc[0,:3].notna().all()


def test_leg_switch_is_exit_and_entry():
    h=pd.DataFrame({"month":pd.PeriodIndex(["2020-01"]*2+["2020-02"]*2,freq="M"),
      "permno":[1,2,2,1],"momentum_decile":[10,1,10,1],"leg_weight":[1.]*4,"return_reference":[0.]*4})
    _,m=appendix_b_turnover(h,pd.Series(1.,index=pd.period_range("2020-01",periods=2,freq="M")))
    assert m.iloc[1].unmanaged_half_trade==2.


def test_inverse_convention_requires_positive_scale():
    h,w=example();w.iloc[0]=0
    with pytest.raises(ValueError,match="positive"):appendix_b_turnover(h,w)


def test_significance_cutoff_uses_roundtrip_rate():
    r=pd.Series(np.tile([.01,.02,.03,.02],30));x=pd.Series(.75,index=r.index)
    c=cutoff_roundtrip_bps(r,x)
    assert 0<c<r.mean()/.75*10000
    net=r-c/10000*x
    from scipy.stats import t
    assert net.mean()/net.std(ddof=1)*np.sqrt(len(net))==pytest.approx(t.ppf(.975,len(net)-1))
    r.iloc[0]=np.nan
    assert np.isnan(cutoff_roundtrip_bps(r,x))
