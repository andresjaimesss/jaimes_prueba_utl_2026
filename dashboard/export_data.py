#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_data.py · Reto 4
Genera dashboard/data.json y reescribe dashboard/index.html AUTOCONTENIDO
(los datos quedan embebidos, por eso abre en Chrome sin servidor).

    python dashboard/export_data.py
"""
import json, os, sqlite3, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "db", "puestos_2026.db")
OUT_JSON = os.path.join(ROOT, "dashboard", "data.json")
OUT_HTML = os.path.join(ROOT, "dashboard", "index.html")


def q(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def build_data(conn):
    municipios = [r["nombre"] for r in q(conn,
        "SELECT nombre FROM municipios ORDER BY nombre")]

    colores = {r["nombre"]: r["color"] for r in q(conn,
        "SELECT DISTINCT nombre, color FROM partidos")}

    # Comparativo: total votos CA (agrupaciones) por municipio
    comparativo_ca = q(conn, """
        SELECT mun.nombre AS municipio, SUM(vp.votos) AS votos
        FROM votos_partido vp
        JOIN mesas m ON m.id = vp.mesa_id
        JOIN puestos p ON p.id = m.puesto_id
        JOIN municipios mun ON mun.codmun = p.codmun
        WHERE vp.corporacion = 'CA'
        GROUP BY mun.nombre ORDER BY votos DESC""")

    por_municipio = {}
    for mun in municipios:
        top10 = q(conn, """
            SELECT c.nombre AS candidato, pa.nombre AS partido,
                   pa.color AS color, SUM(vc.votos) AS votos
            FROM votos_candidato vc
            JOIN candidatos c ON c.id = vc.candidato_id
            JOIN partidos  pa ON pa.codpar = c.codpar AND pa.corporacion = c.corporacion
            JOIN mesas m ON m.id = vc.mesa_id
            JOIN puestos p ON p.id = m.puesto_id
            JOIN municipios mun ON mun.codmun = p.codmun
            WHERE c.corporacion = 'CA' AND mun.nombre = ?
            GROUP BY c.id ORDER BY votos DESC LIMIT 10""", (mun,))
        lider = q(conn, """
            SELECT pa.nombre AS partido, pa.color AS color, SUM(vp.votos) AS votos
            FROM votos_partido vp
            JOIN partidos pa ON pa.codpar = vp.codpar AND pa.corporacion = vp.corporacion
            JOIN mesas m ON m.id = vp.mesa_id
            JOIN puestos p ON p.id = m.puesto_id
            JOIN municipios mun ON mun.codmun = p.codmun
            WHERE vp.corporacion = 'SE' AND mun.nombre = ?
            GROUP BY pa.nombre ORDER BY votos DESC LIMIT 1""", (mun,))
        por_municipio[mun] = {"top10_ca": top10,
                              "lider_se": lider[0] if lider else None}

    # Arrastre Verde por puesto y municipio
    arrastre_rows = q(conn, """
        WITH verde AS (
            SELECT pa.corporacion, mun.nombre AS municipio, p.id AS pid,
                   p.nombre AS puesto, SUM(vp.votos) AS votos
            FROM votos_partido vp
            JOIN partidos pa ON pa.codpar = vp.codpar AND pa.corporacion = vp.corporacion
            JOIN mesas m ON m.id = vp.mesa_id
            JOIN puestos p ON p.id = m.puesto_id
            JOIN municipios mun ON mun.codmun = p.codmun
            WHERE pa.agrupacion = 'ALIANZA_VERDE'
            GROUP BY pa.corporacion, p.id)
        SELECT ca.municipio, ca.puesto,
               ca.votos AS ca, se.votos AS se,
               ROUND(1.0*se.votos/NULLIF(ca.votos,0),3) AS ratio
        FROM verde ca JOIN verde se ON se.pid = ca.pid AND se.corporacion='SE'
        WHERE ca.corporacion='CA' ORDER BY ca.municipio, ca.puesto""")
    arrastre = {}
    for r in arrastre_rows:
        arrastre.setdefault(r["municipio"], []).append(
            {"puesto": r["puesto"], "ca": r["ca"], "se": r["se"], "ratio": r["ratio"]})

    return {
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "municipios": municipios,
        "colores": colores,
        "comparativo_ca": comparativo_ca,
        "por_municipio": por_municipio,
        "arrastre": arrastre,
    }


def main():
    conn = sqlite3.connect(DB)
    data = build_data(conn)
    conn.close()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    html = HTML_TEMPLATE.replace(
        "/*__DATA__*/", json.dumps(data, ensure_ascii=False))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK · data.json ({len(data['municipios'])} municipios) e index.html "
          f"autocontenido generados.")


# --------------------------------------------------------------------- #
#  Plantilla HTML (Chart.js CDN · datos embebidos · sin servidor)
# --------------------------------------------------------------------- #
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Arrastre Electoral · Boyacá 2026 · UTL Senado</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#F5F4EF; --panel:#FFFFFF; --ink:#14181E; --muted:#5C6570;
    --line:#E2E0D8; --accent:#B8892B; --grid:#ECEAE3;
    --mono:ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }
  [data-theme="dark"]{
    --bg:#101419; --panel:#171C23; --ink:#EDEEF0; --muted:#98A2AE;
    --line:#252C35; --accent:#D8AE5A; --grid:#20272F;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
       -webkit-font-smoothing:antialiased;line-height:1.45}
  header{border-bottom:1px solid var(--line);padding:22px 26px;display:flex;
         align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
  .brand{display:flex;flex-direction:column;gap:2px}
  .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.22em;
           text-transform:uppercase;color:var(--accent)}
  h1{margin:0;font-size:26px;font-weight:650;letter-spacing:-.01em}
  .sub{color:var(--muted);font-size:13px}
  .controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  select,button{font-family:var(--sans);font-size:13px;padding:8px 12px;
    border:1px solid var(--line);background:var(--panel);color:var(--ink);
    border-radius:8px;cursor:pointer}
  button:hover,select:hover{border-color:var(--accent)}
  main{padding:24px 26px;display:grid;gap:20px;
       grid-template-columns:1fr 1fr;max-width:1180px;margin:0 auto}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
        padding:18px 18px 12px;min-width:0}
  .card.wide{grid-column:1 / -1}
  .card h2{margin:0 0 2px;font-size:14px;font-weight:640;letter-spacing:.01em}
  .card p.note{margin:0 0 12px;color:var(--muted);font-size:12px}
  .chart-wrap{position:relative;height:300px}
  .lider{display:flex;align-items:center;gap:12px;margin-top:14px;
         padding-top:14px;border-top:1px solid var(--line)}
  .swatch{width:14px;height:14px;border-radius:3px;flex:none}
  .lider .lbl{font-family:var(--mono);font-size:11px;letter-spacing:.14em;
              text-transform:uppercase;color:var(--muted)}
  .lider .val{font-weight:640}
  footer{color:var(--muted);font-size:12px;text-align:center;padding:18px;
         border-top:1px solid var(--line)}
  @media(max-width:860px){main{grid-template-columns:1fr}.chart-wrap{height:260px}}
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="eyebrow">UTL · Senado de la República · Boyacá 2026</span>
    <h1>Arrastre Electoral</h1>
    <span class="sub">Cámara y Senado · Tunja · Paipa · Sogamoso · Duitama</span>
  </div>
  <div class="controls">
    <label class="lbl" for="mun" style="font-size:12px;color:var(--muted)">Municipio</label>
    <select id="mun"></select>
    <button id="csv">Exportar CSV</button>
    <button id="theme">Modo oscuro</button>
  </div>
</header>

<main>
  <section class="card wide">
    <h2>Comparativo · votos Cámara por municipio</h2>
    <p class="note">Total de votos de agrupaciones (lista) a Cámara.</p>
    <div class="chart-wrap"><canvas id="cmp"></canvas></div>
  </section>

  <section class="card">
    <h2>Por municipio · Top 10 candidatos Cámara</h2>
    <p class="note">Voto preferente consolidado. Color = partido.</p>
    <div class="chart-wrap"><canvas id="top"></canvas></div>
    <div class="lider">
      <span class="swatch" id="lidsw"></span>
      <div><div class="lbl">Partido líder Senado</div>
           <div class="val" id="lidtx">—</div></div>
    </div>
  </section>

  <section class="card">
    <h2>Arrastre Verde · ratio SE/CA por puesto</h2>
    <p class="note">Línea de referencia en 1.0: por encima, el Verde traccionó más en Senado.</p>
    <div class="chart-wrap"><canvas id="arr"></canvas></div>
  </section>
</main>

<footer id="foot"></footer>

<script>
const DATA = /*__DATA__*/;
const $ = s => document.querySelector(s);
const fmt = n => (n==null?'—':Number(n).toLocaleString('es-CO'));
let cCmp, cTop, cArr;

function gridColor(){return getComputedStyle(document.body).getPropertyValue('--grid');}
function inkColor(){return getComputedStyle(document.body).getPropertyValue('--ink');}
function baseOpts(){
  const g=gridColor(), ink=inkColor();
  return {responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false}},
    scales:{x:{grid:{color:g},ticks:{color:ink}},
            y:{grid:{color:g},ticks:{color:ink}}}};
}

function drawComparativo(){
  const rows=DATA.comparativo_ca;
  const opts=baseOpts();
  cCmp && cCmp.destroy();
  cCmp=new Chart($('#cmp'),{type:'bar',
    data:{labels:rows.map(r=>r.municipio),
      datasets:[{data:rows.map(r=>r.votos),
        backgroundColor:'#5C6570',borderRadius:5}]},
    options:opts});
}

function drawMunicipio(mun){
  const info=DATA.por_municipio[mun];
  const rows=info.top10_ca;
  const opts=baseOpts(); opts.indexAxis='y';
  cTop && cTop.destroy();
  cTop=new Chart($('#top'),{type:'bar',
    data:{labels:rows.map(r=>r.candidato),
      datasets:[{data:rows.map(r=>r.votos),
        backgroundColor:rows.map(r=>r.color||'#8A8D91'),borderRadius:4}]},
    options:opts});
  const l=info.lider_se;
  $('#lidsw').style.background=l?l.color:'transparent';
  $('#lidtx').textContent=l?`${l.partido} · ${fmt(l.votos)} votos`:'—';
}

function drawArrastre(mun){
  const rows=DATA.arrastre[mun]||[];
  const opts=baseOpts();
  opts.plugins.annotation=undefined;
  cArr && cArr.destroy();
  cArr=new Chart($('#arr'),{type:'line',
    data:{labels:rows.map(r=>r.puesto.replace(/PUESTO |-.*/g,'').trim()||r.puesto),
      datasets:[
        {label:'ratio SE/CA',data:rows.map(r=>r.ratio),
         borderColor:'#007C34',backgroundColor:'#007C34',
         tension:.25,pointRadius:4,fill:false},
        {label:'referencia 1.0',data:rows.map(()=>1),
         borderColor:'#B8892B',borderDash:[6,4],pointRadius:0,fill:false}
      ]},
    options:Object.assign(opts,{plugins:{legend:{display:true,
      labels:{color:inkColor()}}}})});
}

function redraw(){const mun=$('#mun').value;
  drawComparativo();drawMunicipio(mun);drawArrastre(mun);}

// Selector
DATA.municipios.forEach(m=>{const o=document.createElement('option');
  o.value=m;o.textContent=m;$('#mun').appendChild(o);});
$('#mun').addEventListener('change',()=>{const mun=$('#mun').value;
  drawMunicipio(mun);drawArrastre(mun);});

// Dark mode (bonus) - CSS custom properties
$('#theme').addEventListener('click',()=>{
  const dark=document.body.getAttribute('data-theme')==='dark';
  document.body.setAttribute('data-theme',dark?'':'dark');
  $('#theme').textContent=dark?'Modo oscuro':'Modo claro';
  redraw();
});

// Exportar CSV (bonus): top 10 CA del municipio activo
$('#csv').addEventListener('click',()=>{
  const mun=$('#mun').value, rows=DATA.por_municipio[mun].top10_ca;
  let csv='municipio,candidato,partido,votos_ca\n';
  rows.forEach(r=>{csv+=`${mun},"${r.candidato}","${r.partido}",${r.votos}\n`;});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
  a.download=`top10_ca_${mun}.csv`;a.click();
});

$('#foot').textContent=`Datos generados ${DATA.generado} · Pipeline UTL Senado 2026 · Fuente: Registraduría Nacional`;
redraw();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
