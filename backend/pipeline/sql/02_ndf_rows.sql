-- NDF rows in the state, cleaned, with our specialty slug attached.
--
-- The NDF has one row per clinician per enrollment, group affiliation and practice
-- address, so an NPI can appear many times. Rows stay separate here; 05_select_address
-- picks one per NPI. Rows with an unmapped specialty are kept (specialty NULL) so the
-- drops can be counted.

DROP TABLE IF EXISTS staging.ndf_rows;
CREATE TABLE staging.ndf_rows AS
SELECT
    btrim(n.npi) AS npi,
    staging.clean(n.ind_enrl_id) AS enrollment_id,
    staging.clean(n.provider_first_name) AS first_name,
    staging.clean(n.provider_last_name) AS last_name,
    upper(staging.clean(n.cred)) AS ndf_credential,
    -- A four-digit year, or NULL. Plausibility is checked in 06_providers.
    CASE WHEN btrim(n.grd_yr) ~ '^[0-9]{4}$' THEN btrim(n.grd_yr)::int END AS graduation_year,
    btrim(n.pri_spec) AS cms_specialty,
    m.slug AS specialty,
    staging.clean(n.org_pac_id) AS org_pac_id,
    staging.clean(n.adrs_id) AS address_id,
    staging.clean(n.adr_ln_1) AS address_line_1,
    staging.clean(n.city_town) AS city,
    -- ZIP+4 values are cut to the five-digit ZIP.
    left(btrim(n.zip_code), 5) AS zip5
FROM staging.raw_ndf AS n
CROSS JOIN staging.params AS p
LEFT JOIN staging.specialty_map AS m ON m.cms_specialty = btrim(n.pri_spec)
WHERE n.state = p.state;
