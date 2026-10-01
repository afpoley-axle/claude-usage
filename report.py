"""Render report.html: weekly usage charts by model and project (no external deps)."""

import json
from collections import defaultdict
from datetime import datetime

METRICS = ["messages", "input", "output", "cache_write", "cache_read"]
MAX_SERIES = 7  # categorical slots; the rest fold into "Other"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Usage Report</title>
<style>
:root{--bg:#fcfcfb;--card:#fff;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--grid:#e8e7e3;--line:#dddcd7;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#4a3aa7;--s8:#a8a7a2}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1a1a19;--card:#222220;--ink:#fff;--ink2:#c3c2b7;
--muted:#8f8e88;--grid:#33332f;--line:#3a3a36;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#6b6a66}}
:root[data-theme="dark"]{--bg:#1a1a19;--card:#222220;--ink:#fff;--ink2:#c3c2b7;--muted:#8f8e88;--grid:#33332f;--line:#3a3a36;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#6b6a66}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:28px 16px 48px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 2px}
.sub{color:var(--ink2);margin:0 0 20px}.note{color:var(--muted);font-size:12px;margin:0 0 12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:16px}
.tile,.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.tile span{color:var(--ink2);font-size:12px}
.card{margin-bottom:16px}.legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin:6px 0 10px;font-size:12px;color:var(--ink2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
svg{display:block;width:100%;height:auto;overflow:visible}svg text{fill:var(--ink2);font-size:11px}
.mark{cursor:default}.mark:hover{opacity:.8}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;
font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;z-index:9;max-width:260px}#tip b{display:block;margin-bottom:2px}
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
th,td{padding:5px 8px;border-bottom:1px solid var(--grid);text-align:right}th:first-child,td:first-child{text-align:left}
th{color:var(--ink2);font-weight:600}details{margin-top:10px}summary{cursor:pointer;color:var(--ink2);font-size:12px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}select{font:inherit;padding:4px 8px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
</style></head><body><main>
<h1>Claude Code usage</h1>
<p class="sub" id="sub"></p>
<div class="row" style="margin-bottom:14px"><label for="wk">Week</label><select id="wk"></select></div>
<div class="tiles" id="tiles"></div>
<div class="card"><h2>Tokens by project, split by model</h2><p class="note">Selected week. Total tokens = input + output + cache write + cache read.</p>
<div class="legend" id="lg1"></div><div id="c1"></div>
<details><summary>Table</summary><div id="t1"></div></details></div>
<div class="card"><h2>Tokens by model</h2><p class="note">Selected week.</p><div id="c2"></div>
<details><summary>Table</summary><div id="t2"></div></details></div>
<div class="card"><h2>Weekly total tokens by model</h2><p class="note">Allowance weeks, Thursday 15:00 to Thursday 15:00 local.</p>
<div class="legend" id="lg3"></div><div id="c3"></div>
<details><summary>Table</summary><div id="t3"></div></details></div>
</main><div id="tip"></div>
<script>
const D = __DATA__;
const NS="http://www.w3.org/2000/svg", tip=document.getElementById("tip");
const fmt=n=>n>=1e9?(n/1e9).toFixed(1)+"B":n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?(n/1e3).toFixed(1)+"K":String(n);
const col=m=>`var(--s${D.models.indexOf(m)+1})`;
const tot=r=>r.input+r.output+r.cache_write+r.cache_read;
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e}
function hover(e,html){e.classList.add("mark");e.addEventListener("mousemove",ev=>{tip.innerHTML=html;tip.style.display="block";
 const x=Math.min(ev.clientX+14,innerWidth-tip.offsetWidth-8);tip.style.left=x+"px";tip.style.top=(ev.clientY+14)+"px"});
 e.addEventListener("mouseleave",()=>tip.style.display="none")}
function legend(id,models){document.getElementById(id).innerHTML=models.map(m=>`<span><i style="background:${col(m)}"></i>${m}</span>`).join("")}
function ticks(max,k=5){const s=Math.pow(10,Math.floor(Math.log10(max||1)));const st=[1,2,2.5,5,10].map(x=>x*s).find(x=>max/x<=k);
 const out=[];for(let v=0;v<=max+1e-9;v+=st)out.push(v);if(out[out.length-1]<max)out.push(out[out.length-1]+st);return out}
function table(id,head,rows){document.getElementById(id).innerHTML="<table><tr>"+head.map(h=>`<th>${h}</th>`).join("")+"</tr>"+
 rows.map(r=>"<tr>"+r.map(c=>`<td>${c}</td>`).join("")+"</tr>").join("")+"</table>"}
// Horizontal stacked bars: rows=[{name, parts:[{model,value,r}]}]
function hbars(id,rows){const host=document.getElementById(id);host.innerHTML="";
 const W=Math.max(host.clientWidth,300),L=Math.min(210,W*.34),R=56,bh=20,gap=12,T=6,H=T+rows.length*(bh+gap)+22;
 const max=Math.max(...rows.map(r=>r.parts.reduce((a,p)=>a+p.value,0)),1),tk=ticks(max,Math.max(2,Math.floor((W-L-R)/80))),X=v=>L+(W-L-R)*v/tk[tk.length-1];
 const s=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img"},host);
 tk.forEach(v=>{el("line",{x1:X(v),x2:X(v),y1:T,y2:H-20,stroke:"var(--grid)"},s);el("text",{x:X(v),y:H-6,"text-anchor":"middle"},s).textContent=fmt(v)});
 rows.forEach((r,i)=>{const y=T+i*(bh+gap);let x=L,sum=0;
  const nc=Math.floor(L/6.6);el("text",{x:L-8,y:y+bh/2+4,"text-anchor":"end",style:"fill:var(--ink)"},s).textContent=r.name.length>nc?r.name.slice(0,nc-1)+"…":r.name;
  r.parts.forEach((p,j)=>{const w=Math.max(X(p.value)-L,0);if(!w)return;const last=j===r.parts.length-1;
   const rect=el("rect",{x,y,width:Math.max(w-(last?0:2),0.5),height:bh,rx:last?4:0,fill:col(p.model)},s);
   hover(rect,`<b>${r.name}</b>${p.model}<br>${fmt(p.value)} tokens · ${p.r.messages.toLocaleString()} msgs<br>output ${fmt(p.r.output)}`);
   x+=w;sum+=p.value});
  el("text",{x:x+6,y:y+bh/2+4,style:"fill:var(--ink)"},s).textContent=fmt(sum)})}
function weekly(){const host=document.getElementById("c3");host.innerHTML="";
 const W=Math.max(host.clientWidth,300),L=50,T=10,B=40,H=300,wks=D.weeks.slice().reverse(),n=wks.length,bw=Math.min(46,(W-L-10)/n-6);
 const max=Math.max(...wks.map(w=>w.total),1),tk=ticks(max),Y=v=>H-B-(H-B-T)*v/tk[tk.length-1];
 const s=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img"},host);
 tk.forEach(v=>{el("line",{x1:L,x2:W,y1:Y(v),y2:Y(v),stroke:"var(--grid)"},s);el("text",{x:L-6,y:Y(v)+4,"text-anchor":"end"},s).textContent=fmt(v)});
 wks.forEach((w,i)=>{const cx=L+(i+.5)*(W-L)/n,x=cx-bw/2;let base=0;
  const parts=D.models.map(m=>[m,w.models[m]]).filter(p=>p[1]);
  parts.forEach(([m,r],j)=>{const v=tot(r),y0=Y(base),y1=Y(base+v),last=j===parts.length-1;
   const rect=el(last?"path":"rect",last?{d:`M${x},${y0-2}V${y1+4}q0,-4 4,-4h${bw-8}q4,0 4,4V${y0-2}Z`,fill:col(m)}:
    {x,y:y1,width:bw,height:Math.max(y0-y1-(j?2:0),0.5),fill:col(m)},s);
   hover(rect,`<b>Week of ${w.week}</b>${m}<br>${fmt(v)} tokens · ${r.messages.toLocaleString()} msgs`);base+=v});
  if(i%Math.ceil(n/Math.floor(W/70))===0||i===n-1)el("text",{x:cx,y:H-B+16,"text-anchor":"middle"},s).textContent=w.week.slice(5)})}
function render(){const wk=document.getElementById("wk").value,w=D.weeks.find(x=>x.week===wk);
 const all=Object.values(w.models).reduce((a,r)=>{for(const k in r)a[k]=(a[k]||0)+r[k];return a},{});
 document.getElementById("tiles").innerHTML=[["Total tokens",fmt(tot(all))],["Output tokens",fmt(all.output)],
  ["Messages",all.messages.toLocaleString()],["Projects",Object.keys(w.projects).length]].map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join("");
 const projs=Object.entries(w.projects).map(([name,ms])=>({name,ms,t:Object.values(ms).reduce((a,r)=>a+tot(r),0)})).sort((a,b)=>b.t-a.t);
 legend("lg1",D.models.filter(m=>projs.some(p=>p.ms[m])));
 hbars("c1",projs.map(p=>({name:p.name,parts:D.models.filter(m=>p.ms[m]).map(m=>({model:m,value:tot(p.ms[m]),r:p.ms[m]}))})));
 table("t1",["Project","Model","Messages","Input","Output","Cache write","Cache read","Total"],projs.flatMap(p=>
  D.models.filter(m=>p.ms[m]).map(m=>{const r=p.ms[m];return[p.name,m,r.messages.toLocaleString(),fmt(r.input),fmt(r.output),fmt(r.cache_write),fmt(r.cache_read),fmt(tot(r))]})));
 const ms=D.models.filter(m=>w.models[m]).sort((a,b)=>tot(w.models[b])-tot(w.models[a]));
 hbars("c2",ms.map(m=>({name:m,parts:[{model:m,value:tot(w.models[m]),r:w.models[m]}]})));
 table("t2",["Model","Messages","Input","Output","Cache write","Cache read","Total"],ms.map(m=>{const r=w.models[m];
  return[m,r.messages.toLocaleString(),fmt(r.input),fmt(r.output),fmt(r.cache_write),fmt(r.cache_read),fmt(tot(r))]}))}
document.getElementById("sub").textContent=`Generated ${D.generated}. Weeks start Thursday 15:00 local, matching the allowance reset.`;
const sel=document.getElementById("wk");sel.innerHTML=D.weeks.map(w=>`<option value="${w.week}">Week of ${w.week}${w.current?" (current)":""}</option>`).join("");
sel.onchange=render;legend("lg3",D.models);weekly();
table("t3",["Week of","Messages","Output","Total"],D.weeks.map(w=>{const a=Object.values(w.models);
 return[w.week,a.reduce((s,r)=>s+r.messages,0).toLocaleString(),fmt(a.reduce((s,r)=>s+r.output,0)),fmt(w.total)]}));
render();
let rz;addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(()=>{weekly();render()},150)});
</script></body></html>
"""


def write_report(daily, path, current_week):
    def total(m):
        return m["input"] + m["output"] + m["cache_write"] + m["cache_read"]

    model_totals = defaultdict(int)
    for (_, _, _, model), m in daily.items():
        model_totals[model] += total(m)
    ranked = sorted(model_totals, key=lambda k: -model_totals[k])
    keep = ranked[:MAX_SERIES]
    label = lambda model: model if model in keep else "Other"

    weeks = defaultdict(lambda: {"models": defaultdict(lambda: dict.fromkeys(METRICS, 0)),
                                 "projects": defaultdict(lambda: defaultdict(lambda: dict.fromkeys(METRICS, 0)))})
    for (_, wk, project, model), m in daily.items():
        w = weeks[wk]
        for k, v in m.items():
            w["models"][label(model)][k] += v
            w["projects"][project][label(model)][k] += v

    data = {
        "generated": f"{datetime.now().astimezone():%Y-%m-%d %H:%M %Z}",
        "models": keep + (["Other"] if len(keep) < len(ranked) else []),
        "weeks": [{"week": wk, "current": wk == current_week,
                   "total": sum(total(m) for m in w["models"].values()),
                   "models": w["models"], "projects": w["projects"]}
                  for wk, w in sorted(weeks.items(), reverse=True)],
    }
    path.write_text(PAGE.replace("__DATA__", json.dumps(data)))
