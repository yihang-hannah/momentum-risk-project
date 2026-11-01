import pandas as pd,numpy as np
from momentum_risk_project.ciz_quality import screen_formation_values


def test_formation_screen_rejects_stale_and_beginning_values_but_keeps_quotes():
    x=pd.DataFrame({'mthcaldt':pd.to_datetime(['1935-07-31']*5),'mthprcdt':pd.to_datetime(['1935-07-31','1935-07-29','1935-07-15','1935-07-31','1935-07-31']),
        'mthprc':[10.]*5,'mthcap':[100.]*5,'mthprcflg':['BA','BA','TR','MP','TR'],
        'mthdtflg':['PE','LA','NS','PE','PE'],'mthcompflg':['Y','R','R','G','R'], 'mthret':[.1]*5})
    before=x.copy(deep=True);y=screen_formation_values(x)
    assert y.formation_value_usable.tolist()==[True,False,False,False,True]
    assert y.mthcap.isna().tolist()==[False,True,True,True,False]
    pd.testing.assert_series_equal(y.mthret,x.mthret)
    pd.testing.assert_frame_equal(before,x)


def test_database_start_NS_is_usable_when_actual_date_is_period_end():
    x=pd.DataFrame({'mthcaldt':pd.to_datetime(['1925-12-31']), 'mthprcdt':pd.to_datetime(['1925-12-31']),
        'mthprc':[10.], 'mthcap':[100.], 'mthprcflg':['TR'], 'mthdtflg':['NS']})
    assert screen_formation_values(x).formation_value_usable.all()
