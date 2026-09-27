-- One MIPS final score per NPI.
--
-- A clinician can have several rows: scored as an individual, through each group
-- (TIN) they bill under, through an APM entity, subgroup or virtual group. The rows can
-- disagree (e.g. 0 as an individual, 75 through their group). We keep the highest.
-- That follows CMS's rule for a clinician scored more than one way under the same TIN
-- (the highest final score is the one used for payment), extended across TINs because
-- we rate the clinician, not the billing arrangement. Scores outside 0-100 or not
-- numeric are ignored.
--
-- A final score of 0 means nothing that could be scored was submitted (in practice, not
-- taking part), so it counts as no score (NULL, then imputed like any other missing
-- score), never as the worst possible quality.
-- Source: CMS, "2024 Traditional MIPS Scoring Guide" (qpp.cms.gov, QPP resource
-- library). The final score (0-100) is the weighted sum of the category scores. A
-- clinician who doesn't submit at least 1 available quality measure gets 0 points in
-- quality unless it's reweighted, and so does a submitted measure that misses data
-- completeness (except in a small practice, which gets 3). Cost needs no submission (it
-- comes from claims), and every scored cost measure earns 1-10 points, so a cost score
-- of 0 means no cost measure was scored. A final score of exactly 0 is therefore 0 in
-- every category that counted. Checked in the national file: all 380 rows with a final
-- score of 0 have quality 0 and improvement activities 0, cost 0 or blank, and
-- Promoting Interoperability 0 or blank (reweighted). The CMS data dictionary
-- (DOC_Data_Dictionary.pdf) says nothing about a final score of 0; it only says the file
-- covers clinicians participating in MIPS and that a blank category score means the
-- category was weighted to 0.
--
--   final_score  the highest score above 0; NULL when every row is 0
--   zero_only    true when the clinician's only scores are 0 (counted in the report)

DROP TABLE IF EXISTS staging.mips_scores;
CREATE TABLE staging.mips_scores AS
SELECT
    npi,
    max(score) FILTER (WHERE score > 0) AS final_score,
    bool_and(score = 0) AS zero_only,
    count(*) AS score_rows
FROM (
    SELECT btrim(npi) AS npi, staging.to_numeric(final_mips_score) AS score
    FROM staging.raw_mips
) AS scores
WHERE score BETWEEN 0 AND 100
GROUP BY npi;
