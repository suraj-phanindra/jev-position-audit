"""Standalone descriptive pilot figure, explicitly excluded from confirmatory evidence."""
import argparse
import json
from pathlib import Path


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report');parser.add_argument('output_prefix')
    args=parser.parse_args()
    Path(args.output_prefix).parent.mkdir(parents=True,exist_ok=True)
    report=json.loads(Path(args.report).read_text())
    sources=['MTBench','HANNA','SummEval'];kinds=['noul','choice','score']
    labels=['P(strictly better)','Preference probability','Normalized rubric coordinate']
    fig,axes=plt.subplots(3,3,figsize=(12,9),sharex=True)
    for row,kind in enumerate(kinds):
        for col,source in enumerate(sources):
            ax=axes[row,col]
            cells=sorted([c for c in report['contrasts'] if c['axis']=='state_order'
                          and c['kind']==kind and c['source']==source],key=lambda c:c['gap_bin'])
            for c in cells:
                ax.plot(c['gap_bin'],c['mean'],'o',color='#245b84')
                if 'ci95' in c:
                    lo,hi=c['ci95'];ax.vlines(c['gap_bin'],lo,hi,color='#245b84',linewidth=1.5)
                ax.annotate('n='+str(c['tasks']),(c['gap_bin'],c['mean']),xytext=(4,6),textcoords='offset points',fontsize=8)
            ax.axhline(0,color='#777777',linewidth=.8)
            ax.set_xticks(range(5),['copy','1','2','3','4'])
            ax.spines[['top','right']].set_visible(False)
            if row==0:ax.set_title(source)
            if col==0:ax.set_ylabel(labels[row]+'\nfirst minus second')
            if row==2:ax.set_xlabel('Source-specific external gap bin')
    fig.suptitle('Jev pilot only: state-order contrasts',fontsize=16)
    fig.text(.5,.02,f"{report.get('task_clusters','Unspecified')} task clusters; n labels count tasks per cell. Bars: unadjusted 95% task bootstrap intervals.\n"
             'One-task cells have no interval. Rating gaps and preference margins are different scales.',
             ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.06,1,.95])
    for suffix in ('.png','.svg'):
        path=Path(args.output_prefix+suffix)
        if path.exists():raise ValueError('Refusing to overwrite figure')
        fig.savefig(path,dpi=180)
    print('Saved PNG and SVG pilot figures')

if __name__=='__main__':main()
