-- =====================================================================
-- Tarea 3.1 · Arrastre Verde CA -> SE  (9 pts)
-- Ratio  votos_SE_Verde / votos_CA_Verde  por PUESTO y MUNICIPIO.
-- Homologacion: Alianza Verde codpar_CA = 5  ->  codpar_SE = 57
--   (aqui via agrupacion canonica 'ALIANZA_VERDE' para robustez).
-- ratio > 1  => el Verde traccion mas en Senado que en Camara en ese puesto.
-- =====================================================================
WITH verde AS (
    SELECT pa.corporacion, p.codmun, p.id AS puesto_id, SUM(vp.votos) AS votos
    FROM votos_partido vp
    JOIN partidos  pa ON pa.codpar = vp.codpar AND pa.corporacion = vp.corporacion
    JOIN mesas     m  ON m.id = vp.mesa_id
    JOIN puestos   p  ON p.id = m.puesto_id
    WHERE pa.agrupacion = 'ALIANZA_VERDE'
    GROUP BY pa.corporacion, p.codmun, p.id
),
ca AS (SELECT codmun, puesto_id, votos AS votos_ca FROM verde WHERE corporacion = 'CA'),
se AS (SELECT codmun, puesto_id, votos AS votos_se FROM verde WHERE corporacion = 'SE')
SELECT  mun.nombre                                   AS municipio,
        pu.nombre                                    AS puesto,
        ca.votos_ca                                  AS votos_ca_verde,
        se.votos_se                                  AS votos_se_verde,
        ROUND(1.0 * se.votos_se / NULLIF(ca.votos_ca, 0), 3) AS ratio_arrastre
FROM ca
JOIN se         ON se.puesto_id = ca.puesto_id
JOIN puestos pu ON pu.id       = ca.puesto_id
JOIN municipios mun ON mun.codmun = ca.codmun
ORDER BY ratio_arrastre DESC;
