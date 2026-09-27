-- One row per NPI from Medicare Physician & Other Practitioners - by Provider.
--
-- Individuals only (entity code 'I'; 'O' rows are organizations). The file has one
-- row per NPI already. Medicare Part B fee-for-service only: Medicare Advantage,
-- Medicaid and commercial patients aren't counted.
--
--   beneficiaries             distinct Medicare patients seen in the year -> patient_volume
--   allowed_per_beneficiary   total Medicare allowed amount / beneficiaries
--                             -> the "Medicare spending per patient" index
--
-- Why per beneficiary and not per service: Medicare pays by fee schedule, so the same
-- service is paid about the same whoever provides it, and the amount per service mostly
-- reflects the mix of services billed (many cheap tests vs. mostly visits or
-- procedures), not a price. Spending per patient measures how much care a clinician
-- uses for each patient they see. It is still influenced by how sick those patients are.

DROP TABLE IF EXISTS staging.medicare_utilization;
CREATE TABLE staging.medicare_utilization AS
SELECT
    btrim(u.rndrng_npi) AS npi,
    staging.clean(u.rndrng_prvdr_crdntls) AS credentials,
    btrim(u.rndrng_prvdr_zip5) AS zip5,
    staging.to_numeric(u.tot_benes)::int AS beneficiaries,
    staging.to_numeric(u.tot_srvcs) AS services,
    staging.to_numeric(u.tot_mdcr_alowd_amt) AS allowed_amount,
    staging.to_numeric(u.tot_mdcr_alowd_amt) / NULLIF(staging.to_numeric(u.tot_benes), 0)
        AS allowed_per_beneficiary
FROM staging.raw_physician AS u
CROSS JOIN staging.params AS p
WHERE u.rndrng_prvdr_ent_cd = 'I' AND u.rndrng_prvdr_state_abrvtn = p.state;

-- ZIP -> centroid, from the Census ZCTA gazetteer (INTPTLAT/INTPTLONG: the internal
-- point, which always lies inside the ZCTA). A ZCTA approximates a ZIP code; PO-box-only
-- ZIPs have no ZCTA, so providers listed at one can't be located.
DROP TABLE IF EXISTS staging.zip_centroids;
CREATE TABLE staging.zip_centroids AS
SELECT
    btrim(geoid) AS zip5,
    staging.to_numeric(intptlat)::float8 AS latitude,
    staging.to_numeric(intptlong)::float8 AS longitude
FROM staging.raw_zcta
WHERE staging.to_numeric(intptlat) IS NOT NULL AND staging.to_numeric(intptlong) IS NOT NULL;
