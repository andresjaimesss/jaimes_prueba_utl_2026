#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scatter.py · Reto 5.2
viz/scatter_ca_se.png
  cada punto = una MESA
  x = total votos Camara (agrupaciones) en la mesa
  y = total votos Senado (agrupaciones) en la mesa
  color por municipio · recta de regresion OLS · r de Pearson anotado.

Imprime:  r=X.XXX | pendiente=X.XXX | n_mesas=NNN
(el manifest captura estos valores).

    python viz/scatter.py
"""
import os, sqlite3
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "db", "puestos_2026.db")
OUT = os.path.join(ROOT, "viz", "scatter_ca_se.png")


def compute():
    """Devuelve (municipios, puntos_por_mun, r, slope, intercept, n)."""
    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT mun.nombre AS municipio, m.id AS mesa_id,
               SUM(CASE WHEN vp.corporacion='CA' THEN vp.votos ELSE 0 END) AS ca,
               SUM(CASE WHEN vp.corporacion='SE' THEN vp.votos ELSE 0 END) AS se
        FROM votos_partido vp
        JOIN mesas m ON m.id = vp.mesa_id
        JOIN puestos p ON p.id = m.puesto_id
        JOIN municipios mun ON mun.codmun = p.codmun
        GROUP BY m.id
        HAVING ca > 0 AND se > 0
        ORDER BY mun.nombre""").fetchall()
    conn.close()
    pts = {}
    xs, ys = [], []
    for mun, _mid, ca, se in rows:
        pts.setdefault(mun, ([], []))
        pts[mun][0].append(ca); pts[mun][1].append(se)
        xs.append(ca); ys.append(se)
    xs, ys = np.array(xs, float), np.array(ys, float)
    n = len(xs)
    slope, intercept = np.polyfit(xs, ys, 1)
    r = float(np.corrcoef(xs, ys)[0, 1])
    return pts, r, slope, intercept, n, xs


def main():
    pts, r, slope, intercept, n, xs = compute()
    palette = ["#007C34", "#7B2D8B", "#1E477D", "#E07B00",
               "#B8892B", "#2A9D8F", "#9B2226", "#457B9D"]
    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    for i, (mun, (cx, cy)) in enumerate(pts.items()):
        ax.scatter(cx, cy, s=26, alpha=0.72, label=mun,
                   color=palette[i % len(palette)], edgecolors="none")
    xline = np.linspace(xs.min(), xs.max(), 100)
    ax.plot(xline, slope * xline + intercept, color="#14181E", lw=1.8,
            label=f"OLS  y={slope:.2f}x+{intercept:.0f}")
    ax.set_xlabel("Votos Cámara por mesa", fontsize=10)
    ax.set_ylabel("Votos Senado por mesa", fontsize=10)
    ax.set_title("Relación voto Cámara vs Senado por mesa · Boyacá 2026",
                 fontsize=11, pad=10)
    ax.text(0.03, 0.95, f"r de Pearson = {r:.3f}\nn = {n} mesas",
            transform=ax.transAxes, fontsize=10, va="top",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#B8892B"))
    ax.legend(fontsize=8, loc="lower right", framealpha=0.9)
    ax.grid(True, color="#ECEAE3")
    fig.tight_layout()
    fig.savefig(OUT, dpi=130)
    print(f"r={r:.3f} | pendiente={slope:.3f} | n_mesas={n}")


if __name__ == "__main__":
    main()
