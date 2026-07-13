-- =====================================================================
-- Tarea 3.3 · Atribucion deterministica SE  (8 pts)
-- Top 5 candidatos de SENADO por atribucion consolidada.
--   A_ij = (votos_cand / votos_partido) x votos_SE_partido   [por mesa],
--          sumado sobre todas las mesas.
-- Interpretacion (ver README §Hallazgos):
--   votos_partido  = suma de voto PREFERENTE del partido en la mesa
--                    (base sobre la que se reparte proporcionalmente).
--   votos_SE_partido = TOTAL de la agrupacion en la mesa (preferente +
--                    voto de solo lista). Asi la formula RE-DISTRIBUYE el
--                    voto de lista entre los candidatos segun su peso.
--   => el top de atribucion puede diferir del top por voto directo.
-- =====================================================================
WITH pref AS (   -- voto preferente SE por candidato y mesa
    SELECT vc.mesa_id, c.codpar, c.id AS candidato_id, c.nombre, vc.votos
    FROM votos_candidato vc
    JOIN candidatos c ON c.id = vc.candidato_id
    WHERE c.corporacion = 'SE'
),
pref_tot AS (    -- base preferente del partido por mesa (denominador)
    SELECT mesa_id, codpar, SUM(votos) AS votos_pref
    FROM pref GROUP BY mesa_id, codpar
),
se_tot AS (      -- total de la agrupacion SE por mesa (multiplicador)
    SELECT mesa_id, codpar, votos AS votos_se_partido
    FROM votos_partido WHERE corporacion = 'SE'
)
SELECT  pa.nombre  AS partido,
        pref.nombre AS candidato,
        ROUND(SUM( (1.0 * pref.votos / NULLIF(pt.votos_pref, 0)) * st.votos_se_partido ), 1)
                    AS atribucion_se
FROM pref
JOIN pref_tot pt ON pt.mesa_id = pref.mesa_id AND pt.codpar = pref.codpar
JOIN se_tot   st ON st.mesa_id = pref.mesa_id AND st.codpar = pref.codpar
JOIN partidos pa ON pa.codpar = pref.codpar AND pa.corporacion = 'SE'
GROUP BY pref.candidato_id
ORDER BY atribucion_se DESC
LIMIT 5;
