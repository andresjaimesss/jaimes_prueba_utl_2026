#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etl.py  ·  Transform + Load del pipeline UTL Senado 2026.

- init_db()          crea el esquema (db/schema.sql)
- normalize_source() convierte un JSON crudo de la Registraduria a la forma
                     interna. **UNICA funcion a ajustar** si la API real trae
                     otros nombres de campo (ver dict de alias abajo).
- load_record()      carga idempotente (INSERT OR IGNORE) + carga_log
- normalize_nombre() unifica nombres de candidatos (mayuscula, sin tildes)

Uso directo (reconstruye la BD desde db/raw/ o, si no hay, desde sample_data/):
    python db/etl.py
"""
import json, os, sqlite3, sys, unicodedata, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH     = os.path.join(ROOT, "db", "puestos_2026.db")
SCHEMA_PATH = os.path.join(ROOT, "db", "schema.sql")
RAW_DIR     = os.path.join(ROOT, "db", "raw")
SAMPLE_DIR  = os.path.join(ROOT, "sample_data")

# Catalogo canonico de las agrupaciones exigidas por la prueba.
# (codpar_CA, codpar_SE) -> (agrupacion, color)
PARTIDOS_CATALOGO = [
    # codpar, corporacion, nombre, agrupacion, color
    ("5",  "CA", "ALIANZA VERDE",       "ALIANZA_VERDE",      "#007C34"),
    ("57", "SE", "ALIANZA VERDE",       "ALIANZA_VERDE",      "#007C34"),
    ("87", "CA", "PACTO HISTORICO",     "PACTO_HISTORICO",    "#7B2D8B"),
    ("92", "SE", "PACTO HISTORICO",     "PACTO_HISTORICO",    "#7B2D8B"),
    ("10", "CA", "CENTRO DEMOCRATICO",  "CENTRO_DEMOCRATICO", "#1E477D"),
    ("10", "SE", "CENTRO DEMOCRATICO",  "CENTRO_DEMOCRATICO", "#1E477D"),
    ("2",  "CA", "PARTIDO CONSERVADOR", "CONSERVADOR",        "#E07B00"),
    ("2",  "SE", "PARTIDO CONSERVADOR", "CONSERVADOR",        "#E07B00"),
]


# --------------------------------------------------------------------- #
#  Normalizacion
# --------------------------------------------------------------------- #
def normalize_nombre(s):
    """Mayusculas, sin tildes, espacios colapsados."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def _pick(d, *keys, default=None):
    """Devuelve el primer key presente (tolerante a variantes de la API)."""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def _to_int(v):
    try:
        return int(str(v).replace(".", "").replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0


def normalize_source(raw):
    """
    JSON crudo -> forma interna. AJUSTAR AQUI si la API real difiere.
    Los alias cubren las variantes mas comunes de la Registraduria.
    """
    corp = normalize_nombre(_pick(raw, "eleccion", "corporacion", "tipo", "cargo", default=""))
    corp = "SE" if corp.startswith(("SE", "SEN")) else ("CA" if corp.startswith(("CA", "CAM")) else corp)

    rec = {
        "corporacion": corp,
        "codmun": str(_pick(raw, "codmun", "codigo_municipio", "codMunicipio", "municipio_codigo", default="")).strip(),
        "municipio": normalize_nombre(_pick(raw, "municipio", "nombre_municipio", "nombreMunicipio", default="")),
        "puestos": [],
    }
    for pu in _pick(raw, "puestos", "puestosVotacion", "zonasPuestos", default=[]) or []:
        puesto = {
            "codpue": str(_pick(pu, "codpue", "codigo_puesto", "codPuesto", "puesto_codigo", default="")).strip(),
            "nombre": normalize_nombre(_pick(pu, "puesto", "nombre_puesto", "nombrePuesto", "nombre", default="")),
            "zona":   str(_pick(pu, "zona", "codzona", "codigo_zona", default="")).strip(),
            "mesas": [],
        }
        for me in _pick(pu, "mesas", "mesasVotacion", default=[]) or []:
            mesa = {
                "nummesa": str(_pick(me, "nummesa", "mesa", "numero", "numeroMesa", default="")).strip(),
                "partidos": [],
            }
            for pa in _pick(me, "partidos", "agrupaciones", "partidosPoliticos", "listas", default=[]) or []:
                partido = {
                    "codpar": str(_pick(pa, "codpar", "codigo_partido", "codPartido", "codigo", default="")).strip(),
                    "nombre": normalize_nombre(_pick(pa, "partido", "nombre_partido", "agrupacion", "nombre", default="")),
                    "votos_partido": _to_int(_pick(pa, "votos_partido", "votos", "total", "totalVotos", "votosAgrupacion", default=0)),
                    "candidatos": [],
                }
                for ca in _pick(pa, "candidatos", "candidatosVoto", default=[]) or []:
                    partido["candidatos"].append({
                        "codcan": str(_pick(ca, "codcan", "codigo_candidato", "codCandidato", "codigo", default="")).strip(),
                        "nombre": normalize_nombre(_pick(ca, "candidato", "nombre_candidato", "nombre", default="")),
                        "votos":  _to_int(_pick(ca, "votos", "total", "totalVotos", default=0)),
                    })
                mesa["partidos"].append(partido)
            puesto["mesas"].append(mesa)
        rec["puestos"].append(puesto)
    return rec


# --------------------------------------------------------------------- #
#  Base de datos
# --------------------------------------------------------------------- #
def connect(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    # Semilla del catalogo de partidos (idempotente).
    conn.executemany(
        "INSERT OR IGNORE INTO partidos(codpar,corporacion,nombre,agrupacion,color) VALUES (?,?,?,?,?)",
        PARTIDOS_CATALOGO,
    )
    conn.commit()


def _ensure_partido(conn, codpar, corp, nombre):
    """Auto-registra un partido no catalogado (dedup por PK)."""
    conn.execute(
        "INSERT OR IGNORE INTO partidos(codpar,corporacion,nombre,agrupacion,color) VALUES (?,?,?,?,?)",
        (codpar, corp, nombre or codpar, normalize_nombre(nombre or codpar).replace(" ", "_"), "#8A8D91"),
    )


def load_record(conn, rec, fuente="sample_data"):
    """Carga idempotente de un municipio+corporacion. Devuelve (ins, omit)."""
    corp = rec["corporacion"]
    codmun = rec["codmun"]
    ins = omit = 0

    def ins_ignore(sql, params):
        nonlocal ins, omit
        cur = conn.execute(sql, params)
        if cur.rowcount == 1:
            ins += 1
        else:
            omit += 1

    conn.execute("INSERT OR IGNORE INTO municipios(codmun,nombre) VALUES (?,?)",
                 (codmun, rec["municipio"]))

    for pu in rec["puestos"]:
        conn.execute(
            "INSERT OR IGNORE INTO puestos(codmun,codpue,nombre,zona) VALUES (?,?,?,?)",
            (codmun, pu["codpue"], pu["nombre"], pu["zona"]),
        )
        pid = conn.execute("SELECT id FROM puestos WHERE codmun=? AND codpue=?",
                           (codmun, pu["codpue"])).fetchone()[0]
        for me in pu["mesas"]:
            conn.execute("INSERT OR IGNORE INTO mesas(puesto_id,nummesa) VALUES (?,?)",
                         (pid, me["nummesa"]))
            mid = conn.execute("SELECT id FROM mesas WHERE puesto_id=? AND nummesa=?",
                               (pid, me["nummesa"])).fetchone()[0]
            for pa in me["partidos"]:
                _ensure_partido(conn, pa["codpar"], corp, pa["nombre"])
                ins_ignore(
                    "INSERT OR IGNORE INTO votos_partido(mesa_id,corporacion,codpar,votos) VALUES (?,?,?,?)",
                    (mid, corp, pa["codpar"], pa["votos_partido"]),
                )
                for ca in pa["candidatos"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO candidatos(codpar,corporacion,codcan,nombre) VALUES (?,?,?,?)",
                        (pa["codpar"], corp, ca["codcan"], ca["nombre"]),
                    )
                    cid = conn.execute(
                        "SELECT id FROM candidatos WHERE codpar=? AND corporacion=? AND codcan=?",
                        (pa["codpar"], corp, ca["codcan"]),
                    ).fetchone()[0]
                    ins_ignore(
                        "INSERT OR IGNORE INTO votos_candidato(mesa_id,candidato_id,votos) VALUES (?,?,?)",
                        (mid, cid, ca["votos"]),
                    )

    conn.execute(
        "INSERT INTO carga_log(fuente,municipio,corporacion,filas_insertadas,filas_omitidas,detalle) "
        "VALUES (?,?,?,?,?,?)",
        (fuente, rec["municipio"], corp, ins, omit,
         f"{len(rec['puestos'])} puestos"),
    )
    conn.commit()
    return ins, omit


def rebuild_from_dir(directory, fuente):
    """Reconstruye la BD desde *.json de un directorio."""
    files = sorted(glob.glob(os.path.join(directory, "*.json")))
    if not files:
        return False
    conn = connect()
    init_db(conn)
    tot_i = tot_o = 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            rec = normalize_source(json.load(f))
        if not rec["codmun"]:
            print(f"  [WARN] {os.path.basename(path)} sin codmun, se omite")
            continue
        i, o = load_record(conn, rec, fuente=fuente)
        tot_i += i; tot_o += o
        print(f"  {os.path.basename(path):<18} {rec['municipio']:<10} {rec['corporacion']}  "
              f"ins={i:<5} omit={o}")
    n_mun = conn.execute("SELECT COUNT(*) FROM municipios").fetchone()[0]
    conn.close()
    print(f"OK · {n_mun} municipios · insertadas={tot_i} omitidas={tot_o} · fuente={fuente}")
    return True


if __name__ == "__main__":
    src = RAW_DIR if glob.glob(os.path.join(RAW_DIR, "*.json")) else SAMPLE_DIR
    fuente = "API" if src == RAW_DIR else "sample_data"
    print(f"[etl] reconstruyendo BD desde {os.path.relpath(src, ROOT)}/ ...")
    if not rebuild_from_dir(src, fuente):
        sys.exit("No se encontraron archivos JSON de entrada.")
