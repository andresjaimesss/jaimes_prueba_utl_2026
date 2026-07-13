#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper.py  ·  Reto 1 · Extraccion API Registraduria (Congreso 2026 · Boyaca)

Extrae Camara (CA) y Senado (SE) de los 4 municipios y carga la BD de forma
idempotente. Si la API no responde, usa sample_data/ (documentado en README).

    python scraper/scraper.py                         # 4 municipios (CA y SE)
    python scraper/scraper.py --municipios TUNJA PAIPA
    python scraper/scraper.py --preflight             # conteo sin descargar (+3)
    python scraper/scraper.py --source sample         # forzar datos de muestra

--------------------------------------------------------------------------
MAPEO DE LA API  (confirmar con F12 -> Network en el portal; ver README §API)
  Host   : https://resultadospreccongreso2026.registraduria.gov.co
  Patron : el SPA pide un JSON por division geografica (nomenclator DIVIPOL).
  Si el patron real difiere, ajuste URL_TEMPLATES y CORP_CODE aqui abajo, y
  parse en db/etl.py::normalize_source (unico punto de mapeo de campos).
--------------------------------------------------------------------------
"""
import argparse, json, os, sys, time

# etl vive en ../db
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "db"))
import etl  # noqa: E402

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://resultadospreccongreso2026.registraduria.gov.co"
CORP_CODE = {"CA": "camara", "SE": "senado"}      # <- confirmar con F12
HEADERS = {
    "User-Agent": "Mozilla/5.0 (UTL-Boyaca-2026 pipeline)",
    "Accept": "application/json, text/plain, */*",
    "Referer": API_BASE + "/",
}
# Patron REAL verificado con F12 -> Network (ver README §API):
#   nomenclator:  {base}/json/nomenclator.json
#   resultados:   {base}/json/{ambito}.json     (ambito = codigo interno)
# El JSON real trae los votos en camaras[].partotabla[]/mapagan[], una forma
# distinta a la del enunciado. Mientras normalize_source() se adapte a esa
# forma, el pipeline se alimenta de sample_data (ver README). Al detectar el
# esquema real, run() lo registra y cae a sample_data de forma limpia.
URL_TEMPLATES = [
    "{base}/json/{ambito}.json",
]

MUNICIPIOS = {  # nombre -> codmun DIVIPOL (Boyaca = 15)
    "TUNJA": "15001", "PAIPA": "15516", "SOGAMOSO": "15759", "DUITAMA": "15238",
}
# codmun DIVIPOL -> ambito interno de la Registraduria (resolver en nomenclator).
# Tunja verificado en vivo (/json/0700001.json); los demas a confirmar.
AMBITO = {"15001": "0700001", "15516": None, "15759": None, "15238": None}
COD2NOM = {v: k for k, v in MUNICIPIOS.items()}
RAW_DIR = os.path.join(ROOT, "db", "raw")
SAMPLE_DIR = os.path.join(ROOT, "sample_data")


def resolve_municipios(args_list):
    if not args_list:
        return list(MUNICIPIOS.items())
    out = []
    for a in args_list:
        key = etl.normalize_nombre(a)
        if key in MUNICIPIOS:
            out.append((key, MUNICIPIOS[key]))
        elif a in COD2NOM:
            out.append((COD2NOM[a], a))
        else:
            print(f"  [WARN] municipio desconocido: {a}")
    return out


def fetch_api(codmun, corp, retries=3, backoff=1.5, timeout=15):
    """Descarga con retry/backoff exponencial. Devuelve dict o None.
    Requiere el 'ambito' interno del municipio (resuelto via nomenclator)."""
    if requests is None:
        return None
    ambito = AMBITO.get(codmun)
    if not ambito:
        print(f"      ambito de {codmun} no resuelto en nomenclator -> sample_data")
        return None
    last = None
    for tmpl in URL_TEMPLATES:
        url = tmpl.format(base=API_BASE, ambito=ambito)
        for intento in range(1, retries + 1):
            try:
                r = requests.get(url, headers=HEADERS, timeout=timeout)
                if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                    return r.json()
                last = f"HTTP {r.status_code}"
                if r.status_code in (404, 400):
                    break
            except Exception as e:  # noqa: BLE001
                last = str(e)[:80]
            time.sleep(backoff ** intento)
    print(f"      API sin respuesta ({last}) -> fallback sample_data")
    return None


def es_esquema_real(raw):
    """True si el JSON viene con la forma real de la Registraduria (camaras[])."""
    return isinstance(raw, dict) and "camaras" in raw


def load_sample(codmun, corp):
    path = os.path.join(SAMPLE_DIR, f"{codmun}_{corp}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def preflight(municipios):
    """Muestra conteo (puestos/mesas) sin cargar la BD. Bonus 1.2 (+3)."""
    print("PREFLIGHT (sin descargar a BD):")
    print(f"  {'MUNICIPIO':<10} {'CORP':<4} {'PUESTOS':>8} {'MESAS':>7} {'FUENTE'}")
    tot = 0
    for nombre, codmun in municipios:
        for corp in ("CA", "SE"):
            raw = fetch_api(codmun, corp)
            if raw is not None and es_esquema_real(raw):
                raw = None  # esquema real -> usar sample para el conteo
            raw = raw or load_sample(codmun, corp)
            fuente = "API/sample"
            if raw is None:
                print(f"  {nombre:<10} {corp:<4} {'--':>8} {'--':>7} NO DISPONIBLE")
                continue
            rec = etl.normalize_source(raw)
            n_pu = len(rec["puestos"])
            n_me = sum(len(p["mesas"]) for p in rec["puestos"])
            tot += n_me
            print(f"  {nombre:<10} {corp:<4} {n_pu:>8} {n_me:>7} {fuente}")
    print(f"  TOTAL mesas estimadas: {tot}")


def run(municipios, force_source=None):
    os.makedirs(RAW_DIR, exist_ok=True)
    conn = etl.connect()
    etl.init_db(conn)
    tot_i = tot_o = 0
    print(f"Extrayendo {len(municipios)} municipio(s) x 2 corporaciones...")
    for nombre, codmun in municipios:
        for corp in ("CA", "SE"):
            if force_source == "sample":
                raw, fuente = load_sample(codmun, corp), "sample_data"
            else:
                raw = fetch_api(codmun, corp)
                fuente = "API"
                # La API real entrega la forma camaras[]/partotabla[], distinta
                # a la del enunciado. Hasta adaptar normalize_source() a esa
                # forma, se usa sample_data (documentado en README §API).
                if raw is not None and es_esquema_real(raw):
                    print(f"      esquema real (camaras[]) detectado -> sample_data")
                    raw = None
                if raw is None:
                    raw, fuente = load_sample(codmun, corp), "sample_data"
            if raw is None:
                print(f"  [ERROR] {nombre} {corp}: sin datos (ni API ni sample)")
                continue
            # landing crudo (permite reconstruir con db/etl.py)
            with open(os.path.join(RAW_DIR, f"{codmun}_{corp}.json"), "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False)
            rec = etl.normalize_source(raw)
            i, o = etl.load_record(conn, rec, fuente=fuente)
            tot_i += i; tot_o += o
            print(f"  {nombre:<10} {corp}  ins={i:<5} omit={o:<5} fuente={fuente}")
    n_mun = conn.execute("SELECT COUNT(*) FROM municipios").fetchone()[0]
    n_mesas = conn.execute("SELECT COUNT(*) FROM mesas").fetchone()[0]
    conn.close()
    print("-" * 52)
    print(f"BD lista: {n_mun}/4 municipios · {n_mesas} mesas · "
          f"insertadas={tot_i} omitidas={tot_o}")
    print(f"Archivo: {os.path.relpath(etl.DB_PATH, os.getcwd())}")


def main():
    ap = argparse.ArgumentParser(description="Scraper resultados Congreso 2026 - Boyaca")
    ap.add_argument("--municipios", nargs="*", help="TUNJA PAIPA ... (default: los 4)")
    ap.add_argument("--preflight", action="store_true", help="conteo sin descargar (+3)")
    ap.add_argument("--source", choices=["api", "sample"], help="forzar fuente")
    args = ap.parse_args()
    municipios = resolve_municipios(args.municipios)
    if not municipios:
        sys.exit("Sin municipios validos.")
    if args.preflight:
        preflight(municipios)
    else:
        run(municipios, force_source=args.source)


if __name__ == "__main__":
    main()
