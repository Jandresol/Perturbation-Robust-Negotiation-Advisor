"""Local, content-addressed Matplotlib figures from saved case measurements. No model calls."""
import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
import textwrap
import threading
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'negotiation-matplotlib'))
LOCK=threading.Lock()
VERSION='case-figures-v3'
PLOTS=('acceptance','distance','nli','rejections','noise_match','sentence_pairs')
LABELS={'paraphrase_fact':'Paraphrase (fact)','paraphrase_doc':'Paraphrase (document)','register':'Register shift (document)'}
COLORS={'paraphrase_fact':'#2b7bdb','paraphrase_doc':'#f36933','register':'#19b283'}
REASONS={'accepted':('Accepted','green'),'cosine':('Rejected: cosine similarity','#efa500'),'nli_fwd':('Rejected: forward entailment','#e87da5'),'nli_bwd':('Rejected: backward entailment','#6652da'),'hard_facts':('Rejected: hard facts','#e74747'),'unknown':('Rejected: unspecified','#888888')}


def measurements(package):
    facts={f['id']:f for f in package.get('facts',[])}
    sources={s['id']:s for s in package.get('sources',[])}
    rows=[]
    for variant in package.get('variants',[]):
        m=variant.get('audit') or variant.get('validation')
        if isinstance(m,str):
            try:m=json.loads(m)
            except (ValueError,TypeError):continue
        if not isinstance(m,dict) or type(m.get('accepted')) is not bool:continue
        frame=variant.get('frame','')
        level=m.get('level') or next((x for x in ['light','moderate','heavy'] if re.search(r'\b'+x+r'\b',frame,re.I)),'unspecified')
        operator=m.get('operator') or ('paraphrase_fact' if variant.get('method')=='peer-semantic-v1' else 'unspecified')
        fact=facts.get(variant.get('factId'),{})
        row={'id':str(variant.get('id','')),'operator':str(operator),'level':str(level),'accepted':m['accepted'],
             'reject_reason':'accepted' if m['accepted'] else m.get('reject_reason') or 'unknown',
             'original':str(fact.get('text','Original claim unavailable')),'text':str(variant.get('text','')),
             'source':str(sources.get(fact.get('sourceId'),{}).get('title','Source unavailable')),'factId':variant.get('factId')}
        for key in ['cos','d_emb','nli_fwd','nli_bwd','noise_d_emb','nli_threshold']:
            value=m.get(key)
            row[key]=value if type(value) in [int,float] and math.isfinite(value) else None
        rows.append(row)
    if len(rows)>2048:raise ValueError('Too many measurements to plot')
    return rows


def _style(ax):
    ax.spines[['top','right']].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='y',color='#e3e2dd',linewidth=1)


def _empty(ax,message):
    ax.axis('off');ax.text(.5,.5,message,ha='center',va='center',wrap=True,transform=ax.transAxes,color='#637269',fontsize=13)


def build_figures(package,root):
    rows=measurements(package)
    material={'version':VERSION,'title':str(package.get('title','Current case')),'rows':rows}
    key=hashlib.sha256(json.dumps(material,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    target=Path(root)/key
    with LOCK:
        if not (target/'manifest.json').exists():
            target.mkdir(parents=True,exist_ok=True)
            _render(rows,target)
            (target/'manifest.json').write_text(json.dumps({'count':len(rows),'accepted':sum(r['accepted'] for r in rows)}))
    return {'key':key,'count':len(rows),'accepted':sum(r['accepted'] for r in rows),'plots':{name:{ext:f'/api/engines/figures/{key}/{name}.{ext}' for ext in ['png','pdf']} for name in PLOTS},'csv':f'/api/engines/figures/{key}/measurements.csv'}


def _render(rows,target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import PercentFormatter
    import numpy as np
    ops=list(dict.fromkeys(r['operator'] for r in rows))
    levels=[x for x in ['light','moderate','heavy','unspecified'] if any(r['level']==x for r in rows)]
    levels+=list(dict.fromkeys(r['level'] for r in rows if r['level'] not in levels))
    colors={op:COLORS.get(op,plt.get_cmap('tab10')(i%10)) for i,op in enumerate(ops)}
    def save(fig,name):
        for ext in ['png','pdf']:fig.savefig(target/f'{name}.{ext}',dpi=170,bbox_inches='tight',facecolor='white')
        plt.close(fig)
    def panels():
        fig,axes=plt.subplots(1,max(1,len(ops)),figsize=(max(7,5*len(ops)),4.4),squeeze=False)
        return fig,axes[0]
    with plt.rc_context({'font.family':'DejaVu Sans','font.size':12,'axes.labelsize':14,'axes.titlesize':15,'axes.edgecolor':'#44443f','axes.linewidth':1.2,'svg.fonttype':'none','text.parse_math':False}):
        fig,ax=plt.subplots(figsize=(10,4.5));_style(ax)
        if rows:
            width=.8/len(ops)
            for i,op in enumerate(ops):
                for j,level in enumerate(levels):
                    group=[r for r in rows if r['operator']==op and r['level']==level]
                    if not group:continue
                    n=sum(r['accepted'] for r in group);x=j-.4+width*(i+.5)
                    ax.bar(x,n/len(group),width*.94,color=colors[op],label=LABELS.get(op,op) if j==next(k for k,l in enumerate(levels) if any(r['operator']==op and r['level']==l for r in rows)) else None)
                    ax.text(x,n/len(group)+.025,f'{n}/{len(group)}',ha='center')
            ax.set_xticks(range(len(levels)),[x.title() for x in levels]);ax.set_ylim(0,1.14);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_ylabel('Acceptance rate');ax.set_xlabel('Requested rewording strength');ax.legend(loc='lower left',bbox_to_anchor=(0,1.02),ncol=min(3,len(ops)),frameon=False)
        else:_empty(ax,'No semantic measurements saved for this case yet.')
        save(fig,'acceptance')
        legend=[Line2D([],[],marker='o',linestyle='',color='#444',label='Accepted (filled; colour = operator)'),Line2D([],[],marker='o',linestyle='',markerfacecolor='none',markeredgecolor='#8a8983',label='Rejected (open)')]
        for name in ['distance','nli']:
            fig,axes=panels()
            for i,op in enumerate(ops):
                ax=axes[i];_style(ax);group=[r for r in rows if r['operator']==op];ax.set_title(f'({chr(97+i)}) {LABELS.get(op,op)}'+(f'\nn = {len(group)}' if name=='nli' else ''),loc='left')
                plotted=0
                for j,r in enumerate(group):
                    if name=='distance':
                        if r['d_emb'] is None:continue
                        x=levels.index(r['level'])+((j*0.61803398875)%1-.5)*.25;y=r['d_emb']
                    else:
                        if r['nli_fwd'] is None or r['nli_bwd'] is None:continue
                        x=r['nli_fwd'];y=r['nli_bwd']
                    ax.scatter(x,y,s=45,facecolors=colors[op] if r['accepted'] else 'none',edgecolors='white' if r['accepted'] else '#8a8983',linewidths=1.1,alpha=.9);plotted+=1
                if name=='distance':
                    ax.set_xticks(range(len(levels)),[x.title() for x in levels]);ax.set_xlim(-.5,len(levels)-.5);ax.set_ylabel(r'$d_{\mathrm{emb}}$',parse_math=True);ax.set_ylim(bottom=0)
                    ax.ticklabel_format(axis='y',style='sci',scilimits=(-2,3))
                else:
                    ax.set_xlim(-.04,1.04);ax.set_ylim(-.04,1.04);ax.grid(axis='x',color='#e3e2dd');ax.set_ylabel(r'$P_{\mathrm{entail}}(\mathrm{reworded}\Rightarrow\mathrm{original})$',parse_math=True)
                    thresholds={r['nli_threshold'] for r in group if r['nli_threshold'] is not None}
                    for t in thresholds:ax.axvline(t,color='#8a8983',linestyle='--');ax.axhline(t,color='#8a8983',linestyle='--')
                if not plotted:_empty(ax,'No recorded values for this panel.')
            if not ops:_empty(axes[0],'No semantic measurements saved for this case yet.')
            fig.supxlabel('Requested rewording strength' if name=='distance' else r'$P_{\mathrm{entail}}(\mathrm{original}\Rightarrow\mathrm{reworded})$',y=-.02,parse_math=name=='nli')
            fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.5,-.08),ncol=2,frameon=False);fig.tight_layout();save(fig,name)
        fig,ax=plt.subplots(figsize=(11,max(3,1+len(ops)*1.1)));_style(ax)
        if rows:
            reasons=list(dict.fromkeys(r['reject_reason'] for r in rows));left=np.zeros(len(ops))
            for reason in reasons:
                values=[sum(r['reject_reason']==reason for r in rows if r['operator']==op) for op in ops]
                totals=[sum(r['operator']==op for r in rows) for op in ops];widths=[v/n for v,n in zip(values,totals)]
                label,color=REASONS.get(reason,(f'Rejected: {reason}','#888888'));ax.barh(range(len(ops)),widths,left=left,color=color,edgecolor='white',linewidth=2,label=label)
                for j,(w,n) in enumerate(zip(widths,values)):
                    if w>.025:ax.text(left[j]+w/2,j,str(n),ha='center',va='center',color='white' if color in ['green','#6652da','#e74747'] else 'black')
                left+=widths
            ax.set_yticks(range(len(ops)),[f"{LABELS.get(op,op)}\n(n = {sum(r['operator']==op for r in rows)})" for op in ops]);ax.invert_yaxis();ax.set_xlim(0,1);ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('Share of candidate rewordings (bar labels: counts)');ax.legend(loc='upper center',bbox_to_anchor=(.5,-.28),ncol=2,frameon=False)
        else:_empty(ax,'No acceptance decisions saved for this case yet.')
        save(fig,'rejections')
        fig,ax=plt.subplots(figsize=(6,6));_style(ax)
        controls=[r for r in rows if r['accepted'] and r['d_emb'] is not None and r['noise_d_emb'] is not None and r['d_emb']>0 and r['noise_d_emb']>0]
        if controls:
            for op in ops:
                group=[r for r in controls if r['operator']==op]
                if group:ax.scatter([r['d_emb'] for r in group],[r['noise_d_emb'] for r in group],color=colors[op],edgecolors='white',label=f'{LABELS.get(op,op)} (n = {len(group)})')
            lo=min(min(r['d_emb'],r['noise_d_emb']) for r in controls)*.8;hi=max(max(r['d_emb'],r['noise_d_emb']) for r in controls)*1.2
            ax.plot([lo,hi],[lo,hi],'--',color='#8a8983',label='Equal distance');ax.set_xscale('log');ax.set_yscale('log');ax.grid(axis='x',color='#e3e2dd');ax.set_xlabel(r'$d_{\mathrm{emb}}$ of accepted rewording',parse_math=True);ax.set_ylabel(r'$d_{\mathrm{emb}}$ of matched noise control',parse_math=True);ax.legend(frameon=False)
            for tick in ax.get_xticklabels()+ax.get_yticklabels():tick.set_parse_math(True)
        else:_empty(ax,'No matched noise controls were recorded.\nThis run tested wording substitutions only.')
        save(fig,'noise_match')
        # Diversify examples across facts, operators and outcomes instead of taking eight copies of one fact.
        examples=[];seen=set()
        for r in rows:
            identity=(r['factId'],r['operator'],r['accepted'])
            if identity not in seen:examples.append(r);seen.add(identity)
            if len(examples)>=6:break
        blocks=[]
        for r in examples:
            original=textwrap.wrap(r['original'],57);new=textwrap.wrap(r['text'],57);blocks.append((r,original,new,max(len(original),len(new))))
        def heading_for(r):
            status='accepted' if r['accepted'] else 'rejected: '+str(r['reject_reason'])
            return f"{LABELS.get(r['operator'],r['operator'])}, {r['level']} — {r['source']} ({status})"
        height=max(3,.6+sum(.24*len(textwrap.wrap(heading_for(r),115))+.1+n*.24+.65 for r,_,_,n in blocks));fig,ax=plt.subplots(figsize=(12,height));ax.axis('off');ax.set_xlim(0,1);ax.set_ylim(0,height)
        y=height-.3
        for x,title in [(0,'Original sentence'),(.43,'Reworded sentence'),(.85,'cos'),(.91,'fwd'),(.97,'bwd')]:ax.text(x,y,title,weight='bold',va='top',ha='left' if x<.8 else 'center')
        ax.plot([0,1],[y-.25,y-.25],color='#555',lw=1);y-=.65
        for r,original,new,n in blocks:
            status='accepted' if r['accepted'] else 'rejected: '+str(r['reject_reason'])
            heading=heading_for(r)
            for line in textwrap.wrap(heading,115):ax.text(0,y,line,color=colors[r['operator']],weight='bold',va='top');y-=.24
            y-=.1;ax.text(.01,y,'\n'.join(original),va='top');ax.text(.41,y,'→',va='top',color='#888');ax.text(.43,y,'\n'.join(new),va='top')
            for x,key in [(.85,'cos'),(.91,'nli_fwd'),(.97,'nli_bwd')]:ax.text(x,y,f'{r[key]:.2f}' if r[key] is not None else '—',ha='center',va='top',family='monospace')
            y-=n*.24+.65
        if not examples:_empty(ax,'No measured sentence pairs saved for this case yet.')
        save(fig,'sentence_pairs')
    fields=['id','factId','operator','level','accepted','reject_reason','cos','d_emb','nli_fwd','nli_bwd','noise_d_emb','nli_threshold','source','original','text']
    with (target/'measurements.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows({k:r.get(k) for k in fields} for r in rows)
