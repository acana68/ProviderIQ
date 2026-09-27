-- Helpers for reading the raw text columns.
--
-- Every staging.raw_* column is text, exactly as downloaded. Casting a malformed value
-- with ::numeric would abort the whole transform, so values go through to_numeric(),
-- which turns anything that isn't a plain decimal number (including '') into NULL.

CREATE OR REPLACE FUNCTION staging.to_numeric(value text) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN btrim(value) ~ '^-?[0-9]+(\.[0-9]+)?$' THEN btrim(value)::numeric
    END
$$;

-- NULL for an empty or all-whitespace value; otherwise the value, trimmed.
CREATE OR REPLACE FUNCTION staging.clean(value text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(btrim(value), '')
$$;
