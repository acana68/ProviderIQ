-- Search locations: a small list of New Jersey municipalities with coordinates.
--
-- New Jersey is divided entirely into 564 municipalities (cities, boroughs, townships,
-- towns, villages), and the Census publishes them as county subdivisions. Places alone
-- would miss most of the large ones, which are townships (Edison, Woodbridge, Toms River).
--
-- Chosen: every municipality with at least 40,000 residents (Census Vintage 2025
-- estimates), plus the largest municipality in each of the 21 counties, so every part
-- of the state has a nearby search location. Coordinates are the gazetteer's internal
-- point. Names drop the legal suffix ("Newark city" -> "Newark"). When another NJ
-- municipality has the same name without its suffix (there are six Washington
-- townships), the county is added: "Washington (Gloucester County)".

DROP TABLE IF EXISTS staging.cms_cities;
CREATE TABLE staging.cms_cities AS
WITH population AS (
    SELECT
        state || county || cousub AS geoid,
        county,
        staging.to_numeric(popestimate2025)::int AS population
    FROM staging.raw_population
    -- 061: minor civil division (county subdivision) rows.
    WHERE sumlev = '061'
),
counties AS (
    -- 050: county rows, e.g. "Essex County".
    SELECT county, name AS county_name FROM staging.raw_population WHERE sumlev = '050'
),
municipalities AS (
    SELECT
        btrim(g.geoid) AS geoid,
        regexp_replace(btrim(g.name), ' (city|township|borough|town|village)$', '') AS name,
        c.county_name,
        pop.population,
        staging.to_numeric(g.intptlat)::float8 AS latitude,
        staging.to_numeric(g.intptlong)::float8 AS longitude,
        row_number() OVER (
            PARTITION BY pop.county ORDER BY pop.population DESC, btrim(g.geoid)
        ) AS rank_in_county,
        -- Among all NJ municipalities, not only the chosen ones.
        count(*) OVER (
            PARTITION BY regexp_replace(btrim(g.name), ' (city|township|borough|town|village)$', '')
        ) AS name_count
    FROM staging.raw_cousub AS g
    JOIN population AS pop ON pop.geoid = btrim(g.geoid)
    JOIN counties AS c ON c.county = pop.county
),
chosen AS (
    SELECT * FROM municipalities WHERE population >= 40000 OR rank_in_county = 1
)
SELECT
    CASE WHEN name_count > 1 THEN name || ' (' || county_name || ')' ELSE name END AS name,
    p.state,
    latitude,
    longitude,
    county_name,
    population,
    geoid
FROM chosen
CROSS JOIN staging.params AS p;
