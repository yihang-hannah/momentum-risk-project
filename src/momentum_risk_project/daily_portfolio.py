"""Daily returns of monthly-formed stock deciles, with explicit missing policies."""
import numpy as np
import pandas as pd


def daily_wml_from_holdings(holdings, daily_records, trading_dates, *, mode="strict"):
    """Reconstruct P1/P10 daily returns from fixed month-start stock quantities.

    mode='strict' leaves unobserved daily returns and incomplete terminal payoffs
    unknown. mode='carry_prices' carries total-return values only across unquoted
    days within 200 CRSP trading dates; it is an explicit valuation sensitivity,
    not an observed zero return or a claim that shares could be sold there.
    In that mode, excluded/partial terminal values remain as-published; the source
    quality audit still labels them incomplete. Valid quotes with missing returns
    are not turned into zeros.

    mode='zero_regular_dm' fills missing ordinary-stock daily returns at the
    component level, retaining observed Y delisting components. Unknown final
    payoffs stay unknown. This zero rule is a user-selected sensitivity; DM
    documents inclusion of delisting returns, not this ordinary-gap imputation.

    mode='zero_regular_dm_checked' additionally protects missing corporate
    actions and multi-session returns; legacy mode remains reproducible.

    mode='zero_missing_reconstructed' retains published numeric components,
    recovers recorded terminal components once, and sets missing components to
    zero. Partial/unknown terminal increments are explicitly assumed zero, not
    declared observed. Multi-session numeric returns are booked on their source
    end date; intervening unavailable valuations are zero. This is a complete
    last-observation/zero-increment research scenario, not a provider rule.

    Known final payoffs follow monthly research attribution to the delist month;
    this is not a point-in-time disclosure or cash-settlement simulator. Included
    daily delisting records are never added twice. Long and short leg daily
    returns are calculated separately, then subtracted (not compounded WML).
    """
    reconstructed_zero = mode == "zero_missing_reconstructed"
    checked_flags = mode == "zero_regular_dm_checked"
    if reconstructed_zero:
        mode = "zero_regular_dm"
    if checked_flags:
        mode = "zero_regular_dm"
    if mode not in {"strict", "carry_prices", "zero_regular_dm"}:
        raise ValueError("Unknown daily missing-data mode")
    dates = pd.DatetimeIndex(trading_dates).sort_values().unique()
    if dates.empty or dates.hasnans:
        raise ValueError("Trading calendar must be nonempty and valid")
    h = holdings.loc[holdings.momentum_decile.isin([1, 10])].copy()
    d = daily_records.copy()
    d["date"] = pd.to_datetime(d.dlycaldt)
    d["month"] = d.date.dt.to_period("M")
    if d.duplicated(["permno", "date", "dlydelflg"]).any():
        raise ValueError("Duplicate daily stock/component records")
    pieces = []
    for month, positions in h.groupby("month", sort=True):
        month_dates = dates[dates.to_period("M") == month]
        if len(month_dates) == 0:
            raise ValueError("Holding month absent from calendar")
        frame = pd.DataFrame(index=month_dates)
        frame.index.name = "date"
        md = d.loc[d.month.eq(month)]
        for decile in (1, 10):
            pos = positions.loc[positions.momentum_decile.eq(decile)].set_index("permno")
            if pos.empty:
                raise ValueError("Missing winner or loser leg")
            source = md.loc[md.permno.isin(pos.index)]
            source = source.copy()
            source["assumed_missing_component"] = False
            source["special_missing_assumed"] = False
            # Monthly research attribution: move a separate Y component onto
            # its actual delist date before collapsing components. Otherwise
            # clearing positions after delist could accidentally erase Y at t+1.
            y = source.dlydelflg.eq("Y")
            if "delistingdt" in pos and y.any():
                actual = source.loc[y, "permno"].map(pos.delistingdt)
                valid_dates = actual.notna() & pd.to_datetime(actual).dt.to_period("M").eq(month)
                mapped = month_dates[np.minimum(month_dates.searchsorted(pd.to_datetime(actual.loc[valid_dates])),len(month_dates)-1)]
                source.loc[actual.loc[valid_dates].index, "date"] = mapped
            if mode == "carry_prices":
                # Explicit as-published valuation sensitivity: no invented terminal
                # loss for a missing Y component. Quality remains unresolved.
                source = source.loc[~(source.dlydelflg.eq("Y") & source.dlyret.isna())]
            if mode == "zero_regular_dm" and "delret" in pos:
                recorded = pos.delret.where(pos.delret.ge(-1) & np.isfinite(pos.delret) & (reconstructed_zero | ~pos.mthdelflg.eq("V")))
                replacement = source.permno.map(recorded)
                recover_y = source.dlydelflg.eq("Y") & source.dlyret.isna() & replacement.notna()
                source.loc[recover_y, "dlyret"] = replacement.loc[recover_y]
            policy_blocked = pd.Series(False, index=source.index)
            if checked_flags:
                ordinary = ~source.dlydelflg.eq("Y")
                if "dlyretmissflg" in source:
                    policy_blocked |= ordinary & ~source.dlyretmissflg.isin(["NA", "MP", "NT", "GP"])
                if "dlyretdurflg" in source:
                    policy_blocked |= ordinary & source.dlyretdurflg.isin([f"P{i}" for i in range(1,10)])
                source.loc[policy_blocked, "dlyret"] = np.nan
            zero_components = pd.Series(False, index=source.index)
            if mode == "zero_regular_dm":
                zero_components = source.dlyret.isna() & (reconstructed_zero | ~source.dlydelflg.eq("Y")) & ~policy_blocked
                source["assumed_missing_component"] = zero_components
                if reconstructed_zero and "dlyretmissflg" in source:
                    source["special_missing_assumed"] = zero_components & ~source.dlyretmissflg.isin(["NA","MP","NT","GP"])
                source.loc[zero_components, "dlyret"] = 0.0
            # N and Y components on a date compound; strict missing components stay unknown.
            good = np.isfinite(source.dlyret) & source.dlyret.ge(-1)
            src = source.assign(gross=(1+source.dlyret).where(good), bad=~good, zero_imputed=zero_components)
            grouped = src.groupby(["date", "permno"]).agg(
                gross=("gross", "prod"), bad=("bad", "any"),
                price=("dlyprc", "max"), components=("dlyret", "size"),
                zero_imputed=("zero_imputed", "sum"))
            ret = (grouped.gross - 1).where(~grouped.bad).unstack("permno")
            price = grouped.price.unstack("permno")
            ret = ret.reindex(index=month_dates, columns=pos.index)
            price = price.reindex(index=month_dates, columns=pos.index)
            carried = pd.DataFrame(False, index=month_dates, columns=pos.index)
            unresolved_terminal = pd.Series(False, index=pos.index)
            if mode == "carry_prices":
                initial_dates = pd.to_datetime(pos.get("formation_price_date", pos.formation_date)).fillna(pd.to_datetime(pos.formation_date))
                initial_numbers = dates.searchsorted(initial_dates, side="right")-1
                day_numbers = dates.get_indexer(month_dates)
                priced = price.to_numpy(dtype=float) > 0
                observed_numbers = np.where(priced, day_numbers[:, None], -1)
                last_numbers = np.maximum.accumulate(np.vstack([initial_numbers, observed_numbers]), axis=0)[1:]
                ages = day_numbers[:, None]-last_numbers
                mask = ret.isna().to_numpy() & ~priced & (ages >= 0) & (ages <= 200)
                values = ret.to_numpy(dtype=float, copy=True)
                values[mask] = 0.0
                ret = pd.DataFrame(values, index=month_dates, columns=pos.index)
                carried = pd.DataFrame(mask, index=month_dates, columns=pos.index)
            zero_imputed = pd.DataFrame(0, index=month_dates, columns=pos.index)
            if mode == "zero_regular_dm":
                # An absent ordinary record is zero under this scenario. A
                # present bad component (especially unknown Y) is NOT zero.
                blocked = grouped.bad.unstack("permno").reindex(index=month_dates, columns=pos.index).fillna(False).astype(bool)
                absent_or_missing = ret.isna() & ~blocked
                zero_imputed = grouped.zero_imputed.unstack("permno").reindex(index=month_dates, columns=pos.index).fillna(0).astype(int)
                zero_imputed += absent_or_missing.astype(int)
                ret = ret.mask(absent_or_missing, 0.0)
                # No event date is not evidence of a complete terminal payoff.
                unknown = ~pos.payoff_complete.fillna(False).astype(bool)
                if reconstructed_zero:
                    unknown[:] = False
                if "delistingdt" in pos:
                    unknown &= pos.delistingdt.isna()
                for stock in pos.index[unknown & pos.mthdelflg.isin(["G", "M", "V"])]:
                    ret.loc[:, stock] = np.nan
                    zero_imputed.loc[:, stock] = 0
                    unresolved_terminal.loc[stock] = True
            terminal = pos.loc[pos.get("delistingdt", pd.Series(pd.NaT,index=pos.index)).notna()]
            for stock, row in terminal.iterrows():
                deldate = row.get("delistingdt", pd.NaT)
                if pd.notna(deldate) and pd.Timestamp(deldate).to_period("M") == month:
                    event_index = month_dates.searchsorted(pd.Timestamp(deldate))
                    event_index = min(event_index, len(month_dates)-1)
                    event_date = month_dates[event_index]
                    components = source.loc[source.permno.eq(stock) & source.dlydelflg.eq("Y")]
                    included = (components.dlyret.notna() & ~components.assumed_missing_component).any()
                    flag = row.mthdelflg
                    payoff = row.get("delret", np.nan)
                    known = pd.notna(payoff) and np.isfinite(payoff) and payoff >= -1 and (reconstructed_zero or flag != "V")
                    dm_unknown = (mode == "zero_regular_dm" and not reconstructed_zero and
                        not (bool(row.get("payoff_complete", False)) or known or (included and flag != "V")))
                    if (mode == "strict" and not bool(row.get("payoff_complete", False))) or dm_unknown:
                        ret.loc[event_date, stock] = np.nan
                        unresolved_terminal.loc[stock] = True
                    elif known and not included:
                        current = ret.loc[event_date, stock]
                        if pd.notna(current):
                            ret.loc[event_date, stock] = (1+current)*(1+payoff)-1
                    # Proceeds/closed liability stay in cash after the terminal event.
                    after = month_dates > event_date
                    ret.loc[after, stock] = 0.0
                    zero_imputed.loc[after, stock] = 0
            if reconstructed_zero:
                # Missing is imputed at stock/component level, never by filling
                # an already aggregated WML series with zero.
                if ret.isna().any().any():
                    raise ValueError("Unresolved invalid numeric return in zero-missing reconstruction")
                frame[f"P{decile}_assumed_terminal_positions"] = int((~pos.payoff_complete.fillna(False).astype(bool)).sum())
                frame[f"P{decile}_special_missing_components"] = source.groupby("date").special_missing_assumed.sum().reindex(month_dates,fill_value=0)
                if "dlyretdurflg" in source:
                    multi=source.dlyretdurflg.isin([f"P{i}" for i in range(1,10)]) & source.dlyret.notna()
                    frame[f"P{decile}_multisession_endpoint_components"] = source.loc[multi].groupby("date").size().reindex(month_dates,fill_value=0)
            wealth = (1 + ret).cumprod(skipna=False)
            values = wealth.mul(pos.leg_weight, axis=1)
            leg_wealth = values.sum(axis=1, min_count=len(pos))
            previous = leg_wealth.shift(1, fill_value=1.0)
            frame[f"P{decile}"] = leg_wealth/previous-1
            frame[f"P{decile}_unknown_positions"] = ret.isna().sum(axis=1)
            frame[f"P{decile}_carried_positions"] = carried.sum(axis=1)
            if mode == "zero_regular_dm":
                frame[f"P{decile}_zero_imputed_components"] = zero_imputed.sum(axis=1)
            frame[f"P{decile}_unresolved_terminal_positions"] = int(unresolved_terminal.sum())
        frame["WML"] = frame.P10 - frame.P1
        pieces.append(frame)
    return pd.concat(pieces).sort_index()
