"""Plot SCF family wealth by parents' education, 2016–2025.
Requires pandas, numpy, matplotlib. Run get_data.py first.
"""
import argparse
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

YEARS = (2016, 2019, 2022, 2025)
LABELS = {1:'Less than high school', 2:'High school',
          3:'Some college / associate', 4:"Bachelor’s or higher"}
COLORS = {1:'#9B5945', 2:'#BD871D', 3:'#27857D', 4:'#254F87'}

def stata(path, columns=None):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith('.dta'))
        with z.open(name) as f:
            if columns is not None:
                reader = pd.read_stata(f, iterator=True, convert_categoricals=False)
                names = {n.lower():n for n in reader.variable_labels()}
                f.seek(0)
                d = pd.read_stata(f, columns=[names[c] for c in columns], convert_categoricals=False)
            else:
                d = pd.read_stata(f, convert_categoricals=False)
    d.columns = d.columns.str.lower()
    return d

def median(x, w):
    order = np.argsort(x, kind='stable'); x, w = np.asarray(x)[order], np.asarray(w)[order]
    total = w.sum()
    if not total > 0: raise ValueError('Empty weighted group')
    c = w.cumsum(); i = np.searchsorted(c, total/2, side='left')
    # SAS-style inverse weighted empirical CDF; average at an exact half-weight boundary.
    return (x[i]+x[i+1])/2 if c[i] == total/2 and i+1 < len(x) else x[i]

def analyze(raw):
    results, audit = [], []
    for year in YEARS:
        full = stata(raw / f'scf{year}s.zip', ['y1','yy1','x6032','x6033','x42001'])
        with zipfile.ZipFile(raw / f'scfp{year}excel.zip') as z:
            with z.open(next(n for n in z.namelist() if n.lower().endswith('.csv'))) as f:
                extract = pd.read_csv(f)
        extract.columns = extract.columns.str.lower()
        d = full.merge(extract[['y1','yy1','networth','wgt','age']],
                       on=['y1','yy1'], how='outer', validate='one_to_one', indicator=True)
        assert (d['_merge']=='both').all(), 'Incomplete merge'
        assert d.groupby('yy1').size().eq(5).all(), 'Expected five implicates per family'
        d['implicate'] = d.y1.astype('int64') - 10*d.yy1.astype('int64')
        assert set(d.implicate)==set(range(1,6))
        assert np.isfinite(d[['networth','wgt']]).all().all() and (d.wgt>0).all()
        assert np.allclose(5*d.wgt, d.x42001), 'Extract and raw weights disagree'
        # -1 is valid: less than first grade, not missing.
        codes = {-1:1, 1:1, 8:2, 9:3, 12:4}
        mother, father = d.x6032.map(codes), d.x6033.map(codes)
        valid = mother.notna() & father.notna()
        d['group'] = np.maximum(mother, father)
        audit.append({'year':year, 'families':int(d.yy1.nunique()),
                      'records':len(d), 'excluded_records':int((~valid).sum()),
                      'excluded_weight_share':float(d.loc[~valid,'wgt'].sum()/d.wgt.sum()),
                      'population_estimate':float(d.wgt.sum()),
                      'all_family_median':float(np.mean([median(g.networth, g.wgt) for _,g in d.groupby('implicate')]))})
        d = d.loc[valid].copy()
        rw = stata(raw / f'scf{year}rw1s.zip')
        assert rw.y1.is_unique
        first = d[d.implicate==1].merge(rw, on='y1', how='left', validate='one_to_one', indicator='rw_merge')
        assert (first.rw_merge=='both').all()
        # Official bootstrap weights must be multiplied by selection multiplicities.
        weights = first[[f'wt1b{i}' for i in range(1,1000)]].fillna(0).to_numpy(dtype=float)
        weights *= first[[f'mm{i}' for i in range(1,1000)]].fillna(0).to_numpy(dtype=float)
        assert (weights>=0).all()
        for group in LABELS:
            g = d[d.group==group]
            im = np.array([median(h.networth,h.wgt) for _,h in g.groupby('implicate')])
            assert len(im)==5
            m = first.group.to_numpy()==group
            x = first.loc[m,'networth'].to_numpy()
            order = np.argsort(x, kind='stable'); x=x[order]; w=weights[m][order]
            sums=w.sum(axis=0); assert (sums>0).all()
            cum=w.cumsum(axis=0)
            idx=(cum>=sums[None,:]/2).argmax(axis=0)
            reps=x[idx]
            boundary=(cum[idx,np.arange(999)]==sums/2)&(idx<len(x)-1)
            reps[boundary]=(reps[boundary]+x[idx[boundary]+1])/2
            assert np.allclose(reps[[0,99,998]], [median(x,w[:,j]) for j in (0,99,998)])
            # Federal Reserve codebook MEANIT method: first-implicate sampling
            # variance plus (1+1/5) times between-implicate variance.
            se=float(np.sqrt(np.var(reps,ddof=1)+1.2*np.var(im,ddof=1)))
            estimate=float(im.mean())
            results.append({'year':year, 'group':group,'parent_education':LABELS[group],
                            'median_networth_2025_dollars':estimate, 'standard_error':se,
                            'ci95_low':estimate-1.96*se,'ci95_high':estimate+1.96*se,
                            'mean_unweighted_families':len(g)/5,
                            'population_share':g.wgt.sum()/d.wgt.sum()})
        print(f'Validated and estimated {year}',flush=True)
    return pd.DataFrame(results), audit

def draw(data, out):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
                         'axes.spines.top':False,'axes.spines.right':False,
                         'axes.spines.left':False,'axes.spines.bottom':False})
    fig,ax=plt.subplots(figsize=(12.5,8),facecolor='#FAFAF7')
    ax.set_facecolor('#FAFAF7'); fig.subplots_adjust(left=.10,right=.75,top=.73,bottom=.25)
    fig.text(.10,.93,'Family wealth by parents’ education',fontsize=24,fontweight='bold',color='#192D3D')
    fig.text(.10,.877,'Median family net worth • constant 2025 dollars',fontsize=14,color='#405463')
    fig.text(.10,.824,'2016–2025 SCF  |  Parental education was not collected in 1989–2013.',
             fontsize=11,color='#596773')
    for group in LABELS:
        g=data[data.group==group]; x=g.year.to_numpy(); y=g.median_networth_2025_dollars.to_numpy()/1000
        low=g.ci95_low.to_numpy()/1000; high=g.ci95_high.to_numpy()/1000
        ax.fill_between(x,low,high,color=COLORS[group],alpha=.10,linewidth=0)
        ax.plot(x,y,color=COLORS[group],lw=2.7,marker='o',ms=6)
        label_y=y[-1]+{1:-9,2:0,3:7,4:0}[group]
        if group in (1,3):
            ax.plot([2025.04,2025.28],[y[-1],label_y],color=COLORS[group],lw=.8,clip_on=False)
        ax.text(2025.35,label_y,LABELS[group]+'\n'+f'${y[-1]:,.0f}k',va='center',
                fontsize=11,color=COLORS[group],fontweight='bold')
    ax.set_xlim(2015.7,2025.2); ax.set_xticks(YEARS)
    ax.set_ylim(min(0,data.ci95_low.min()/1000),data.ci95_high.max()/1000*1.1)
    ax.yaxis.set_major_locator(MultipleLocator(100))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'${x:,.0f}k'))
    ax.tick_params(axis='both',length=0,pad=9,labelcolor='#405463')
    ax.grid(axis='y',color='#D9DEDE',lw=.7);ax.set_axisbelow(True)
    fig.text(.10,.17,'Families: all SCF primary economic units; no age restriction. Groups use the higher education of the',fontsize=10,color='#405463')
    fig.text(.10,.145,'reference person’s mother or father. “Some college” includes associate degrees. Family wealth = assets − debts.',fontsize=10,color='#405463')
    fig.text(.10,.108,'Weighted medians averaged over five imputations. Shading: approximate 95% intervals using 999 bootstrap',fontsize=9.5,color='#596773')
    fig.text(.10,.084,'replicate weights plus imputation uncertainty. Descriptive comparisons; not adjusted for age or other characteristics.',fontsize=9.5,color='#596773')
    fig.text(.10,.043,'Source: Federal Reserve Board, SCF full public files and summary extracts. Downloaded October 16, 2026.',fontsize=9,color='#596773')
    for ext in ('png','svg'):
        fig.savefig(out/f'wealth_by_parent_education.{ext}',dpi=200,facecolor=fig.get_facecolor())
    plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=Path(__file__).parent/'data/raw')
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'output')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    data,audit=analyze(args.data)
    data.to_csv(args.output/'estimates.csv',index=False)
    (args.output/'validation.json').write_text(json.dumps(audit,indent=2)+'\n')
    draw(data,args.output)
    print(data[['year','parent_education','median_networth_2025_dollars','standard_error']].to_string(index=False))

if __name__=='__main__': main()
