import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams["font.family"]="DejaVu Sans"
fig,ax=plt.subplots(figsize=(7.2,3.6));ax.set_xlim(0,100);ax.set_ylim(0,52);ax.axis("off")
def band(y,h,c,label):
    ax.add_patch(FancyBboxPatch((1,y),98,h,boxstyle="round,pad=0,rounding_size=1",fc=c,ec="#999",lw=0.8))
    ax.text(2.5,y+h-2.2,label,fontsize=8,style="italic",color="#444",va="center")
def box(x,y,w,h,t,bold=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0,rounding_size=0.8",fc="#d8e8f5",ec="#1f6fa8",lw=1.1))
    ax.text(x+w/2,y+h/2,t,ha="center",va="center",fontsize=8.5,weight="bold" if bold else "normal")
def arr(x1,y1,x2,y2,both=False):
    ax.annotate("",xy=(x2,y2),xytext=(x1,y1),arrowprops=dict(arrowstyle="<|-|>" if both else "-|>",color="#333",lw=1,shrinkA=0,shrinkB=0))
band(39,12,"#eaf5ee","User / workflow specification");band(20.5,17,"#eaf1fa","LightComm orchestration layer");band(1,18,"#fdf7e6","")
ax.text(2.5,2.6,"LLM serving endpoints (hosted NVIDIA NIM endpoints in this study)",fontsize=8,style="italic",color="#444",va="center")
box(36,40.5,28,7,"Task input\n(workflow DAG G)",True)
box(4,22,26,10,"Action-state\ncompressor  φ");box(37,22,26,10,"Tier router\nρ(t(v))");box(70,22,26,10,"DAG scheduler σ\n(concurrency K)")
box(4,5,26,11,"Large tier (120B-class)\nplan / synthesize / final");box(37,5,26,11,"Small tier (30B-class)\nretrieve / classify / edit");box(70,5,26,11,"Parallel branch\nexecution\n(independent steps)")
arr(50,40.5,50,32);arr(40,40.5,20,32);arr(60,40.5,80,32)
arr(30,27,37,27,True);arr(63,27,70,27,True)
ax.text(33.5,23.3,"records",ha="center",fontsize=7,color="#1f6fa8")
ax.text(66.5,23.3,"tiers",ha="center",fontsize=7,color="#1f6fa8")
arr(46,22,17,16);arr(54,22,50,16);arr(83,22,83,16)
fig.tight_layout(pad=0.2);import os; os.makedirs("results/figures",exist_ok=True); fig.savefig("results/figures/fig1_architecture.pdf"); fig.savefig("results/figures/fig1_architecture.png",dpi=220)
