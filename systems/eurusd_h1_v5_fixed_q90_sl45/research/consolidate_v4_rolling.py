import json, glob, zipfile
from pathlib import Path
import numpy as np, pandas as pd
from math import sqrt
OUT=Path('/mnt/data/price_equation_v4_rolling_100_output'); OUT.mkdir(exist_ok=True)
dirs=[Path(x) for x in sorted(glob.glob('/mnt/data/price_equation_v4_rolling_batch_*'), key=lambda p:int(Path(p).name.split('_')[-2]))]
windows=pd.concat([pd.read_csv(d/'v4_rolling_100_window_metrics.csv') for d in dirs], ignore_index=True)
trades=pd.concat([pd.read_csv(d/'v4_rolling_100_selected_trades.csv') for d in dirs], ignore_index=True)
allbars=pd.concat([pd.read_csv(d/'v4_rolling_100_all_test_bars.csv') for d in dirs], ignore_index=True)
# dedupe safety
windows=windows.drop_duplicates(['window_id','mode']).sort_values(['window_id','mode']).reset_index(drop=True)
trades=trades.drop_duplicates(['window_id','mode','Time']).sort_values(['Time','mode']).reset_index(drop=True)
allbars=allbars.drop_duplicates(['window_id','Time']).sort_values(['window_id','Time']).reset_index(drop=True)

def wilson(k,n,z=1.959963984540054):
    if n==0:return [None,None]
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [float(c-h),float(c+h)]
def maxdd(x):
    x=np.asarray(x,float)
    if len(x)==0:return None
    eq=np.cumsum(x); peak=np.maximum.accumulate(np.r_[0.,eq]); return float((np.r_[0.,eq]-peak).min())
def summary(mode):
    w=windows[windows['mode']==mode].copy(); t=trades[trades['mode']==mode].copy().sort_values('Time'); nz=w[w['signals']>0]
    n=len(t); k=int(t['correct'].astype(bool).sum())
    s={
      'windows':int(len(w)),'windows_with_signals':int(len(nz)), 'total_candidate_bars':int(w.test_rows.sum()), 'total_signals':int(n),
      'pooled_accuracy':float(t.correct.mean()) if n else None,'wilson95':wilson(k,n),'correct':k,'wrong':int(n-k),
      'gross_mean_pips':float(t.gross_pips.mean()) if n else None,'gross_median_pips':float(t.gross_pips.median()) if n else None,'gross_total_pips':float(t.gross_pips.sum()) if n else 0.,
      'median_window_accuracy':float(nz.selected_accuracy.median()) if len(nz) else None,'q25_window_accuracy':float(nz.selected_accuracy.quantile(.25)) if len(nz) else None,'q75_window_accuracy':float(nz.selected_accuracy.quantile(.75)) if len(nz) else None,
      'median_window_expectancy':float(nz.gross_mean_pips.median()) if len(nz) else None,'q25_window_expectancy':float(nz.gross_mean_pips.quantile(.25)) if len(nz) else None,'q75_window_expectancy':float(nz.gross_mean_pips.quantile(.75)) if len(nz) else None,
      'profitable_windows_gross_fraction':float((nz.gross_sum_pips>0).mean()) if len(nz) else None,
      'positive_expectancy_windows_fraction':float((nz.gross_mean_pips>0).mean()) if len(nz) else None,
      'windows_accuracy_ge_60':float((nz.selected_accuracy>=.60).mean()) if len(nz) else None,
      'windows_accuracy_ge_70':float((nz.selected_accuracy>=.70).mean()) if len(nz) else None,
      'gross_max_drawdown_pips':maxdd(t.gross_pips.values) if n else None,
      'mean_recorded_spread_pips':float(t.spread_pips_recorded.mean()) if n else None,
      'after_recorded_spread_mean_pips':float(t.net_after_recorded_spread_pips.mean()) if n else None,
      'after_recorded_spread_total_pips':float(t.net_after_recorded_spread_pips.sum()) if n else None,
      'after_recorded_spread_maxdd_pips':maxdd(t.net_after_recorded_spread_pips.values) if n else None,
      'validation_q_counts':{str(k):int(v) for k,v in w.validation_quantile.value_counts().sort_index().items()},
      'cost_sensitivity':[]
    }
    for c in [0,.2,.5,.8,1.0,1.2,1.5]:
        if n:
            tt=t.copy(); tt['net']=tt.gross_pips-c
            ws=tt.groupby('window_id').net.sum()
            s['cost_sensitivity'].append({'cost_pips':c,'mean_pips':float(tt.net.mean()),'total_pips':float(tt.net.sum()),'profitable_windows_fraction':float((ws>0).mean()),'maxdd_pips':maxdd(tt.net.values)})
    # 20-window eras
    eras=[]
    for lo in range(1,101,20):
        hi=lo+19; ww=w[(w.window_id>=lo)&(w.window_id<=hi)]; tt=t[(t.window_id>=lo)&(t.window_id<=hi)]
        ntt=len(tt)
        eras.append({'windows':f'{lo}-{hi}','start':ww.window_start.min(),'end':ww.window_end_exclusive.max(),'signals':ntt,
                     'accuracy':float(tt.correct.mean()) if ntt else None,'gross_mean_pips':float(tt.gross_pips.mean()) if ntt else None,'gross_total_pips':float(tt.gross_pips.sum()) if ntt else 0.,
                     'profitable_window_fraction':float((ww[ww.signals>0].gross_sum_pips>0).mean()) if (ww.signals>0).any() else None})
    s['eras_20_windows']=eras
    cols=['window_id','window_start','signals','selected_accuracy','gross_mean_pips','gross_sum_pips','validation_quantile']
    s['worst_10']=nz.nsmallest(10,'gross_sum_pips')[cols].to_dict('records')
    s['best_10']=nz.nlargest(10,'gross_sum_pips')[cols].to_dict('records')
    return s
report={'version':'V4 Specialist23 rolling pseudo-OOS 100 x 2 months','window_range':{'first':'2009-12-01','last_start':'2026-06-01','last_end_exclusive':'2026-08-01'},'adaptive':summary('adaptive'),'fixed_q90':summary('fixed_q90')}
# compare last 20 vs first 80
for mode in ['adaptive','fixed_q90']:
    t=trades[trades['mode']==mode]
    for name,mask in [('first80',t.window_id<=80),('last20',t.window_id>80)]:
        x=t[mask]
        report[mode][name]={'signals':len(x),'accuracy':float(x.correct.mean()) if len(x) else None,'gross_mean_pips':float(x.gross_pips.mean()) if len(x) else None,'gross_total_pips':float(x.gross_pips.sum()) if len(x) else 0.}
# cumulative per trade and per window for charts/inspection
for mode in ['adaptive','fixed_q90']:
    ix=trades['mode']==mode
    trades.loc[ix,'cum_gross_pips']=trades.loc[ix].sort_values('Time').gross_pips.cumsum().values
windows.to_csv(OUT/'v4_rolling_100_window_metrics.csv',index=False)
trades.to_csv(OUT/'v4_rolling_100_selected_trades.csv',index=False)
allbars.to_csv(OUT/'v4_rolling_100_all_test_bars.csv',index=False)
(OUT/'v4_rolling_100_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
A=report['adaptive'];F=report['fixed_q90']
(OUT/'README_RU.txt').write_text(f'''V4 Specialist23 — rolling pseudo-OOS, 100 последовательных двухмесячных окон\n\nОкна: 2009-12-01 ... 2026-07-31\nВ каждом окне используются только данные до начала окна. Development делится 80/20 по времени на train/validation. Test = следующие 2 месяца.\n\nADAPTIVE GATE\nСигналов: {A['total_signals']}\nAccuracy: {A['pooled_accuracy']:.2%} (Wilson95 {A['wilson95'][0]:.2%}..{A['wilson95'][1]:.2%})\nGross expectancy: {A['gross_mean_pips']:.3f} pip/trade\nGross total: {A['gross_total_pips']:.1f} pips\nДоля прибыльных окон: {A['profitable_windows_gross_fraction']:.2%}\nMedian window accuracy: {A['median_window_accuracy']:.2%}\nMedian window expectancy: {A['median_window_expectancy']:.3f} pip/trade\nMax DD gross: {A['gross_max_drawdown_pips']:.1f} pips\nПосле recorded spread (приблизительно): {A['after_recorded_spread_mean_pips']:.3f} pip/trade\n\nFIXED q=0.90\nСигналов: {F['total_signals']}\nAccuracy: {F['pooled_accuracy']:.2%}\nGross expectancy: {F['gross_mean_pips']:.3f} pip/trade\nGross total: {F['gross_total_pips']:.1f} pips\nДоля прибыльных окон: {F['profitable_windows_gross_fraction']:.2%}\n''',encoding='utf-8')
# zip
zip_path='/mnt/data/price_equation_v4_rolling_100_bundle.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for p in [Path('/mnt/data/price_equation_eurusd_h1_v4_rolling_100.py'), OUT/'v4_rolling_100_report.json',OUT/'v4_rolling_100_window_metrics.csv',OUT/'v4_rolling_100_selected_trades.csv',OUT/'v4_rolling_100_all_test_bars.csv',OUT/'README_RU.txt']:
        z.write(p,arcname=p.name)
print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
