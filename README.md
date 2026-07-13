# JAIMES — Prueba Técnica UTL Senado 2026

Pipeline de datos electorales del Congreso 2026 para cuatro municipios de
Boyacá (Tunja, Paipa, Sogamoso, Duitama): extracción desde la API de la
Registraduría, base de datos SQLite, SQL analítico de arrastre electoral,
dashboard HTML interactivo y visualizaciones en Python.

## Candidato

| Campo | Valor |
|-------|-------|
| Nombre | Johan Andres Jaimes Jaimes |
| Email  | andresjaimes785@gmail.com |
| Repositorio | https://github.com/andresjaimesss/jaimes_prueba_utl_2026 |

## Instalación

Requisitos: **Python 3.10+** (SQLite viene con la librería estándar).

```bash
pip install -r requirements.txt
```

Dependencias: `requests` (scraper), `matplotlib` y `numpy` (visualizaciones).

## Pipeline de ejecución

Ejecute en este orden desde la raíz del repositorio (reproduce todo en < 10 min):

```bash
# 1) Extracción + carga idempotente de la BD (Cámara y Senado, 4 municipios)
python scraper/scraper.py                 # usa la API; si no responde, sample_data/
python scraper/scraper.py --preflight      # (bonus) conteo sin descargar

# 2) (opcional) Reconstruir la BD desde los JSON crudos ya descargados
python db/etl.py

# 3) Datos + dashboard autocontenido
python dashboard/export_data.py            # genera data.json e index.html

# 4) Visualizaciones
python viz/heatmap.py                      # viz/heatmap_municipios.png
python viz/scatter.py                      # viz/scatter_ca_se.png

# 5) Validación / manifest de evaluación
python outputs/generar_manifest.py         # imprime "4/4 municipios" y "SQL OK"
```

Abra `dashboard/index.html` directamente en Chrome o Firefox (sin servidor; los
datos van embebidos en el archivo).

## API

**Host:** `https://resultadospreccongreso2026.registraduria.gov.co`
El portal es una SPA: la interfaz consulta primero un **nomenclator** (división
político-electoral, DIVIPOL) y luego un JSON de resultados por división
geográfica. El mapeo se hizo con **F12 → pestaña Network**.

**Patrón de URL** (por corporación y municipio; ajustable en
`scraper/scraper.py → URL_TEMPLATES` y `CORP_CODE`):

```
{host}/api/v1/resultados/{corporacion}/municipio/{codmun}
{host}/data/{corporacion}/{codmun}.json         # variantes probadas
```

**Cómo obtener el nomenclator:** los códigos DIVIPOL de Boyacá (departamento
`15`) para los municipios objetivo son `TUNJA=15001`, `PAIPA=15516`,
`SOGAMOSO=15759`, `DUITAMA=15238` (mapa `MUNICIPIOS` en `scraper.py`). El
listado completo se obtiene del endpoint de nomenclator que carga la SPA al
inicio (visible en Network al abrir el portal).

**Campos JSON utilizados (8+):** `codmun`, `municipio`, `puestos[]`,
`codpue`, `zona`, `mesas[]`, `nummesa`, `partidos[]`, `codpar`,
`votos_partido`, `candidatos[]`, `codcan`, `votos`.

**Cabeceras HTTP:** `User-Agent`, `Accept: application/json`, `Referer` al host
(ver `HEADERS` en `scraper.py`).

**Intento contra la API / fallback:** el scraper hace *retry con backoff
exponencial* sobre los patrones de URL. Si la API no responde (fuera de la
ventana de publicación o cambio de esquema), usa automáticamente los archivos
de `sample_data/` con la misma forma, y lo registra en `carga_log` con
`fuente='sample_data'`. El parser de campos está aislado en
`db/etl.py → normalize_source()` y es tolerante a variantes de nombres de campo,
para adaptarse al esquema real con un cambio mínimo.

## Municipios en la BD

| Municipio | codmun | Corporaciones |
|-----------|--------|---------------|
| TUNJA     | 15001  | CA + SE |
| PAIPA     | 15516  | CA + SE |
| SOGAMOSO  | 15759  | CA + SE |
| DUITAMA   | 15238  | CA + SE |

Verificable con `python outputs/generar_manifest.py` → `4/4 municipios`.

## Hallazgos principales

- **Arrastre Verde CA→SE (3.1).** El ratio `votos_SE / votos_CA` de la Alianza
  Verde (homologación `codpar 5 → 57`) se calcula por puesto y municipio. Un
  ratio > 1.0 (línea de referencia del dashboard) indica que la lista traccionó
  más en Senado que en Cámara en ese puesto; el patrón no es uniforme, hay
  puestos con arrastre alto y otros por debajo de 1.0.
- **Dominancia extrema (3.2).** Se identifican las mesas donde un solo candidato
  concentra > 60 % de los votos de su partido en esa mesa — señal de liderazgos
  muy localizados (caciquismo de puesto).
- **Atribución determinística SE (3.3).** `A_ij = (votos_cand / votos_partido) ×
  votos_SE_partido`. Aquí `votos_partido` es la base de **voto preferente** del
  partido en la mesa y `votos_SE_partido` es el **total** de la agrupación
  (preferente + voto de solo lista). Por eso **el top por atribución no siempre
  coincide con el top por voto directo (bonus 3.3):** la fórmula reparte el voto
  de lista entre los candidatos según su peso preferente, favoreciendo a
  candidatos de listas con mucho voto de solo-lista frente a candidatos con voto
  personal alto pero en listas pequeñas.

## Bonus implementados

- **1.2** Flag `--preflight` en el scraper (conteo sin descargar). **(+3)**
- **2.1** 3 índices SQLite con justificación (ver `db/schema.sql`). **(+2)**
- **3.3** Explicación de por qué el top CA ≠ top atribución SE (arriba). **(+2)**
- **4** Dark mode con CSS custom properties (botón *Modo oscuro*). **(+3)**
- **4** Botón *Exportar CSV* funcional en el dashboard. **(+2)**
