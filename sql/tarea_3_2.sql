-- =====================================================================
-- Tarea 3.2 · Dominancia extrema  (8 pts)
-- Mesas donde UN candidato concentra > 60% del total de votos de su
-- partido (agrupacion/lista) en esa misma mesa y corporacion.
-- Denominador: votos_partido (total de la agrupacion en la mesa).
-- =====================================================================
SELECT  mun.nombre                                          AS municipio,
        pu.nombre                                           AS puesto,
        m.nummesa                                           AS mesa,
        c.corporacion                                       AS corp,
        pa.nombre                                           AS partido,
        c.nombre                                            AS candidato,
        vc.votos                                            AS votos_candidato,
        vp.votos                                            AS votos_partido,
        ROUND(100.0 * vc.votos / vp.votos, 1)               AS pct_del_partido
FROM votos_candidato vc
JOIN candidatos     c  ON c.id = vc.candidato_id
JOIN votos_partido  vp ON vp.mesa_id = vc.mesa_id
                      AND vp.corporacion = c.corporacion
                      AND vp.codpar = c.codpar
JOIN mesas          m  ON m.id = vc.mesa_id
JOIN puestos        pu ON pu.id = m.puesto_id
JOIN municipios     mun ON mun.codmun = pu.codmun
JOIN partidos       pa ON pa.codpar = c.codpar AND pa.corporacion = c.corporacion
WHERE vp.votos > 0
  AND 1.0 * vc.votos / vp.votos > 0.60
ORDER BY pct_del_partido DESC, votos_candidato DESC;
