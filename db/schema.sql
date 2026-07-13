-- =====================================================================
-- schema.sql  ·  Prueba Tecnica UTL Senado 2026 · Boyaca
-- Modelo relacional del padron de resultados (Camara=CA / Senado=SE)
-- Jerarquia Registraduria: municipio -> puesto -> mesa -> agrupacion/candidato
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ----- Catalogos -----------------------------------------------------
CREATE TABLE IF NOT EXISTS municipios (
    codmun  TEXT PRIMARY KEY,
    nombre  TEXT NOT NULL
);

-- Un mismo partido usa codpar distinto por corporacion (voto preferente):
-- Alianza Verde = 5 (CA) / 57 (SE), Pacto = 87/92, etc.
-- 'agrupacion' es la clave canonica que homologa CA<->SE.
CREATE TABLE IF NOT EXISTS partidos (
    codpar       TEXT NOT NULL,
    corporacion  TEXT NOT NULL CHECK (corporacion IN ('CA','SE')),
    nombre       TEXT NOT NULL,
    agrupacion   TEXT NOT NULL,          -- canonica: ALIANZA_VERDE, PACTO_HISTORICO...
    color        TEXT,                   -- hex para el dashboard
    PRIMARY KEY (codpar, corporacion)
);

CREATE TABLE IF NOT EXISTS puestos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    codmun  TEXT NOT NULL REFERENCES municipios(codmun),
    codpue  TEXT NOT NULL,
    nombre  TEXT,
    zona    TEXT,
    UNIQUE (codmun, codpue)             -- idempotencia
);

CREATE TABLE IF NOT EXISTS mesas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    puesto_id  INTEGER NOT NULL REFERENCES puestos(id),
    nummesa    TEXT NOT NULL,
    UNIQUE (puesto_id, nummesa)         -- idempotencia
);

CREATE TABLE IF NOT EXISTS candidatos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    codpar       TEXT NOT NULL,
    corporacion  TEXT NOT NULL CHECK (corporacion IN ('CA','SE')),
    codcan       TEXT NOT NULL,
    nombre       TEXT NOT NULL,
    UNIQUE (codpar, corporacion, codcan),
    FOREIGN KEY (codpar, corporacion) REFERENCES partidos(codpar, corporacion)
);

-- ----- Hechos --------------------------------------------------------
-- Total de la agrupacion (lista) por mesa y corporacion.
CREATE TABLE IF NOT EXISTS votos_partido (
    mesa_id      INTEGER NOT NULL REFERENCES mesas(id),
    corporacion  TEXT NOT NULL CHECK (corporacion IN ('CA','SE')),
    codpar       TEXT NOT NULL,
    votos        INTEGER NOT NULL CHECK (votos >= 0),
    PRIMARY KEY (mesa_id, corporacion, codpar),
    FOREIGN KEY (codpar, corporacion) REFERENCES partidos(codpar, corporacion)
);

-- Voto preferente por candidato y mesa.
CREATE TABLE IF NOT EXISTS votos_candidato (
    mesa_id       INTEGER NOT NULL REFERENCES mesas(id),
    candidato_id  INTEGER NOT NULL REFERENCES candidatos(id),
    votos         INTEGER NOT NULL CHECK (votos >= 0),
    PRIMARY KEY (mesa_id, candidato_id)
);

-- ----- Auditoria de carga -------------------------------------------
CREATE TABLE IF NOT EXISTS carga_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    fuente            TEXT,               -- 'API' | 'sample_data'
    municipio         TEXT,
    corporacion       TEXT,
    filas_insertadas  INTEGER DEFAULT 0,
    filas_omitidas    INTEGER DEFAULT 0,
    detalle           TEXT
);

-- ----- Indices (bonus 2.1) ------------------------------------------
-- Optimiza el filtro corporacion+codpar del arrastre (3.1) y de export_data.
CREATE INDEX IF NOT EXISTS idx_vpart_corp_par ON votos_partido(corporacion, codpar);
-- Optimiza los JOIN de atribucion/dominancia (3.2/3.3) por candidato.
CREATE INDEX IF NOT EXISTS idx_vcand_cand    ON votos_candidato(candidato_id);
-- Optimiza el recorrido municipio -> puestos del dashboard y del heatmap.
CREATE INDEX IF NOT EXISTS idx_puestos_mun   ON puestos(codmun);
