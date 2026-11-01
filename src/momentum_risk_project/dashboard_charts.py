"""Interactive presentation charts; financial calculations stay in the package."""
import plotly.graph_objects as go
import pandas as pd
COLORS={"Unmanaged":"#8293ab","Risk managed":"#0e8b7c"}


def style(fig,height=360,ytitle=None):
    fig.update_layout(template="plotly_white",height=height,margin=dict(l=10,r=20,t=20,b=15),
        font=dict(family="Arial, sans-serif",size=12,color="#566579"),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h",yanchor="bottom",y=1.03,x=0),
        hovermode="x unified",yaxis_title=ytitle)
    fig.update_xaxes(showgrid=False,zeroline=False)
    fig.update_yaxes(gridcolor="#eaf0f4",zeroline=False)
    return fig


def lines(frame,*,ytitle=None,height=360,percent=False,log=False,percent_format=".0%"):

    fig=go.Figure()
    for name in frame:
        fig.add_trace(go.Scatter(x=frame.index,y=frame[name],name=name,mode="lines",
            line=dict(color=COLORS.get(name,"#d18d41"),width=2.6,dash="dash" if name.startswith("KF") else "solid"),
            hovertemplate=("%{y:.2%}" if percent else "%{y:,.2f}")+"<extra>"+name+"</extra>"))
    style(fig,height,ytitle)
    if percent:fig.update_yaxes(tickformat=percent_format)
    if log:fig.update_yaxes(type="log")
    return fig


def monthly_account(view,column):
    frame=view.account.pivot(index="month",columns="display_strategy",values=column).reindex(columns=["Unmanaged","Risk managed"])
    frame.index=pd.PeriodIndex(frame.index,freq="M").to_timestamp("M")
    return frame


def fee_sensitivity(snapshot,view):
    q=snapshot.frames["metrics"]
    q=q.loc[q.window.eq(view.window)&q.method.eq(view.method)]
    fig=go.Figure()
    for name,label in {"unmanaged":"Unmanaged","managed_shared_KF_risk":"Risk managed"}.items():
        f=q.loc[q.strategy.eq(name)].sort_values("cost_bps_per_dollar")
        fig.add_trace(go.Scatter(x=f.cost_bps_per_dollar,y=f["Sharpe (rf=0)"],name=label,mode="lines+markers",line=dict(color=COLORS[label],width=2.5)))
    style(fig,320,"Net Sharpe · rf = 0")
    fig.update_xaxes(title="One-way cost per dollar traded (bps)")
    fig.add_vline(x=view.cost,line_dash="dot",line_color="#d18d41")
    return fig
