"""Render report.html: weekly usage and estimated cost by model and project (no external deps)."""

import json
from collections import defaultdict
from datetime import datetime

METRICS = ["messages", "input", "output", "cache_write", "cache_write_1h", "cache_read"]
MAX_SERIES = 4  # models and projects each get 4 hues, disjoint so colors never imply a link; the rest fold into "Other"

# Anthropic API list prices, $ per million tokens: (input, output, cache read).
# Cache writes bill at 1.25x input (5-minute TTL) or 2x input (1-hour TTL).
# Source: claude-api skill model table, cached 2026-09-25. Update as prices change.
PRICES = {
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-opus-4-7": (5.00, 25.00, 0.50),
    "claude-opus-4-6": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}


def price_for(model):
    # Longest prefix wins, so "claude-opus-5-5" isn't priced as "claude-opus-5"
    # and dated IDs like "claude-haiku-4-5-20251001" still match.
    matches = [k for k in PRICES if model == k or model.startswith(k + "-")]
    return PRICES[max(matches, key=len)] if matches else None


def cost(model, m):
    p = price_for(model)
    if p is None:
        return 0.0
    i, o, cr = p
    cw5 = m["cache_write"] - m["cache_write_1h"]
    return (m["input"] * i + m["output"] * o + cw5 * 1.25 * i
            + m["cache_write_1h"] * 2 * i + m["cache_read"] * cr) / 1e6


def total(m):
    return m["input"] + m["output"] + m["cache_write"] + m["cache_read"]


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Usage Report</title>
<style>
:root{--bg:#fcfcfb;--card:#fff;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--grid:#e8e7e3;--line:#dddcd7;--accent:#2a78d6;
--m1:#2a78d6;--m2:#eda100;--m3:#e87ba4;--m4:#008300;--mo:#a8a7a2;--p1:#eb6834;--p2:#1baf7a;--p3:#4a3aa7;--p4:#e34948;--po:#a8a7a2}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1a1a19;--card:#222220;--ink:#fff;--ink2:#c3c2b7;--accent:#3987e5;
--muted:#8f8e88;--grid:#33332f;--line:#3a3a36;--m1:#3987e5;--m2:#c98500;--m3:#d55181;--m4:#008300;--mo:#6b6a66;--p1:#d95926;--p2:#199e70;--p3:#9085e9;--p4:#e66767;--po:#6b6a66}}
:root[data-theme="dark"]{--bg:#1a1a19;--card:#222220;--ink:#fff;--ink2:#c3c2b7;--muted:#8f8e88;--grid:#33332f;--line:#3a3a36;--accent:#3987e5;
--m1:#3987e5;--m2:#c98500;--m3:#d55181;--m4:#008300;--mo:#6b6a66;--p1:#d95926;--p2:#199e70;--p3:#9085e9;--p4:#e66767;--po:#6b6a66}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:28px 16px 48px}h1{font-size:28px;margin:0 0 4px}h2{font-size:18px;margin:0 0 2px}
h3{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:26px 0 10px}
.sub{color:var(--ink2);margin:0 0 20px}.note{color:var(--muted);font-size:14px;margin:0 0 12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:16px}
.tile,.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile b{display:block;font-size:30px;font-variant-numeric:tabular-nums}.tile span{color:var(--ink2);font-size:14px}
.card{margin-bottom:16px}.legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin:6px 0 12px;font-size:14px;color:var(--ink2)}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-1px}
svg{display:block;width:100%;height:auto;overflow:visible}svg text{fill:var(--ink2);font-size:13px}
.mark{cursor:default}.mark:hover{opacity:.8}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;
font-size:14px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;z-index:9;max-width:260px}#tip b{display:block;margin-bottom:2px}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
th,td{padding:5px 8px;border-bottom:1px solid var(--grid);text-align:right}th:first-child,td:first-child,.l{text-align:left}
th{color:var(--ink2);font-weight:600}details{margin-top:10px}summary{cursor:pointer;color:var(--ink2);font-size:14px}
.controls{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
select{font:inherit;padding:4px 8px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:7px;overflow:hidden}
.seg button{font:inherit;font-size:15px;border:0;background:var(--card);color:var(--ink2);padding:4px 12px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--accent);color:#fff}
.foot{color:var(--muted);font-size:14px;margin-top:24px}
</style></head><body><main>
<h1>Claude Code usage</h1>
<p class="sub" id="sub"></p>
<div class="controls">
 <label>Week <select id="wk"></select></label>
 <span class="seg" role="group" aria-label="Measure"><button data-m="cost" aria-pressed="true">Est. cost</button><button data-m="tokens" aria-pressed="false">Tokens</button></span>
</div>
<div class="tiles" id="tiles"></div>
<h3>Selected week</h3>
<div class="card"><h2 id="h1">By project, split by model</h2><p class="note" id="n1"></p>
<div class="legend" id="lg1"></div><div id="c1"></div>
<details><summary>Table</summary><div id="t1"></div></details></div>
<div class="card"><h2 id="h2">By model</h2><p class="note" id="n2"></p><div id="c2"></div>
<details><summary>Table</summary><div id="t2"></div></details></div>
<h3>Every week</h3>
<div class="card"><h2>Estimated cost per week</h2><p class="note" id="n0"></p>
<div class="tiles" id="tiles0"></div><div id="c0"></div>
<details><summary>Table</summary><div id="t0"></div></details></div>
<div class="card"><h2 id="h3">Weekly total by project</h2><p class="note">Allowance weeks, Thursday 15:00 to Thursday 15:00 local. Projects beyond the top four are grouped as Other (hatched).</p>
<div class="legend" id="lg3"></div><div id="c3"></div>
<details><summary>Table</summary><div id="t3"></div></details></div>
<div class="card"><h2 id="h4">Weekly total by model</h2><p class="note">Allowance weeks, Thursday 15:00 to Thursday 15:00 local. Models beyond the top four are grouped as Other.</p>
<div class="legend" id="lg4"></div><div id="c4"></div>
<details><summary>Table</summary><div id="t4"></div></details></div>
<p class="foot" id="foot"></p>
</main><div id="tip"></div>
<script>
const D = __DATA__;
const NS="http://www.w3.org/2000/svg", tip=document.getElementById("tip");
let M="cost";
const fmtN=n=>n>=1e9?(n/1e9).toFixed(1)+"B":n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?(n/1e3).toFixed(1)+"K":String(Math.round(n));
const fmt$=n=>n>=1000?"$"+(n/1000).toFixed(1)+"K":n>=100?"$"+n.toFixed(0):"$"+n.toFixed(2);
const tot=r=>r.input+r.output+r.cache_write+r.cache_read;
const val=r=>M==="cost"?r.cost:tot(r), fv=v=>M==="cost"?fmt$(v):fmtN(v), unit=()=>M==="cost"?"estimated cost":"total tokens";
const add=(a,r)=>{for(const k in r)a[k]=(a[k]||0)+r[k];return a};
const sum=rs=>rs.reduce(add,{messages:0,input:0,output:0,cache_write:0,cache_write_1h:0,cache_read:0,cost:0});
const colM=m=>m==="Other"?"var(--mo)":`var(--m${D.models.indexOf(m)+1})`, colP=p=>p==="Other"?"url(#hatch)":`var(--p${D.projects.indexOf(p)+1})`;
const swatch=c=>c==="url(#hatch)"?"repeating-linear-gradient(45deg,var(--po) 0 2px,transparent 2px 4px)":c;
const pkey=p=>D.projects.includes(p)?p:"Other";
function hatch(s){const p=el("pattern",{id:"hatch",width:5,height:5,patternUnits:"userSpaceOnUse",patternTransform:"rotate(45)"},el("defs",{},s));
 el("rect",{width:5,height:5,fill:"var(--card)"},p);el("rect",{width:2.5,height:5,fill:"var(--po)"},p)}
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e}
function hover(e,html){e.classList.add("mark");e.addEventListener("mousemove",ev=>{tip.innerHTML=html;tip.style.display="block";
 const x=Math.min(ev.clientX+14,innerWidth-tip.offsetWidth-8);tip.style.left=x+"px";tip.style.top=(ev.clientY+14)+"px"});
 e.addEventListener("mouseleave",()=>tip.style.display="none")}
const detail=r=>`${fmt$(r.cost)} est. · ${fmtN(tot(r))} tokens<br>${r.messages.toLocaleString()} msgs · ${fmtN(r.output)} output`;
function legend(id,keys,col){document.getElementById(id).innerHTML=keys.map(k=>`<span><i style="background:${swatch(col(k))}"></i>${k}</span>`).join("")}
function ticks(max,k=5){const s=Math.pow(10,Math.floor(Math.log10(max||1)));const st=[1,2,2.5,5,10].map(x=>x*s).find(x=>max/x<=k);
 const out=[];for(let v=0;v<=max+1e-9;v+=st)out.push(v);if(out[out.length-1]<max)out.push(out[out.length-1]+st);return out}
function table(id,head,rows){document.getElementById(id).innerHTML="<table><tr>"+head.map(h=>`<th>${h}</th>`).join("")+"</tr>"+
 rows.map(r=>"<tr>"+r.map((c,i)=>`<td${i<2&&typeof c==="string"&&!/^[$\\d]/.test(c)?' class="l"':""}>${c}</td>`).join("")+"</tr>").join("")+"</table>"}
const cells=r=>[r.messages.toLocaleString(),fmtN(r.input),fmtN(r.output),fmtN(r.cache_write),fmtN(r.cache_read),fmtN(tot(r)),fmt$(r.cost)];
const HEAD=["Messages","Input","Output","Cache write","Cache read","Total tokens","Est. cost"];
// Horizontal stacked bars: rows=[{name, parts:[{key,r}]}]
function hbars(id,rows,col){const host=document.getElementById(id);host.innerHTML="";
 const W=Math.max(host.clientWidth,300),L=Math.min(250,W*.36),R=70,bh=24,gap=14,T=6,H=T+rows.length*(bh+gap)+22;
 const max=Math.max(...rows.map(r=>r.parts.reduce((a,p)=>a+val(p.r),0)),1e-9),tk=ticks(max,Math.max(2,Math.floor((W-L-R)/95))),X=v=>L+(W-L-R)*v/tk[tk.length-1];
 const s=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img"},host);
 tk.forEach(v=>{el("line",{x1:X(v),x2:X(v),y1:T,y2:H-20,stroke:"var(--grid)"},s);el("text",{x:X(v),y:H-6,"text-anchor":"middle"},s).textContent=fv(v)});
 rows.forEach((r,i)=>{const y=T+i*(bh+gap);let x=L,acc=0;const nc=Math.floor(L/8);
  el("text",{x:L-8,y:y+bh/2+4,"text-anchor":"end",style:"fill:var(--ink)"},s).textContent=r.name.length>nc?r.name.slice(0,nc-1)+"…":r.name;
  const parts=r.parts.filter(p=>val(p.r)>0);
  parts.forEach((p,j)=>{const w=X(val(p.r))-L,last=j===parts.length-1;
   const rect=el(last?"path":"rect",last?{d:`M${x},${y}h${Math.max(w-4,0)}q4,0 4,4v${bh-8}q0,4 -4,4h${-Math.max(w-4,0)}Z`,fill:col(p.key)}:
    {x,y,width:Math.max(w-2,0.5),height:bh,fill:col(p.key)},s);
   hover(rect,`<b>${r.name}</b>${p.key}<br>${detail(p.r)}`);x+=w;acc+=val(p.r)});
  el("text",{x:x+6,y:y+bh/2+4,style:"fill:var(--ink)"},s).textContent=fv(acc)})}
// Stacked columns per week: parts(w) -> {key: r}
function columns(id,keys,col,parts){const host=document.getElementById(id);host.innerHTML="";
 const W=Math.max(host.clientWidth,300),L=62,T=10,B=40,H=300,wks=D.weeks.slice().reverse(),n=wks.length,bw=Math.min(46,(W-L-10)/n-6);
 const P=wks.map(parts),max=Math.max(...P.map(p=>Object.values(p).reduce((a,r)=>a+val(r),0)),1e-9);
 const tk=ticks(max),Y=v=>H-B-(H-B-T)*v/tk[tk.length-1];
 const s=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img"},host);hatch(s);
 tk.forEach(v=>{el("line",{x1:L,x2:W,y1:Y(v),y2:Y(v),stroke:"var(--grid)"},s);el("text",{x:L-6,y:Y(v)+4,"text-anchor":"end"},s).textContent=fv(v)});
 wks.forEach((w,i)=>{const cx=L+(i+.5)*(W-L)/n,x=cx-bw/2;let base=0;
  const ps=keys.map(k=>[k,P[i][k]]).filter(p=>p[1]&&val(p[1])>0);
  ps.forEach(([k,r],j)=>{const v=val(r),y0=Y(base),y1=Y(base+v),last=j===ps.length-1,h=Math.max(y0-y1-(j?2:0),0.5);
   const rect=el(last&&h>4?"path":"rect",last&&h>4?{d:`M${x},${y0-(j?2:0)}V${y1+4}q0,-4 4,-4h${bw-8}q4,0 4,4V${y0-(j?2:0)}Z`,fill:col(k)}:
    {x,y:y1,width:bw,height:h,fill:col(k)},s);
   hover(rect,`<b>Week of ${w.week}</b>${k}<br>${detail(r)}`);base+=v});
  if(i%Math.ceil(n/Math.floor(W/80))===0||i===n-1)el("text",{x:cx,y:H-B+16,"text-anchor":"middle"},s).textContent=w.week.slice(5)})}
function byProject(w){const o={};for(const[p,ms]of Object.entries(w.projects)){const k=pkey(p);o[k]=add(o[k]||sum([]),sum(Object.values(ms)))}return o}
function perWeek(){const host=document.getElementById("c0");host.innerHTML="";
 const wks=D.weeks.slice().reverse(),costs=wks.map(w=>sum(Object.values(w.models)).cost),n=wks.length;
 const done=D.weeks.filter(w=>!w.current).map(w=>sum(Object.values(w.models)).cost),avg=done.reduce((a,b)=>a+b,0)/(done.length||1);
 const cur=D.weeks.find(w=>w.current),last=D.weeks.find(w=>!w.current);
 document.getElementById("n0").textContent=`API list-price equivalent per allowance week. The dashed line is the average of ${done.length} completed weeks.`;
 document.getElementById("tiles0").innerHTML=[["This week so far",cur?fmt$(sum(Object.values(cur.models)).cost):"–"],
  [`Last week (${last?last.week.slice(5):"–"})`,last?fmt$(sum(Object.values(last.models)).cost):"–"],["Average per week",fmt$(avg)],
  ["Highest week",fmt$(Math.max(...done,0))]].map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join("");
 const W=Math.max(host.clientWidth,300),L=62,T=18,B=40,H=260,bw=Math.min(46,(W-L-10)/n-6);
 const tk=ticks(Math.max(...costs,1e-9)),Y=v=>H-B-(H-B-T)*v/tk[tk.length-1];
 const s=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img"},host);hatch(s);
 tk.forEach(v=>{el("line",{x1:L,x2:W,y1:Y(v),y2:Y(v),stroke:"var(--grid)"},s);el("text",{x:L-6,y:Y(v)+4,"text-anchor":"end"},s).textContent=fmt$(v)});
 const showAll=bw>=34;
 wks.forEach((w,i)=>{const c=costs[i],cx=L+(i+.5)*(W-L)/n,x=cx-bw/2,y=Y(c),h=Y(0)-y;
  const bar=el("path",{d:h>4?`M${x},${Y(0)}V${y+4}q0,-4 4,-4h${bw-8}q4,0 4,4V${Y(0)}Z`:`M${x},${Y(0)}v${-Math.max(h,.5)}h${bw}v${Math.max(h,.5)}Z`,
   fill:"var(--accent)",opacity:w.current?.55:1},s);
  hover(bar,`<b>Week of ${w.week}${w.current?" (in progress)":""}</b>${detail(sum(Object.values(w.models)))}`);
  if(showAll||c===Math.max(...costs)||w.current)el("text",{x:cx,y:y-5,"text-anchor":"middle",style:"fill:var(--ink)"},s).textContent=fmt$(c);
  if(i%Math.ceil(n/Math.floor(W/80))===0||i===n-1)el("text",{x:cx,y:H-B+16,"text-anchor":"middle"},s).textContent=w.week.slice(5)});
 if(done.length){el("line",{x1:L,x2:W,y1:Y(avg),y2:Y(avg),stroke:"var(--ink2)","stroke-dasharray":"4 4"},s);
  el("text",{x:L+4,y:Y(avg)-5,"text-anchor":"start",style:"fill:var(--ink2)"},s).textContent=`avg ${fmt$(avg)}`}
 table("t0",["Week of","Messages","Total tokens","Est. cost"],D.weeks.map(w=>{const r=sum(Object.values(w.models));
  return[w.week+(w.current?" (in progress)":""),r.messages.toLocaleString(),fmtN(tot(r)),fmt$(r.cost)]}))}
function history(){
 perWeek();
 columns("c3",D.projects,colP,byProject);columns("c4",D.models,colM,w=>w.models);
 document.getElementById("h3").textContent=`Weekly ${M==="cost"?"estimated cost":"total tokens"} by project`;
 document.getElementById("h4").textContent=`Weekly ${M==="cost"?"estimated cost":"total tokens"} by model`;
 table("t3",["Week of","Project"].concat(HEAD),D.weeks.flatMap(w=>{const bp=byProject(w);
  return D.projects.filter(p=>bp[p]).map(p=>[w.week,p].concat(cells(bp[p])))}));
 table("t4",["Week of","Model"].concat(HEAD),D.weeks.flatMap(w=>D.models.filter(m=>w.models[m]).map(m=>[w.week,m].concat(cells(w.models[m])))))}
function render(){const wk=document.getElementById("wk").value,w=D.weeks.find(x=>x.week===wk);
 const all=sum(Object.values(w.models));
 document.getElementById("tiles").innerHTML=[["Estimated cost",fmt$(all.cost)],["Total tokens",fmtN(tot(all))],["Output tokens",fmtN(all.output)],
  ["Messages",all.messages.toLocaleString()],["Projects",Object.keys(w.projects).length]].map(([k,v])=>`<div class="tile"><span>${k}</span><b>${v}</b></div>`).join("");
 const projs=Object.entries(w.projects).map(([name,ms])=>({name,ms,t:sum(Object.values(ms))})).sort((a,b)=>val(b.t)-val(a.t));
 document.getElementById("h1").textContent=`${M==="cost"?"Estimated cost":"Tokens"} by project, split by model`;
 document.getElementById("h2").textContent=`${M==="cost"?"Estimated cost":"Tokens"} by model`;
 const note=M==="cost"?"API list-price equivalent, not what a subscription bills.":"Total tokens = input + output + cache write + cache read.";
 document.getElementById("n1").textContent=note;document.getElementById("n2").textContent=note;
 legend("lg1",D.models.filter(m=>projs.some(p=>p.ms[m])),colM);
 hbars("c1",projs.map(p=>({name:p.name,parts:D.models.filter(m=>p.ms[m]).map(m=>({key:m,r:p.ms[m]}))})),colM);
 table("t1",["Project","Model"].concat(HEAD),projs.flatMap(p=>D.models.filter(m=>p.ms[m]).map(m=>[p.name,m].concat(cells(p.ms[m])))));
 const ms=D.models.filter(m=>w.models[m]).sort((a,b)=>val(w.models[b])-val(w.models[a]));
 hbars("c2",ms.map(m=>({name:m,parts:[{key:m,r:w.models[m]}]})),colM);
 table("t2",["Model"].concat(HEAD),ms.map(m=>[m].concat(cells(w.models[m]))))}
document.getElementById("sub").textContent=`Generated ${D.generated}. Weeks start Thursday 15:00 local, matching the allowance reset.`;
document.getElementById("foot").textContent="Estimated cost uses Anthropic API list prices per million tokens: input, output, cache reads, and cache writes at 1.25x input (5-minute) or 2x input (1-hour). It shows what this usage would cost on the API, not your plan's charges."
 +(D.unpriced.length?` No price on file for: ${D.unpriced.join(", ")} (counted as $0).`:"");
const sel=document.getElementById("wk");sel.innerHTML=D.weeks.map(w=>`<option value="${w.week}">Week of ${w.week}${w.current?" (current)":""}</option>`).join("");
sel.onchange=render;legend("lg3",D.projects,colP);legend("lg4",D.models,colM);
document.querySelectorAll(".seg button").forEach(b=>b.onclick=()=>{M=b.dataset.m;
 document.querySelectorAll(".seg button").forEach(x=>x.setAttribute("aria-pressed",x===b));history();render()});
history();render();
let rz;addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(()=>{history();render()},150)});
</script></body></html>
"""


def top_keys(totals):
    ranked = sorted(totals, key=lambda k: -totals[k])
    return ranked[:MAX_SERIES] + (["Other"] if len(ranked) > MAX_SERIES else [])


def write_report(daily, path, current_week):
    model_totals, project_totals = defaultdict(int), defaultdict(int)
    for (_, _, project, model), m in daily.items():
        model_totals[model] += total(m)
        project_totals[project] += total(m)
    models, projects = top_keys(model_totals), top_keys(project_totals)
    label = lambda model: model if model in models else "Other"

    empty = lambda: dict.fromkeys(METRICS + ["cost"], 0)
    weeks = defaultdict(lambda: {"models": defaultdict(empty),
                                 "projects": defaultdict(lambda: defaultdict(empty))})
    for (_, wk, project, model), m in daily.items():
        row = dict(m, cost=cost(model, m))
        for target in (weeks[wk]["models"][label(model)], weeks[wk]["projects"][project][label(model)]):
            for k, v in row.items():
                target[k] += v

    data = {
        "generated": f"{datetime.now().astimezone():%Y-%m-%d %H:%M %Z}",
        "models": models,
        "projects": projects,
        "unpriced": sorted(m for m in model_totals if price_for(m) is None),
        "weeks": [{"week": wk, "current": wk == current_week, **w}
                  for wk, w in sorted(weeks.items(), reverse=True)],
    }
    path.write_text(PAGE.replace("__DATA__", json.dumps(data)))
