-- One NDF row per NPI: the clinician's practice address.
--
-- Only rows with a mapped specialty are candidates, so a clinician enrolled under both
-- a mapped and an unmapped specialty keeps the mapped one. Among the candidates, the
-- first row in this order wins:
--
--   1. The ZIP has a Census centroid, so a clinician with several addresses isn't
--      dropped as unlocatable because one of them is a PO box.
--   2. The ZIP matches the one on the clinician's Medicare utilization record: the
--      address two independent CMS sources agree on.
--   3. The address listed on the most NDF rows (under the most enrollments and group
--      affiliations): the clinician's main practice site, most likely.
--   4. Tie-breaks that only make the choice deterministic: address id, enrollment id,
--      group PAC id, specialty. No two rows of one NPI tie on all of them unless
--      they're identical.

DROP TABLE IF EXISTS staging.ndf_selected;
CREATE TABLE staging.ndf_selected AS
WITH candidates AS (
    SELECT
        r.*,
        z.zip5 IS NOT NULL AS located,
        -- NULL (no Medicare record) sorts with false.
        coalesce(r.zip5 = u.zip5, false) AS matches_medicare_zip,
        count(*) OVER (PARTITION BY r.npi, r.address_id) AS address_listings
    FROM staging.ndf_rows AS r
    LEFT JOIN staging.zip_centroids AS z ON z.zip5 = r.zip5
    LEFT JOIN staging.medicare_utilization AS u ON u.npi = r.npi
    WHERE r.specialty IS NOT NULL
)
SELECT DISTINCT ON (npi) *
FROM candidates
ORDER BY
    npi,
    located DESC,
    matches_medicare_zip DESC,
    address_listings DESC,
    address_id NULLS LAST,
    enrollment_id NULLS LAST,
    org_pac_id NULLS LAST,
    cms_specialty;
