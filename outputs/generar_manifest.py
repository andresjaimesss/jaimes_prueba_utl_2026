#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_manifest.py · Validacion automatica del pipeline (Retos 1.3 / 2.3 / 3)

- Verifica 4/4 municipios y conteos por tabla.
- Ejecuta los 3 .sql y captura resultados ("SQL OK" o "ERROR").
- Verifica el partido lider SE por municipio.
- Captura r / pendiente / n_mesas del scatter.
- Escribe outputs/evaluation_manifest.json.

    python outputs/generar_manifest.py
"""
import json, os, sqlite3, sys, datetime

# =====================================================================
#  META  ·  << EDITAR ANTES DE ENTREGAR >>
# =====================================================================
META = {
    "nombre": "JAIMES JAIMES JOHAN ANDRES",
    "email":  "andresjaimes785@gmail.com",
    "repo":   "https://github.com/andresjaimesss/jaimes_prueba_utl_2026",
}
# =====================================================================

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "db", "puestos_2026.db")
SQL_DIR = os.path.join(ROOT, "sql")
OUT = os.path.join(ROOT, "outputs", "evaluation_manifest.json")
sys.path.insert(0, os.path.join(ROOT, "viz"))

ESPERADOS = ["TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"]


def run_sql_file(conn, path):
    sql = open(path, encoding="utf-8").read()
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows


def main():
    if not os.path.exists(DB):
        sys.exit("ERROR: no existe db/puestos_2026.db. Ejecute primero scraper/scraper.py")
    conn = sqlite3.connect(DB)

    # ---- Municipios --------------------------------------------------
    encontrados = [r[0] for r in conn.execute(
        "SELECT nombre FROM municipios ORDER BY nombre")]
    faltan = [m for m in ESPERADOS if m not in encontrados]
    mun_ok = len(faltan) == 0

    # ---- Conteos por tabla ------------------------------------------
    tablas = ["municipios", "partidos", "puestos", "mesas", "candidatos",
              "votos_partido", "votos_candidato", "carga_log"]
    conteos = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tablas}

    # ---- Lider SE por municipio (Reto 2.3) --------------------------
    lider_se = {}
    for m in encontrados:
        row = conn.execute("""
            SELECT pa.nombre, SUM(vp.votos) v
            FROM votos_partido vp
            JOIN partidos pa ON pa.codpar=vp.codpar AND pa.corporacion=vp.corporacion
            JOIN mesas ms ON ms.id=vp.mesa_id
            JOIN puestos p ON p.id=ms.puesto_id
            JOIN municipios mun ON mun.codmun=p.codmun
            WHERE vp.corporacion='SE' AND mun.nombre=?
            GROUP BY pa.nombre ORDER BY v DESC LIMIT 1""", (m,)).fetchone()
        lider_se[m] = {"partido": row[0], "votos": row[1]} if row else None

    # ---- Retos SQL ---------------------------------------------------
    retos = {}
    sql_global_ok = True
    for tarea in ("3_1", "3_2", "3_3"):
        path = os.path.join(SQL_DIR, f"tarea_{tarea}.sql")
        try:
            rows = run_sql_file(conn, path)
            retos[tarea] = {"status": "OK", "filas": len(rows), "muestra": rows[:5]}
            print(f"  tarea_{tarea}: SQL OK ({len(rows)} filas)")
        except Exception as e:  # noqa: BLE001
            sql_global_ok = False
            retos[tarea] = {"status": "ERROR", "error": str(e)}
            print(f"  tarea_{tarea}: ERROR -> {e}")

    # ---- Viz (scatter) ----------------------------------------------
    viz = {}
    try:
        import scatter  # viz/scatter.py
        _pts, r, slope, _b, n, _xs = scatter.compute()
        viz["scatter"] = {"r": round(r, 3), "pendiente": round(slope, 3), "n_mesas": n}
        print(f"  scatter: r={r:.3f} | pendiente={slope:.3f} | n_mesas={n}")
    except Exception as e:  # noqa: BLE001
        viz["scatter"] = {"error": str(e)}
        print(f"  scatter: ERROR -> {e}")

    conn.close()

    manifest = {
        "meta": META,
        "generado": datetime.datetime.now().isoformat(timespec="seconds"),
        "municipios": {
            "esperados": len(ESPERADOS), "encontrados": len(encontrados),
            "lista": encontrados, "faltan": faltan, "ok": mun_ok,
        },
        "conteos": conteos,
        "lider_se_por_municipio": lider_se,
        "retos_sql": retos,
        "viz": viz,
        "resumen": {
            "municipios": f"{len(encontrados)}/{len(ESPERADOS)} municipios",
            "sql": "SQL OK" if sql_global_ok else "SQL ERROR",
        },
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("-" * 52)
    print(f"  {manifest['resumen']['municipios']}")
    print(f"  {manifest['resumen']['sql']} en los 3 retos")
    if not mun_ok:
        print(f"  [AVISO] faltan municipios: {faltan}")
    print(f"  manifest -> {os.path.relpath(OUT, os.getcwd())}")
    if META['nombre'] == "APELLIDO NOMBRE":
        print("  [RECUERDE] edite la seccion META (nombre, email, repo) antes de entregar.")


if __name__ == "__main__":
    main()
