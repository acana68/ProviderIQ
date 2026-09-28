-- One row per NPI from Medicare Physician & Other Practitioners - by Provider.
--
-- Individuals only (entity code 'I'; 'O' rows are organizations). The file has one
-- row per NPI already. Medicare Part B fee-for-service only: Medicare Advantage,
-- Medicaid and commercial patients aren't counted.
--
--   beneficiaries        Tot_Benes: distinct Medicare patients seen in the year
--                        -> patient_volume
--   medical_*            the Med_* fields: medical (non-drug) services only
--   medical_allowed_per_beneficiary
--                        Med_Mdcr_Alowd_Amt / Med_Tot_Benes
--                        -> the "Medicare spending per patient" index (06_providers.sql)
--
-- Why per beneficiary and not per service: Medicare pays by fee schedule, so the same
-- service is paid about the same whoever provides it, and the amount per service mostly
-- reflects the mix of services billed (many cheap tests vs. mostly visits or
-- procedures), not a price. Spending per patient measures how much care a clinician
-- uses for each patient they see. It is still influenced by how sick those patients are.
--
-- Why medical (non-drug) only: the file splits every total into Drug_* (HCPCS codes on
-- the Medicare Part B Drug Average Sales Price (ASP) list: drugs given in the office,
-- such as chemotherapy, biologic infusions and injections) and Med_* (everything else,
-- "medical (non-ASP) services"). Part B drug spending mostly reflects the condition
-- treated (a chemotherapy regimen, a biologic for macular degeneration or MS), not how
-- much care the clinician chooses to use. Source: CMS, "Medicare Physician & Other
-- Practitioners - by Provider" data dictionary (data.cms.gov).
--
-- Suppression: CMS blanks the Med_* amounts and counts when Med_Sprsn_Ind is set: '*'
-- = fewer than 11 beneficiaries had medical services, '#' = counter-suppressed because
-- the Drug_* part covered fewer than 11 (so it can't be recovered as total - medical).
-- Either way the non-drug amount isn't published, so spending is left unreported.

DROP TABLE IF EXISTS staging.medicare_utilization;
CREATE TABLE staging.medicare_utilization AS
SELECT
    btrim(u.rndrng_npi) AS npi,
    staging.clean(u.rndrng_prvdr_crdntls) AS credentials,
    btrim(u.rndrng_prvdr_zip5) AS zip5,
    staging.to_numeric(u.tot_benes)::int AS beneficiaries,
    staging.to_numeric(u.tot_srvcs) AS services,
    staging.to_numeric(u.tot_mdcr_alowd_amt) AS allowed_amount,
    staging.to_numeric(u.drug_mdcr_alowd_amt) AS drug_allowed_amount,
    staging.clean(u.med_sprsn_ind) IS NOT NULL AS medical_suppressed,
    staging.to_numeric(u.med_tot_benes)::int AS medical_beneficiaries,
    staging.to_numeric(u.med_mdcr_alowd_amt) AS medical_allowed_amount,
    staging.to_numeric(u.med_mdcr_alowd_amt) / NULLIF(staging.to_numeric(u.med_tot_benes), 0)
        AS medical_allowed_per_beneficiary
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
