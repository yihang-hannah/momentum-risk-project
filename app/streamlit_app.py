"""Presentation-only research desk. Run: streamlit run app/streamlit_app.py."""
import json
import streamlit as st
from momentum_risk_project.dashboard import (
    load_snapshot, DashboardDataError, WINDOW_LABELS, METHOD_LABELS,
)
from momentum_risk_project.dashboard_charts import lines,monthly_account,fee_sensitivity

st.set_page_config(page_title="Momentum | Research Desk",page_icon="↗",layout="wide",initial_sidebar_state="expanded")
st.markdown("""<style>
.block-container {padding-top:2rem; max-width:1560px; padding-bottom:3rem;}
[data-testid="stSidebar"] {border-right:1px solid #e5ebf0;}
[data-testid="stSidebar"] .block-container {padding-top:2rem;}
h1 {font-size:2.35rem!important; font-weight:650!important; letter-spacing:-.07rem;}
h2 {font-size:1.25rem!important; letter-spacing:-.025rem;}
h3 {font-size:1.1rem!important;}
[data-testid="stMetric"] {background:#fff; border-color:#e5ebf0; border-radius:12px; padding:18px 20px;}
[data-testid="stMetricValue"] {font-size:1.9rem!important; letter-spacing:-.04rem;}
[data-testid="stMetricLabel"] {font-size:.8rem; color:#64768a;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:#e5ebf0; border-radius:12px;}
.eyebrow {font-size:.69rem;letter-spacing:.16rem;color:#738399;font-weight:700;margin-bottom:6px;}
.brand {font-size:1.22rem;font-weight:700;color:#172c44;letter-spacing:.08rem;}
.brand small {font-size:.66rem;display:block;letter-spacing:.18rem;color:#718199;margin-top:3px;}
.status {display:inline-block;font-size:.72rem;font-weight:600;color:#0d786b;background:#e7f5f0;padding:6px 11px;border-radius:20px;}
.note {background:#fff8eb;border:1px solid #f2dfb8;border-radius:10px;padding:12px 16px;color:#715b31;font-size:.83rem;line-height:1.5;margin:10px 0 20px;}
</style>""",unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand">MOMENTUM<small>RESEARCH DESK / IEOR 4576</small></div>',unsafe_allow_html=True)
    st.divider()

try:
    snapshot=load_snapshot()
except DashboardDataError as error:
    st.title("Your research desk is ready.")
    st.info(str(error))
    st.markdown("Generate the verified local dataset, then refresh this page.")
    st.code("python run_all.py",language="bash")
    st.caption("The stock study requires your authorized local CRSP caches. No data are downloaded by this interface.")
    st.stop()

c=snapshot.config
with st.sidebar:
    st.markdown("**Study settings**")
    window=st.selectbox("Evaluation window",list(c["windows"]),format_func=lambda x:WINDOW_LABELS[x],key="window")
    start,end=c["windows"][window]
    st.caption(f"{start} — {end} · monthly returns")
    source_label=st.selectbox("Return source",["Rebuilt WML · own risk","KF WML · gross benchmark"],key="source")
    source="KF" if source_label.startswith("KF") else "rebuilt"
    if "basis" not in st.session_state:
        st.session_state["basis"]="Net of trading costs"
    if source=="KF":
        st.session_state["basis"]="Gross before costs"
    basis_label=st.radio("Return basis",["Net of trading costs","Gross before costs"],index=None,
        disabled=source=="KF",key="basis",help="KF portfolio returns do not provide a stock-level trading-cost ledger.")
    basis="gross" if source=="KF" or basis_label=="Gross before costs" else "net"
    fee=st.select_slider("Cost per dollar traded",options=list(snapshot.costs),value=float(c["costs"]["baseline_bps"]),
        format_func=lambda x:f"{x:g} bps",disabled=source=="KF" or basis=="gross",key="fee")
    st.caption("One-way trading fee. Financing is zero." if source=="rebuilt" and basis=="net" else "No trading-cost deduction in this gross view.")
    capital=st.number_input("Starting capital ($)",min_value=100.,max_value=1000000000.,value=10000.,step=1000.,key="capital")
    with st.expander("Accounting convention"):
        method=st.selectbox("Stock cost model",list(METHOD_LABELS),format_func=lambda x:METHOD_LABELS[x],
            disabled=source=="KF",key="method")
        st.caption("Funded account: actual buys/sells and fees funded from NAV. Paper-style views use normalized-leg half-turnover.")
    st.divider()
    st.markdown("**Risk model**")
    st.caption(f"Realized volatility · {c['risk']['window']} sessions\n\n{c['risk']['annual_target']:.0%} annual target · {'own-stock daily risk' if source=='rebuilt' else 'KF daily risk'}")
    st.markdown('<span class="status">● Verified saved scenarios</span>',unsafe_allow_html=True)

try:
    view=snapshot.select(window,source=source,basis=basis,cost=float(fee),method=method)
    wealth,drawdown=view.curves(float(capital))
except DashboardDataError as error:
    st.error(str(error));st.stop()

st.markdown('<div class="eyebrow">MOMENTUM RISK MANAGEMENT</div>',unsafe_allow_html=True)
title,tag=st.columns([5,1.5],vertical_alignment="center")
with title:
    st.title("See the return. Understand the risk.")
    st.caption(f"{WINDOW_LABELS[window]} · {start} to {end} · {len(view.returns):,} months · Barroso & Santa-Clara (2015)")
with tag:
    st.markdown('<span class="status">↗ Research backtest / MVP</span>',unsafe_allow_html=True)

if source=="rebuilt":
    st.markdown('<div class="note"><b>Own-stock risk, explicit zero-gap scenario.</b> Rebuilt daily WML determines rebuilt positions; KF uses its own risk separately. Missing stock components and unknown terminal increments are assumed zero, while known delisting returns are included once. Strict unresolved valuations remain a diagnostic.</div>',unsafe_allow_html=True)
else:
    st.caption("KF benchmark · gross returns only. No constituent-stock costs are inferred from the published factor series.")

managed=view.metrics.loc["Risk managed"];plain=view.metrics.loc["Unmanaged"]
cols=st.columns(4)
cols[0].metric("Managed Sharpe",f"{managed['Sharpe (rf=0)']:.3f}",f"{managed['Sharpe (rf=0)']-plain['Sharpe (rf=0)']:+.3f} vs unmanaged",border=True,help="Annual arithmetic mean divided by annual sample volatility; risk-free rate zero.")
cols[1].metric("Annual mean return",f"{managed['Annualized Mean Return']:.2%}",f"{100*(managed['Annualized Mean Return']-plain['Annualized Mean Return']):+.2f} pp",border=True,help="12 times monthly arithmetic mean; distinct from CAGR.")
cols[2].metric("Annual volatility",f"{managed['Annualized Volatility']:.2%}",f"{100*(managed['Annualized Volatility']-plain['Annualized Volatility']):+.2f} pp",delta_color="inverse",border=True)
cols[3].metric("Maximum drawdown",f"{managed['Maximum Drawdown']:.2%}",f"{100*(managed['Maximum Drawdown']-plain['Maximum Drawdown']):+.2f} pp",border=True,help="Includes starting wealth. A positive difference means a less severe drawdown.")
st.caption(f"{'Net' if basis=='net' else 'Gross'} performance · "+(f"{fee:g}bp one-way · {METHOD_LABELS[method]}" if source=='rebuilt' and basis=='net' else 'no trading-cost deduction')+" · deltas compare risk managed with unmanaged")

overview,costs,data=st.tabs(["Performance","Trading & costs","Data & methodology"])
with overview:
    with st.container(border=True):
        row,options=st.columns([4,2])
        row.subheader("Growth of capital")
        row.caption("One portfolio, two approaches to risk.")
        log=options.toggle("Log scale",value=True,key="log")
        benchmark=options.toggle("Show KF gross reference",value=False,disabled=source=="KF",key="benchmark")
        chart=wealth.copy()
        if benchmark and source=="rebuilt":
            first=wealth.index[0]
            import pandas as pd
            for name in view.kf_gross:
                series=(1+view.kf_gross[name]).cumprod()*capital
                series.index=view.kf_gross.index.to_timestamp("M")
                chart[name+" · gross"]=pd.concat([pd.Series([capital],index=[first]),series])
        st.plotly_chart(lines(chart,ytitle="Portfolio value ($)",height=390,log=log),width="stretch",key="wealth")
        st.caption("Wealth is rebased to your starting capital at the selected window. Stock-account history is retained; changing the view does not open a fresh trade. KF dashed lines are gross references.")
    left,right=st.columns([1.25,1])
    with left,st.container(border=True):
        st.subheader("Drawdown")
        st.plotly_chart(lines(drawdown,ytitle="Decline from peak",height=300,percent=True),width="stretch",key="drawdown")
    with right,st.container(border=True):
        st.subheader("Strategy comparison")
        columns=["Annualized Mean Return","Annualized Volatility","Sharpe (rf=0)","CAGR","Maximum Drawdown","Worst month"]
        table=view.metrics[columns].T.rename(index={"Annualized Mean Return":"Annual mean","Annualized Volatility":"Annual volatility","Sharpe (rf=0)":"Sharpe (rf = 0)","Maximum Drawdown":"Max drawdown"})
        formatted=table.copy().astype(object)
        for row in table.index:
            formatted.loc[row]=[f"{x:.3f}" if row.startswith("Sharpe") else f"{x:.2%}" for x in table.loc[row]]
        st.dataframe(formatted,width="stretch",height=265)
        st.caption(f"Same {len(view.returns):,} monthly observations for both strategies.")
    with st.container(border=True):
        st.subheader("Explore monthly returns")
        monthly=view.returns.copy();monthly.index=monthly.index.to_timestamp("M")
        st.plotly_chart(lines(monthly,ytitle="Monthly simple return",height=270,percent=True),width="stretch",key="monthly_returns")

with costs:
    if source=="KF":
        st.info("Stock-level turnover and trading costs are unavailable for the published KF benchmark. Select Rebuilt WML to inspect the stock-cost study.")
    else:
        left,right=st.columns(2)
        with left,st.container(border=True):
            st.subheader("How much do costs matter?")
            st.caption("Exact saved fee scenarios; the vertical marker is your selected scenario.")
            st.plotly_chart(fee_sensitivity(snapshot,view),width="stretch",key="fee_sensitivity")
        with right,st.container(border=True):
            st.subheader("Turnover through time")
            column="turnover" if method=="funded_account" else "half_turnover"
            st.plotly_chart(lines(monthly_account(view,column),ytitle="Actual traded notional / NAV" if method=="funded_account" else "Leg-normalized half-turnover",height=320,percent=True),width="stretch",key="turnover")
        if method=="funded_account":
            left,right=st.columns(2)
            with left,st.container(border=True):
                st.subheader("Monthly trading-cost drag")
                st.plotly_chart(lines(monthly_account(view,"transaction_cost"),ytitle="Fee / pretrade NAV",height=285,percent=True,percent_format=".2%"),width="stretch",key="cost_drag")
            with right,st.container(border=True):
                st.subheader("Applied factor weight")
                st.plotly_chart(lines(monthly_account(view,"factor_weight"),ytitle="Factor multiplier",height=285),width="stretch",key="exposure")
                st.caption("Factor weight 1 = 1 dollar long winners and 1 dollar short losers; gross stock exposure is 2.")
            st.caption("Turnover includes stock entries, exits and return drift. Fees are paid from NAV and targets use after-fee NAV. Dividend cash and delisting settlement use the existing monthly account conventions.")
        else:
            st.info("Paper-style diagnostic: net return = gross return − 2 × one-way fee × half-turnover. This differs from the funded account's actual-trade accounting. The printed inverse-L version is a separate diagnostic, not a verified correction of the paper.")

with data:
    st.subheader("What this view represents")
    a,b=st.columns(2)
    with a,st.container(border=True):
        st.markdown("**Data & timing**")
        st.markdown("Value-weighted winner-minus-loser deciles. Monthly portfolio returns; each strategy’s own daily squared returns forecast its risk. The previous month's final session sets the next month's weight.")
        st.markdown(f"**Risk settings:** {c['risk']['window']} daily observations · {c['risk']['trading_days_per_month']} sessions per month · {c['risk']['annual_target']:.0%} annual target.")
        st.markdown("**Source:** Kenneth French public deciles; rebuilt portfolios use authorized CRSP/WRDS extracts. No downloads or fits run from this interface.")
    with b,st.container(border=True):
        record=view.coverage.iloc[0]
        st.markdown("**Independent-stock coverage**")
        st.metric("Own-stock risk forecasts",f"{int(record.own_stock_risk_forecasts):,} / {len(view.returns):,}")
        st.caption(f"Strict monthly returns available: {int(record.strict_DM_monthly_returns):,}. Complete continuous strict-account months in this view: {int(record.strict_continuous_account_known_months):,}.")
        st.markdown("Unavailable forecasts are **unknown, not cash**. The primary reconstructed strategy estimates risk from its own daily returns under the stated zero scenario. Strict unresolved valuations are retained separately; no KF weights or cash fill are substituted.")
    st.caption("The common evaluation starts in July 1927: reconstructed daily history starts in January and needs a complete 126-session month-end forecast. The 2012–2025 extension is post-sample, not entirely post-publication.")
    with st.expander("Return and cost assumptions"):
        st.markdown("Ordinary monthly stock-return gaps use the accepted zero assumption. The primary scenario includes recorded delisting components once, retains published numeric components and assumes unobserved increments zero; strict diagnostics preserve unknown terminal values. Zero terminal return is not a claim of zero liquidation value. Multi-session numeric components are booked on their observed endpoint, with unavailable intervening values zero. No short-borrow fee, rebate, variable impact or delayed cash-timing model is inferred. Financing is zero.")
        st.markdown("The paper turnover test uses its separate March 1951–December 2010 window. EWMA and GARCH are not integrated yet; the current interface exposes only the validated historical-risk model.")
    with st.expander("Reproduce this study"):
        st.code("python run_all.py\npython -m pytest -p no:cacheprovider tests/ -q",language="bash")
        st.caption("See README, Notebook 03's opening source specification and Notebook 05 for definitions, sources and validation.")
        st.caption("Study fingerprint: "+snapshot.fingerprint[:16])

st.divider()
left,right=st.columns([3,2])
with left:
    st.caption("Export this view · monthly returns, rebased wealth and drawdown")
    st.download_button("Download monthly CSV",data=view.download(float(capital)),file_name=f"momentum_{window}_{source}_{basis}_{view.cost:g}bps.csv",mime="text/csv",key="download_csv")
with right:
    st.caption("Save the exact settings and study fingerprint")
    st.download_button("Download scenario JSON",data=json.dumps(view.metadata(snapshot,float(capital)),indent=2),file_name="momentum_scenario.json",mime="application/json",key="download_settings")
st.caption("MOMENTUM / IEOR 4576 · Research replay of verified historical scenarios. No broker connection or order execution.")
