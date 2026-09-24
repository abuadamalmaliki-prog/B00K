"""Causal multi-timeframe SMC + price features and first-passage labels (research only)."""
import os, sys, numpy as np, pandas as pd
from numba import njit
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'smc_strategy'))
import smc
DATA = os.environ.get("GOLD_DATA", "data")

def load(iv):
    d=pd.read_csv(os.path.join(DATA, f'XAUUSD_{iv}.csv'),parse_dates=['datetime']).set_index('datetime').sort_index()
    d=d[~d.index.duplicated()].astype(float)
    return d

@njit(cache=True)
def label(o,h,l,t_ns,tp,sl,spread,maxhold_ns):
    """Entry at o[i+1]. Long: fill ask=o+spread, exits on bid. Short: fill bid, exits on ask.
    Same bar TP&SL -> SL. Gap beyond SL fills at open; TP always exactly tp.
    Returns res (1 TP, -1 SL, 0 timeout/unresolved), pnl ($), exit index."""
    n=len(o); rl=np.zeros(n,np.int8); rs=np.zeros(n,np.int8); pl=np.zeros(n); ps=np.zeros(n); xl=np.full(n,-1); xs=np.full(n,-1)
    for i in range(n-1):
        e=o[i+1]+spread; T=e+tp; S=e-sl
        for j in range(i+1,n):
            if t_ns[j]-t_ns[i+1]>maxhold_ns:
                rl[i]=0; pl[i]=o[j]-e; xl[i]=j; break
            if l[j]<=S:
                rl[i]=-1; pl[i]=min(o[j],S)-e if j>i+1 else S-e; xl[i]=j; break
            if h[j]>=T:
                rl[i]=1; pl[i]=tp; xl[i]=j; break
        e=o[i+1]; T=e-tp; S=e+sl
        for j in range(i+1,n):
            if t_ns[j]-t_ns[i+1]>maxhold_ns:
                rs[i]=0; ps[i]=e-(o[j]+spread); xs[i]=j; break
            if h[j]+spread>=S:
                rs[i]=-1; ps[i]=e-max(o[j]+spread,S) if j>i+1 else e-S; xs[i]=j; break
            if l[j]+spread<=T:
                rs[i]=1; ps[i]=tp; xs[i]=j; break
    return rl,rs,pl,ps,xl,xs

def htf_map(base, d, rule_td, prefix, length=3):
    """SMC features of HTF frame d (bars labelled at open, duration rule_td), known at bar close; asof-mapped on base index (base bars labelled at open; base bar close = idx+base_td)."""
    f=smc.compute_all(d,length=length)
    c=d.close
    f['atr']=(d.high-d.low).rolling(14).mean()
    f['dist_sh']=(f.last_swing_high-c)/f.atr; f['dist_sl']=(c-f.last_swing_low)/f.atr
    f['in_bfvg']=((c>=f.bull_fvg_bot)&(c<=f.bull_fvg_top)).astype(float); f['in_sfvg']=((c>=f.bear_fvg_bot)&(c<=f.bear_fvg_top)).astype(float)
    f['in_bob']=((d.low<=f.bull_ob_top)&(c>=f.bull_ob_bot)).astype(float); f['in_sob']=((d.high>=f.bear_ob_bot)&(c<=f.bear_ob_top)).astype(float)
    f['sweep_recent']=f.sweep.rolling(6,min_periods=1).sum()
    f['bos_recent']=f.bos.rolling(6,min_periods=1).sum(); f['choch_recent']=f.choch.rolling(6,min_periods=1).sum()
    f['ret1']=c.pct_change()*1e3; f['ret3']=c.pct_change(3)*1e3
    keep=['trend','pd_pos','dist_sh','dist_sl','in_bfvg','in_sfvg','in_bob','in_sob','sweep_recent','bos_recent','choch_recent','ret1','ret3','bars_since_swing_high','bars_since_swing_low']
    f=f[keep].add_prefix(prefix)
    f.index=f.index+rule_td   # known at close
    return f

def build(base_iv='5min'):
    """Base frame + causal features. Base bars labelled at open (UTC); a feature row at bar t uses data up to t's close."""
    b=load(base_iv); btd=pd.Timedelta(base_iv)
    c=b.close; o=b.open
    F=pd.DataFrame(index=b.index)
    lr=np.log(c).diff()
    vol=lr.rolling(288,min_periods=50).std()
    for k in [1,3,6,12,24,48,96,288]:
        F[f'r{k}']=np.log(c/c.shift(k))/(vol*np.sqrt(k))
    for k in [12,48,144,288]:
        hi=b.high.rolling(k).max(); lo=b.low.rolling(k).min()
        F[f'rng{k}']=(c-lo)/(hi-lo+1e-9)
    F['volratio']=lr.rolling(12).std()/vol
    F['atr_usd']=(b.high-b.low).rolling(288,min_periods=50).mean()
    F['bar_body']=(c-o)/(b.high-b.low+1e-9)
    # day context in UTC days (broker day ~ NY 17:00; use UTC midnight as day anchor)
    mt=b.index+pd.Timedelta(hours=8)           # MYT
    day=b.index.normalize()
    g=b.groupby(day)
    dopen=g.open.transform('first'); dhi=g.high.cummax(); dlo=g.low.cummin()
    F['from_dopen']=(c-dopen)/F.atr_usd; F['day_pos']=(c-dlo)/(dhi-dlo+1e-9)
    D=g.agg(o=('open','first'),h=('high','max'),l=('low','min'),c=('close','last'))
    P=D.shift(1).reindex(day); P.index=b.index
    F['pdh_d']=(c-P.h)/F.atr_usd; F['pdl_d']=(c-P.l)/F.atr_usd; F['pd_col']=np.sign(P.c-P.o); F['pd_ret']=(P.c-P.o)/F.atr_usd
    F['hour_myt']=mt.hour+mt.minute/60; F['dow']=mt.dayofweek
    # SMC on base and HTFs
    fb=smc.compute_all(b,length=5)
    F['b_trend']=fb.trend; F['b_pd']=fb.pd_pos; F['b_sweep']=fb.sweep.rolling(6,min_periods=1).sum()
    F['b_choch']=fb.choch.rolling(12,min_periods=1).sum(); F['b_bos']=fb.bos.rolling(12,min_periods=1).sum()
    F['b_dsh']=(fb.last_swing_high-c)/F.atr_usd; F['b_dsl']=(c-fb.last_swing_low)/F.atr_usd
    for iv,td,pre in [x for x in [('15min','15min','m15_'),('1h','1h','h1_'),('4h','4h','h4_')] if pd.Timedelta(x[1])>btd]:
        d=load(iv); f=htf_map(b,d,pd.Timedelta(td),pre)
        f=f[~f.index.duplicated()]
        # base row t is known at t+btd; HTF row known at its index -> asof on (t+btd)
        key=pd.DataFrame({'k':b.index+btd},index=b.index)
        m=pd.merge_asof(key.reset_index(),f,left_on='k',right_index=True,direction='backward').set_index('datetime').drop(columns='k')
        F=F.join(m)
    # daily structure from 1h resample -> D1 SMC
    h1=load('1h'); D1=h1.resample('1D').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    fd=smc.compute_all(D1,length=2)[['trend','pd_pos']].add_prefix('d1_'); fd.index=fd.index+pd.Timedelta('1D')
    key=pd.DataFrame({'k':b.index+btd},index=b.index)
    F=F.join(pd.merge_asof(key.reset_index(),fd,left_on='k',right_index=True,direction='backward').set_index('datetime').drop(columns='k'))
    return b,F
