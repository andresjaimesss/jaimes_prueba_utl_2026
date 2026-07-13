#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
heatmap.py · Reto 5.1
viz/heatmap_municipios.png
  filas    = top 8 candidatos a Camara (por voto total consolidado)
  columnas = 4 municipios
  valor    = % que representa el candidato sobre el total CA del municipio
  con anotaciones en cada celda.

    python viz/heatmap.py
"""
import os, sqlite3
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "db", "puestos_2026.db")
OUT = os.path.join(ROOT, "viz", "heatmap_municipios.png")


def main():
    conn = sqlite3.connect(DB)
    municipios = [r[0] for r in conn.execute(
        "SELECT nombre FROM municipios ORDER BY nombre")]

    top8 = [r[0] for r in conn.execute("""
        SELECT c.nombre
        FROM votos_candidato vc
        JOIN candidatos c ON c.id = vc.candidato_id
        WHERE c.corporacion='CA'
        GROUP BY c.id ORDER BY SUM(vc.votos) DESC LIMIT 8""")]

    # total CA (voto preferente) por municipio, para normalizar la columna
    tot_mun = {m: conn.execute("""
        SELECT SUM(vc.votos) FROM votos_candidato vc
        JOIN candidatos c ON c.id=vc.candidato_id
        JOIN mesas ms ON ms.id=vc.mesa_id
        JOIN puestos p ON p.id=ms.puesto_id
        JOIN municipios mun ON mun.codmun=p.codmun
        WHERE c.corporacion='CA' AND mun.nombre=?""", (m,)).fetchone()[0] or 1
        for m in municipios}

    M = np.zeros((len(top8), len(municipios)))
    for i, cand in enumerate(top8):
        for j, mun in enumerate(municipios):
            v = conn.execute("""
                SELECT COALESCE(SUM(vc.votos),0)
                FROM votos_candidato vc
                JOIN candidatos c ON c.id=vc.candidato_id
                JOIN mesas ms ON ms.id=vc.mesa_id
                JOIN puestos p ON p.id=ms.puesto_id
                JOIN municipios mun ON mun.codmun=p.codmun
                WHERE c.corporacion='CA' AND c.nombre=? AND mun.nombre=?""",
                (cand, mun)).fetchone()[0]
            M[i, j] = 100.0 * v / tot_mun[mun]
    conn.close()

    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    im = ax.imshow(M, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(municipios))); ax.set_xticklabels(municipios, fontsize=10)
    ax.set_yticks(range(len(top8))); ax.set_yticklabels(top8, fontsize=9)
    ax.set_title("Peso de los 8 candidatos top a Cámara por municipio\n"
                 "(% del voto preferente CA del municipio) · Boyacá 2026",
                 fontsize=11, pad=12)
    for i in range(len(top8)):
        for j in range(len(municipios)):
            ax.text(j, i, f"{M[i,j]:.1f}%", ha="center", va="center",
                    fontsize=8, color="black" if M[i, j] < M.max()*0.6 else "white")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("% del total CA municipal", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT, dpi=130)
    print(f"OK · {os.path.relpath(OUT, os.getcwd())} "
          f"({len(top8)} candidatos x {len(municipios)} municipios)")


if __name__ == "__main__":
    main()
