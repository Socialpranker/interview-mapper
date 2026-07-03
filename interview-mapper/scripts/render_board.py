#!/usr/bin/env python3
"""
render_board.py — автономный HTML-борд инсайтов из provenance.json (или scored.json).

Один самодостаточный .html: карточки инсайтов с фильтром по статусу/роли, каждое доказательство
с интервью/строкой и пометкой verified/support. Ничего не грузит из сети — данные встроены.

CLI: python render_board.py provenance.json [--out board.html] [--title "Инсайты: Музей"]
"""
import argparse, json, html

def get_clusters(data):
    if "provenance" in data:
        return data["provenance"]
    return data.get("clusters", [])

TPL = """<!doctype html><html lang=ru><meta charset=utf-8>
<title>{title}</title>
<style>
:root{{--bg:#0f1720;--card:#182533;--mut:#8aa0b4;--tx:#e7eef5;--in:#3fb950;--wl:#e3b341;--wk:#6e7681;--ten:#f778ba}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
header{{padding:20px 24px;border-bottom:1px solid #223}}h1{{margin:0 0 4px;font-size:20px}}
.sub{{color:var(--mut);font-size:13px}}
.bar{{padding:12px 24px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #223}}
.bar button{{background:var(--card);color:var(--tx);border:1px solid #2a3a4a;border-radius:16px;padding:5px 12px;cursor:pointer;font-size:13px}}
.bar button.on{{background:#243447;border-color:#3d5a7a}}
.wrap{{padding:20px 24px;display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(340px,1fr))}}
.card{{background:var(--card);border:1px solid #223;border-left:4px solid var(--wk);border-radius:10px;padding:14px 16px}}
.card.insight{{border-left-color:var(--in)}}.card.watchlist{{border-left-color:var(--wl)}}
.tag{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;background:#22303f;color:var(--mut);margin:0 4px 4px 0}}
.tag.ten{{background:#3a2233;color:var(--ten)}}
.title{{font-weight:600;margin:2px 0 8px}}
.meta{{color:var(--mut);font-size:12px;margin-bottom:8px}}
.ev{{border-top:1px solid #223;padding:7px 0;font-size:13px}}
.q{{color:#cfe0f0}}.who{{color:var(--mut);font-size:12px}}
.bad{{color:#f78;font-size:11px}}.ok{{color:var(--in);font-size:11px}}
</style>
<header><h1>{title}</h1><div class=sub>{sub}</div></header>
<div class=bar id=filters></div>
<div class=wrap id=wrap></div>
<script>
const DATA={data};
const wrap=document.getElementById('wrap'),filters=document.getElementById('filters');
let statusF='all',roleF='all';
const roles=[...new Set(DATA.flatMap(c=>c.roles||[]))];
function mk(el,cls,txt){{const e=document.createElement(el);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}}
function btn(label,active,fn){{const b=mk('button',active?'on':'',label);b.onclick=fn;return b;}}
function renderFilters(){{filters.innerHTML='';
 ['all','insight','watchlist','weak'].forEach(s=>filters.append(btn(s,statusF===s,()=>{{statusF=s;draw();}})));
 filters.append(mk('span','',' · '));
 ['all',...roles].forEach(r=>filters.append(btn(r,roleF===r,()=>{{roleF=r;draw();}})));
}}
function draw(){{renderFilters();wrap.innerHTML='';
 DATA.filter(c=>(statusF==='all'||c.status===statusF)&&(roleF==='all'||(c.roles||[]).includes(roleF)))
 .forEach(c=>{{
  const card=mk('div','card '+c.status);
  card.append(mk('div','title',c.title||c.cluster));
  const tags=mk('div');
  tags.append(mk('span','tag',c.status));
  tags.append(mk('span','tag','распр: '+(c.prevalence||'')));
  if(c.severity!=null)tags.append(mk('span','tag','крит: '+c.severity));
  if(c.triangulated)tags.append(mk('span','tag','триангулирован'));
  if(c.tension)tags.append(mk('span','tag ten','НАПРЯЖЕНИЕ'));
  card.append(tags);
  card.append(mk('div','meta','роли: '+((c.roles||[]).join(', '))));
  (c.evidence||[]).forEach(e=>{{
   const ev=mk('div','ev');
   ev.append(mk('div','q','«'+(e.quote||'')+'»'));
   const w=mk('div','who',(e.interview||'?')+(e.role?' · '+e.role:'')+(e.line?' · L'+e.line:''));
   if(e.verified===false)w.append(mk('span','bad',' ⚠ не verified'));
   if(e.support==='no')w.append(mk('span','bad',' ⚠ не поддерживает'));
   if(e.support==='yes')w.append(mk('span','ok',' ⊨'));
   ev.append(w);card.append(ev);
  }});
  wrap.append(card);
 }});
 if(!wrap.children.length)wrap.append(mk('div','sub','Ничего под фильтр.'));
}}
draw();
</script></html>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default="board.html")
    ap.add_argument("--title", default="Инсайты из интервью")
    a = ap.parse_args()
    data = json.load(open(a.data, encoding="utf-8"))
    clusters = get_clusters(data)
    n_iv = (data.get("summary", {}).get("insights", {}) or {}).get("total_interviews", "?")
    sub = f"кластеров: {len(clusters)} · интервью: {n_iv} · зелёный=инсайт, жёлтый=watchlist, серый=weak"
    htmlout = TPL.format(title=html.escape(a.title), sub=html.escape(str(sub)),
                         data=json.dumps(clusters, ensure_ascii=False))
    open(a.out, "w", encoding="utf-8").write(htmlout)
    print(f"Борд: {len(clusters)} карточек → {a.out}")

if __name__ == "__main__":
    main()
