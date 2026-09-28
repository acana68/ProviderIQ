-- The provider table: every NPI in the state's NDF rows, either kept or dropped with
-- exactly one reason (the first check it fails, in the order below).

-- Credential: the NDF's, when it says MD or DO. When the NDF leaves it blank, the
-- Medicare file's free-text credential is used instead ("M.D." -> MD, "D.O., PH.D." ->
-- DO). Anything else (PA, NP, OD, ...) isn't a physician credential our schema accepts.
DROP TABLE IF EXISTS staging.npi_funnel;
CREATE TABLE staging.npi_funnel AS
WITH npis AS (
    SELECT DISTINCT npi FROM staging.ndf_rows
),
resolved AS (
    SELECT
        n.npi,
        s.npi IS NOT NULL AS mapped,
        s.first_name,
        s.last_name,
        CASE
            WHEN s.ndf_credential IN ('MD', 'DO') THEN s.ndf_credential
            WHEN s.ndf_credential IS NULL THEN (
                SELECT CASE
                    WHEN 'MD' = ANY (tokens) THEN 'MD'
                    WHEN 'DO' = ANY (tokens) THEN 'DO'
                END
                FROM (
                    SELECT string_to_array(
                        upper(regexp_replace(u.credentials, '[.[:space:]]', '', 'g')), ','
                    ) AS tokens
                ) AS parsed
            )
        END AS credential,
        s.ndf_credential,
        u.npi IS NOT NULL AS in_medicare,
        u.beneficiaries,
        s.located
    FROM npis AS n
    LEFT JOIN staging.ndf_selected AS s ON s.npi = n.npi
    LEFT JOIN staging.medicare_utilization AS u ON u.npi = n.npi
)
SELECT
    npi,
    credential,
    CASE
        WHEN NOT mapped THEN 'specialty not mapped'
        -- Before the credential check, which falls back to the Medicare record.
        WHEN NOT in_medicare THEN 'no Medicare utilization record'
        WHEN credential IS NULL AND ndf_credential IS NOT NULL THEN 'not an MD or DO'
        WHEN credential IS NULL THEN 'credential not published'
        WHEN first_name IS NULL OR last_name IS NULL THEN 'missing name'
        -- Spending isn't checked: a clinician without usable spending is kept, with
        -- spending unreported (see cms_providers below).
        WHEN beneficiaries IS NULL OR beneficiaries <= 0 THEN 'no usable Medicare volume'
        WHEN NOT located THEN 'ZIP code not located'
    END AS drop_reason
FROM resolved;

-- The kept providers, in the shape of the providers table.
--
--   years_experience  reference year - medical school graduation year. NULL when the
--                     year is missing, in the future, or more than 60 years back (an
--                     age of about 85 or more: likelier a data error than a clinician
--                     still billing Medicare). Note it counts residency as experience.
--   quality_score     the MIPS final score (1-100), or NULL without one. A score of 0
--                     (nothing scorable submitted) is NULL too; see 03_mips_scores.sql.
--   spending_status   whether Medicare spending per patient is reported:
--                       reported
--                       suppressed        CMS didn't publish the medical (non-drug)
--                                         amounts (Med_Sprsn_Ind; 04_medicare_utilization.sql)
--                       too_few_patients  fewer than params.min_spending_patients
--                                         patients with medical services
--                       not_usable        amount or patient count missing, or amount <= 0
--   spending_per_patient  medical (non-drug) Medicare allowed amount per beneficiary,
--                     or NULL unless reported.
--   cost_index        Medicare spending per patient: spending_per_patient / the median
--                     of it for the same specialty among the kept NJ providers who have
--                     it. 1.0 = the specialty median. NULL unless reported: the app
--                     imputes it and never lets it make a provider stand out. Per
--                     beneficiary, not per service, and without Part B drugs; see
--                     04_medicare_utilization.sql for why.
--   patient_volume    Medicare beneficiaries.
--   latitude/longitude  the practice ZIP's centroid, not the street address.
--
-- Names and cities are published in capitals; initcap() gives "O'Brien" but also
-- "Mcdonald". Complication and readmission rates aren't published per clinician, so
-- they stay NULL, as does accepting_new_patients (unknown).
DROP TABLE IF EXISTS staging.cms_providers;
CREATE TABLE staging.cms_providers AS
WITH kept AS (
    SELECT
        s.*,
        f.credential,
        u.beneficiaries,
        z.latitude,
        z.longitude,
        CASE
            WHEN u.medical_suppressed THEN 'suppressed'
            WHEN u.medical_beneficiaries IS NULL OR u.medical_allowed_amount IS NULL
                THEN 'not_usable'
            WHEN u.medical_beneficiaries < p.min_spending_patients THEN 'too_few_patients'
            WHEN u.medical_allowed_amount <= 0 THEN 'not_usable'
            ELSE 'reported'
        END AS spending_status,
        u.medical_allowed_per_beneficiary
    FROM staging.npi_funnel AS f
    JOIN staging.ndf_selected AS s ON s.npi = f.npi
    JOIN staging.medicare_utilization AS u ON u.npi = f.npi
    JOIN staging.zip_centroids AS z ON z.zip5 = s.zip5
    CROSS JOIN staging.params AS p
    WHERE f.drop_reason IS NULL
),
spending AS (
    SELECT
        *,
        CASE WHEN spending_status = 'reported' THEN medical_allowed_per_beneficiary END
            AS spending_per_patient
    FROM kept
),
medians AS (
    SELECT
        specialty,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY spending_per_patient) AS median_spending
    FROM spending
    GROUP BY specialty
)
SELECT
    k.npi,
    initcap(k.first_name) AS first_name,
    initcap(k.last_name) AS last_name,
    k.credential,
    k.specialty,
    k.cms_specialty,
    initcap(k.city) AS city,
    p.state,
    k.zip5 AS zip_code,
    k.latitude,
    k.longitude,
    k.graduation_year,
    CASE
        WHEN p.reference_year - k.graduation_year BETWEEN 0 AND 60
            THEN p.reference_year - k.graduation_year
    END AS years_experience,
    round(m.final_score, 2)::float8 AS quality_score,
    coalesce(m.zero_only, false) AS mips_zero_only,
    k.spending_status,
    k.spending_per_patient::float8 AS spending_per_patient,
    -- Rounded to 4 places, and never 0 (the providers table requires cost_index > 0).
    -- NULL when spending isn't reported (the CASE is needed: greatest() ignores NULLs).
    CASE
        WHEN k.spending_per_patient IS NOT NULL THEN greatest(
            round((k.spending_per_patient / md.median_spending)::numeric, 4), 0.0001
        )::float8
    END AS cost_index,
    k.beneficiaries AS patient_volume
FROM spending AS k
CROSS JOIN staging.params AS p
JOIN medians AS md ON md.specialty = k.specialty
LEFT JOIN staging.mips_scores AS m ON m.npi = k.npi;
