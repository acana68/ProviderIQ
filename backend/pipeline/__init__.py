"""ELT pipeline for real public data: CMS clinicians in New Jersey.

extract.py downloads raw files into data/raw/, load.py copies them unchanged into the
`staging` schema, the numbered SQL files in sql/ transform them, and transform.py writes
the result to data/cms/ for seeding. See docs/architecture.md, "Real data".
"""
