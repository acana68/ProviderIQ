-- CMS primary specialty -> our specialty slug.
--
-- Keys are the NDF's pri_spec values exactly as CMS publishes them. The NDF uses the
-- Medicare provider enrollment specialty list; every string here was checked against
-- the NJ extract. Anything not listed is dropped and counted (see docs/data-quality.md).
--
-- The rule: map a CMS specialty only when a patient searching for our specialty would
-- expect that clinician, and they see patients in an office. So subspecialties of the
-- same field are in, while surgical fields, inpatient-only roles, and specialties that
-- several fields share are out.

DROP TABLE IF EXISTS staging.specialty_map;
CREATE TABLE staging.specialty_map (
    cms_specialty text PRIMARY KEY,
    slug text NOT NULL,
    reason text NOT NULL
);

INSERT INTO staging.specialty_map (cms_specialty, slug, reason) VALUES
    -- Cardiology: general cardiology and its three medical subspecialties.
    -- Out: CARDIAC SURGERY (a surgical field).
    ('CARDIOVASCULAR DISEASE (CARDIOLOGY)', 'cardiology', 'general cardiology'),
    ('INTERVENTIONAL CARDIOLOGY', 'cardiology', 'cardiology subspecialty'),
    ('CARDIAC ELECTROPHYSIOLOGY', 'cardiology', 'cardiology subspecialty'),
    ('ADVANCED HEART FAILURE AND TRANSPLANT CARDIOLOGY', 'cardiology', 'cardiology subspecialty'),

    -- Orthopedics. Out: HAND SURGERY (orthopedic or plastic surgeons) and SPORTS MEDICINE
    -- (mostly primary-care trained): both are shared by several fields.
    ('ORTHOPEDIC SURGERY', 'orthopedics', 'orthopedic surgeons are orthopedists'),

    -- Dermatology, including Mohs surgeons, who are dermatologists.
    ('DERMATOLOGY', 'dermatology', 'general dermatology'),
    ('MICROGRAPHIC DERMATOLOGIC SURGERY (MDS)', 'dermatology', 'Mohs surgery is a dermatology subspecialty'),

    -- Neurology, including epileptologists (neurologists). Out: NEUROSURGERY.
    ('NEUROLOGY', 'neurology', 'general neurology'),
    ('EPILEPTOLOGISTS', 'neurology', 'epilepsy is a neurology subspecialty'),

    -- Oncology means medical oncology, as in the synthetic data. Out: RADIATION,
    -- SURGICAL and GYNECOLOGICAL ONCOLOGY (procedure-based fields) and HEMATOLOGY alone
    -- (mostly benign blood disorders).
    ('HEMATOLOGY/ONCOLOGY', 'oncology', 'medical oncology with hematology'),
    ('MEDICAL ONCOLOGY', 'oncology', 'medical oncology'),

    -- Primary care: the adult generalist specialties. Out: HOSPITALIST (inpatient only;
    -- nobody books one), PEDIATRIC MEDICINE (Medicare data says little about children's
    -- doctors), PREVENTIVE MEDICINE and OBSTETRICS/GYNECOLOGY.
    ('FAMILY PRACTICE', 'primary-care', 'adult generalist'),
    ('INTERNAL MEDICINE', 'primary-care', 'adult generalist'),
    ('GENERAL PRACTICE', 'primary-care', 'adult generalist'),
    ('GERIATRIC MEDICINE', 'primary-care', 'generalist care for older adults'),

    ('ENDOCRINOLOGY', 'endocrinology', 'endocrinology'),

    -- Out: COLORECTAL SURGERY (PROCTOLOGY), a surgical field.
    ('GASTROENTEROLOGY', 'gastroenterology', 'gastroenterology'),

    -- Out: CRITICAL CARE (INTENSIVISTS) (ICU only) and SLEEP MEDICINE (shared by
    -- pulmonology, neurology, psychiatry and internal medicine).
    ('PULMONARY DISEASE', 'pulmonology', 'pulmonology'),

    -- Out: ADDICTION MEDICINE (practiced from several base specialties).
    ('PSYCHIATRY', 'psychiatry', 'general psychiatry'),
    ('GERIATRIC PSYCHIATRY', 'psychiatry', 'psychiatry subspecialty');
