import numpy as np
import pandas as pd
import pytest
from momentum_risk_project.stock_turnover import stock_level_turnover


def panel():
    return pd.DataFrame([
        [1, '2020-01', 10, 100, 0.1], [2, '2020-01', 1, 100, -0.1],
        [1, '2020-02', 10, 100, 0.0], [2, '2020-02', 1, 100, 0.0],
        [3, '2020-03', 10, 100, 0.0], [2, '2020-03', 1, 100, 0.0],
    ], columns=['permno', 'month', 'momentum_decile', 'formation_cap', 'mthret'])


def test_entry_and_nav_drift_and_membership_exit():
    trades, monthly = stock_level_turnover(panel())
    assert monthly.iloc[0].turnover == pytest.approx(2)
    # Gross January P&L is +20%; pretrade long/short weights are 1.1/1.2 and -.9/1.2.
    assert monthly.iloc[1].turnover == pytest.approx(abs(1-1.1/1.2)+abs(-1+.9/1.2))
    assert monthly.iloc[2].turnover == pytest.approx(2)
    assert monthly.iloc[2].entry_notional == pytest.approx(1)
    assert monthly.iloc[2].exit_notional == pytest.approx(1)
    assert trades.loc[(trades.month == pd.Period('2020-03')) & (trades.permno == 1), 'target_weight'].iloc[0] == 0


def test_cap_weights_and_current_returns_do_not_change_current_turnover():
    data = panel()
    data.loc[len(data)] = [4, '2020-01', 10, 300, 0.2]
    trades, first = stock_level_turnover(data)
    assert trades.loc[(trades.month == pd.Period('2020-01')) & (trades.permno == 4), 'target_weight'].iloc[0] == pytest.approx(.75)
    data.loc[data.month == '2020-02', 'mthret'] = .5
    _, second = stock_level_turnover(data)
    assert first.iloc[1].turnover == second.iloc[1].turnover
    assert first.iloc[2].turnover != second.iloc[2].turnover


def test_missing_previous_return_invalidates_next_month_even_if_stock_exits():
    data = panel()
    data.loc[(data.month == '2020-02') & (data.permno == 1), 'mthret'] = np.nan
    _, monthly = stock_level_turnover(data)
    assert np.isnan(monthly.iloc[1].gross_return)
    assert np.isfinite(monthly.iloc[1].turnover)
    assert np.isnan(monthly.iloc[2].turnover)
    assert not monthly.iloc[2].turnover_known


def test_factor_scaling_is_applied_to_stock_targets():
    weights = pd.Series([1, 1.2, .5], index=pd.period_range('2020-01', periods=3, freq='M'))
    _, monthly = stock_level_turnover(panel(), weights)
    np.testing.assert_allclose(monthly.target_gross_exposure, [2, 2.4, 1])
    np.testing.assert_allclose(monthly.target_net_exposure, 0, atol=1e-14)


def test_total_loss_and_bankruptcy():
    data = panel()
    data.loc[0, 'mthret'] = -1
    data.loc[1, 'mthret'] = 0
    _, monthly = stock_level_turnover(data)
    assert monthly.iloc[0].gross_return == -1
    assert np.isnan(monthly.iloc[1].turnover)


@pytest.mark.parametrize('kind', ['duplicate', 'gap', 'missing_leg', 'bad_cap'])
def test_bad_holdings_rejected(kind):
    data = panel()
    if kind == 'duplicate': data = pd.concat([data, data.iloc[:1]])
    if kind == 'gap': data = data[data.month != '2020-02']
    if kind == 'missing_leg': data = data[~((data.month == '2020-01') & (data.permno == 2))]
    if kind == 'bad_cap': data.loc[0, 'formation_cap'] = 0
    with pytest.raises(ValueError): stock_level_turnover(data)


def test_missing_factor_month_rejected():
    weights = pd.Series([1.0], index=pd.period_range('2020-01', periods=1, freq='M'))
    with pytest.raises(ValueError): stock_level_turnover(panel(), weights)
