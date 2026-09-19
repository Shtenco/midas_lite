#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import json, os
from pathlib import Path
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('NUMEXPR_NUM_THREADS','1')
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
from price_equation_eurusd_h1_v3 import load_quotes, build_features, wilson_interval

CSV='/mnt/data/eurusd_h1/EURUSD_H1.csv'
BATCH_LO=int(os.environ.get('BATCH_LO','1')); BATCH_HI=int(os.environ.get('BATCH_HI','100'))
OUT=Path(f'/mnt/data/price_equation_v4_rolling_batch_{BATCH_LO}_{BATCH_HI}')
TARGET_HOUR=23; N_WINDOWS=100; WINDOW_MONTHS=2
LAST_WINDOW_START=pd.Timestamp('2026-06-01')
CANDIDATE_Q=[0.70,0.80,0.90,0.95,0.98,0.99]
MIN_VAL_SIGNALS=30
COSTS=[0.0,0.2,0.5,0.8,1.0,1.2,1.5]

raw=load_quotes(CSV)
data,features=build_features(raw)
spec=data[data['next_gap_h'].between(.99,1.01) & (data['Time'].dt.hour==TARGET_HOUR)].copy().reset_index(drop=True)
starts=[LAST_WINDOW_START-pd.DateOffset(months=2*(N_WINDOWS-1-i)) for i in range(N_WINDOWS)]

# Precache numeric matrix once; each process slices it by integer indices.
X_all=spec[features].to_numpy(float)
y_pips_all=spec['y_pips'].to_numpy(float)
times=spec['Time'].to_numpy()


def one_window(wi,start):
    end=start+pd.DateOffset(months=2)
    dev_idx=np.flatnonzero(spec['Time'].to_numpy() < np.datetime64(start))
    test_idx=np.flatnonzero((spec['Time'].to_numpy()>=np.datetime64(start))&(spec['Time'].to_numpy()<np.datetime64(end)))
    if len(dev_idx)<500 or len(test_idx)==0: return None
    cut=int(len(dev_idx)*.80)
    tr_idx=dev_idx[:cut]; va_idx=dev_idx[cut:]
    if len(tr_idx)<300 or len(va_idx)<100: return None
    imp=SimpleImputer(strategy='median')
    Xtr=imp.fit_transform(X_all[tr_idx]); Xv=imp.transform(X_all[va_idx]); Xt=imp.transform(X_all[test_idx])
    ytr=(y_pips_all[tr_idx]>0).astype(int); yt=(y_pips_all[test_idx]>0).astype(int)
    model=HistGradientBoostingClassifier(learning_rate=.05,max_iter=150,max_leaf_nodes=31,min_samples_leaf=100,l2_regularization=3.0,random_state=42)
    model.fit(Xtr,ytr)
    pv=model.predict_proba(Xv)[:,1]; sv=np.where(pv>=.5,1.,-1.); cv=np.abs(pv-.5); va_actual=y_pips_all[va_idx]
    cand=[]
    for q in CANDIDATE_Q:
        thr=float(np.quantile(cv,q)); m=cv>=thr; n=int(m.sum())
        if n<MIN_VAL_SIGNALS: continue
        cand.append({'quantile':q,'threshold':thr,'n':n,'accuracy':float(np.mean(sv[m]==np.sign(va_actual[m]))),'gross_mean_pips':float(np.mean(sv[m]*va_actual[m])),'gross_sum_pips':float(np.sum(sv[m]*va_actual[m]))})
    if not cand: return None
    best=max(cand,key=lambda z:z['gross_mean_pips']); fixed_thr=float(np.quantile(cv,.90))
    pt=model.predict_proba(Xt)[:,1]; st=np.where(pt>=.5,1.,-1.); ct=np.abs(pt-.5); actual=y_pips_all[test_idx]; corr_all=st==np.sign(actual)
    outs=[]
    for mode,q,thr in [('adaptive',best['quantile'],best['threshold']),('fixed_q90',.90,fixed_thr)]:
        m=ct>=thr; gross=st[m]*actual[m]; corr=corr_all[m]
        idx=test_idx[m]
        sel=spec.iloc[idx][['Time','Close','Spread']].copy()
        sel['window_id']=wi; sel['window_start']=start; sel['window_end_exclusive']=end; sel['mode']=mode; sel['validation_quantile']=q; sel['threshold']=thr
        sel['prob_up']=pt[m]; sel['confidence']=ct[m]; sel['signal']=st[m]; sel['actual_move_pips']=actual[m]; sel['gross_pips']=gross; sel['correct']=corr
        sel['spread_pips_recorded']=sel['Spread'].astype(float)/10.; sel['net_after_recorded_spread_pips']=sel['gross_pips']-sel['spread_pips_recorded']
        row={'window_id':wi,'window_start':str(start),'window_end_exclusive':str(end),'mode':mode,'dev_rows':len(dev_idx),'train_rows':len(tr_idx),'validation_rows':len(va_idx),'test_rows':len(test_idx),
             'train_start':str(spec.iloc[tr_idx[0]].Time),'train_end':str(spec.iloc[tr_idx[-1]].Time),'validation_start':str(spec.iloc[va_idx[0]].Time),'validation_end':str(spec.iloc[va_idx[-1]].Time),
             'validation_quantile':q,'confidence_threshold':thr,'validation_choice_gross_mean_pips':best['gross_mean_pips'] if mode=='adaptive' else None,
             'all_test_accuracy':float(corr_all.mean()),'all_test_auc':float(roc_auc_score(yt,pt)) if len(np.unique(yt))>1 else None,'signals':int(m.sum()),'signal_rate':float(m.mean()),
             'selected_correct':int(corr.sum()),'selected_accuracy':None if len(corr)==0 else float(corr.mean()),'gross_mean_pips':None if len(gross)==0 else float(gross.mean()),'gross_sum_pips':float(gross.sum()),
             'mean_abs_move_pips':None if len(gross)==0 else float(np.mean(np.abs(actual[m]))),'mean_recorded_spread_pips':None if len(gross)==0 else float(sel.spread_pips_recorded.mean()),
             'net_after_recorded_spread_mean_pips':None if len(gross)==0 else float(sel.net_after_recorded_spread_pips.mean()),'net_after_recorded_spread_sum_pips':float(sel.net_after_recorded_spread_pips.sum())}
        for c in COSTS:
            row[f'net_mean_cost_{c:.1f}']=None if len(gross)==0 else float(gross.mean()-c); row[f'net_sum_cost_{c:.1f}']=float(gross.sum()-c*len(gross))
        outs.append((row,sel))
    ab=spec.iloc[test_idx][['Time','Close','Spread','y_pips']].copy(); ab['window_id']=wi; ab['window_start']=start; ab['window_end_exclusive']=end; ab['prob_up']=pt; ab['confidence']=ct; ab['signal']=st; ab['correct']=corr_all; ab['gross_pips']=st*actual
    return outs,ab

results=[]
for i in range(BATCH_LO,BATCH_HI+1):
    s0=starts[i-1]
    results.append(one_window(i,s0))
    if i % 5 == 0: print(f'completed {i}', flush=True)
window_rows=[]; trade_frames=[]; allbar_frames=[]
for r in results:
    if r is None: continue
    outs,ab=r; allbar_frames.append(ab)
    for row,sel in outs: window_rows.append(row); trade_frames.append(sel)
windows=pd.DataFrame(window_rows); trades=pd.concat(trade_frames,ignore_index=True) if trade_frames else pd.DataFrame(); allbars=pd.concat(allbar_frames,ignore_index=True) if allbar_frames else pd.DataFrame()

def maxdd(x):
    x=np.asarray(x,float)
    if len(x)==0:return None
    eq=np.cumsum(x); peak=np.maximum.accumulate(np.r_[0.,eq]); return float((np.r_[0.,eq]-peak).min())

def summary(mode):
    w=windows[windows['mode']==mode].copy(); t=trades[trades['mode']==mode].sort_values('Time').copy(); nz=w[w.signals>0]
    n=len(t); k=int(t.correct.sum()) if n else 0
    z={'windows':len(w),'windows_with_signals':len(nz),'total_test_candidate_bars':int(w.test_rows.sum()),'total_signals':n,
       'pooled_accuracy':None if not n else float(t.correct.mean()),'pooled_accuracy_wilson95':None if not n else list(wilson_interval(k,n)),
       'pooled_gross_mean_pips':None if not n else float(t.gross_pips.mean()),'pooled_gross_median_pips':None if not n else float(t.gross_pips.median()),'pooled_gross_sum_pips':float(t.gross_pips.sum()) if n else 0.,
       'median_window_accuracy':None if len(nz)==0 else float(nz.selected_accuracy.median()),'q25_window_accuracy':None if len(nz)==0 else float(nz.selected_accuracy.quantile(.25)),'q75_window_accuracy':None if len(nz)==0 else float(nz.selected_accuracy.quantile(.75)),
       'median_window_gross_mean_pips':None if len(nz)==0 else float(nz.gross_mean_pips.median()),'q25_window_gross_mean_pips':None if len(nz)==0 else float(nz.gross_mean_pips.quantile(.25)),'q75_window_gross_mean_pips':None if len(nz)==0 else float(nz.gross_mean_pips.quantile(.75)),
       'profitable_window_fraction_gross':None if len(nz)==0 else float((nz.gross_sum_pips>0).mean()),'positive_expectancy_window_fraction_gross':None if len(nz)==0 else float((nz.gross_mean_pips>0).mean()),
       'max_drawdown_gross_pips_trade_sequence':maxdd(t.gross_pips) if n else None,'mean_recorded_spread_pips':None if not n else float(t.spread_pips_recorded.mean()),
       'pooled_net_after_recorded_spread_mean_pips':None if not n else float(t.net_after_recorded_spread_pips.mean()),'pooled_net_after_recorded_spread_sum_pips':float(t.net_after_recorded_spread_pips.sum()) if n else 0.,
       'max_drawdown_after_recorded_spread_pips':maxdd(t.net_after_recorded_spread_pips) if n else None,'validation_quantile_distribution':{str(k):int(v) for k,v in w.validation_quantile.value_counts().sort_index().items()},'cost_sensitivity':[]}
    for c in COSTS:
        if n:
            tt=t.assign(net=t.gross_pips-c); sums=tt.groupby('window_id').net.sum()
            z['cost_sensitivity'].append({'all_in_cost_pips':c,'net_mean_pips':float(tt.net.mean()),'net_total_pips':float(tt.net.sum()),'profitable_window_fraction_among_windows_with_signals':float((sums>0).mean()),'max_drawdown_pips':maxdd(tt.net)})
    if len(nz):
        cols=['window_id','window_start','signals','selected_accuracy','gross_mean_pips','gross_sum_pips']
        z['worst_10_windows']=nz.nsmallest(10,'gross_sum_pips')[cols].to_dict('records'); z['best_10_windows']=nz.nlargest(10,'gross_sum_pips')[cols].to_dict('records')
    return z

report={'version':'PriceEquation EURUSD H1 V4 Specialist23 rolling 100x2M pseudo-OOS','methodology':{'target_hour':23,'transition':'23:00 -> 00:00 strict +1h only','windows':100,'window_months':2,'first_window_start':str(starts[0]),'last_window_start':str(starts[-1]),'last_window_end_exclusive':str(starts[-1]+pd.DateOffset(months=2)),'development_split_each_window':'80% chronological train / 20% validation, all strictly before test','adaptive_gate':'validation-only quantile selection by gross mean, min 30 validation signals','fixed_benchmark':'q=0.90'},'source':{'rows_raw':len(raw),'start':str(raw.Time.min()),'end':str(raw.Time.max()),'hour23_strict_rows':len(spec)},'adaptive':summary('adaptive'),'fixed_q90':summary('fixed_q90')}
wa=windows[windows['mode']=='adaptive']; era=[]
for lo in range(1,101,20):
    hi=min(100,lo+19); w=wa[(wa.window_id>=lo)&(wa.window_id<=hi)]; t=trades[(trades['mode']=='adaptive')&(trades.window_id>=lo)&(trades.window_id<=hi)]
    era.append({'window_ids':f'{lo}-{hi}','start':w.window_start.min(),'end_exclusive':w.window_end_exclusive.max(),'signals':len(t),'accuracy':None if len(t)==0 else float(t.correct.mean()),'gross_mean_pips':None if len(t)==0 else float(t.gross_pips.mean()),'gross_sum_pips':float(t.gross_pips.sum()) if len(t) else 0.,'profitable_windows_gross_fraction':float((w[w.signals>0].gross_sum_pips>0).mean()) if (w.signals>0).any() else None})
report['adaptive']['era_20window_blocks']=era
OUT.mkdir(parents=True,exist_ok=True); windows.to_csv(OUT/'v4_rolling_100_window_metrics.csv',index=False); trades.to_csv(OUT/'v4_rolling_100_selected_trades.csv',index=False); allbars.to_csv(OUT/'v4_rolling_100_all_test_bars.csv',index=False); (OUT/'v4_rolling_100_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
A=report['adaptive'];F=report['fixed_q90']; (OUT/'README_RU.txt').write_text(f'''V4 rolling 100 x 2-month pseudo-OOS\nDataset {raw.Time.min()} -> {raw.Time.max()}\nWindows {starts[0].date()} -> {(starts[-1]+pd.DateOffset(months=2)-pd.Timedelta(hours=1)).date()}\n\nADAPTIVE\nSignals {A['total_signals']}\nAccuracy {A['pooled_accuracy']:.4%}\nWilson95 {A['pooled_accuracy_wilson95'][0]:.4%}..{A['pooled_accuracy_wilson95'][1]:.4%}\nGross mean {A['pooled_gross_mean_pips']:.4f}\nGross total {A['pooled_gross_sum_pips']:.2f}\nProfitable windows {A['profitable_window_fraction_gross']:.2%}\nMedian window accuracy {A['median_window_accuracy']:.2%}\nMedian window expectancy {A['median_window_gross_mean_pips']:.4f}\nMax DD gross {A['max_drawdown_gross_pips_trade_sequence']:.2f}\nApprox after recorded spread mean {A['pooled_net_after_recorded_spread_mean_pips']:.4f}\n\nFIXED Q90\nSignals {F['total_signals']}\nAccuracy {F['pooled_accuracy']:.4%}\nGross mean {F['pooled_gross_mean_pips']:.4f}\nGross total {F['pooled_gross_sum_pips']:.2f}\nProfitable windows {F['profitable_window_fraction_gross']:.2%}\n''',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
