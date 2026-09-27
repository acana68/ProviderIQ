# Fake raw CMS and Census files

Laid out like `data/raw/`, with the same file names, delimiters, encodings and header
rows as the real downloads. Every data row is invented. The NPIs start with 9, which no
real NPI does (real ones start with 1 or 2). `tests/integration/test_cms_pipeline.py`
runs the whole pipeline on these files.

| NPI | Case |
|---|---|
| 9000000001 | Cardiology. Three NDF rows, two addresses: the 07001 address is listed twice, but 07002 matches the Medicare ZIP, so 07002 wins. MIPS 0 as an individual and 80.5 through a group, so 80.5. |
| 9000000002 | Interventional cardiology, so cardiology. No MIPS row, so quality is NULL. Last name `O'TESTER` becomes `O'Tester`. |
| 9000000003 | Family practice, so primary care. Blank graduation year, and a blank MIPS score: both NULL. |
| 9000000004 | Internal medicine, so primary care. Graduated 1950 (76 years): implausible, so NULL. |
| 9000000005, 9000000006 | Nurse practitioner and physical therapist: unmapped, dropped. |
| 9000000007 | Dermatology. Its only Medicare row is an organization (`O`), so it has no Medicare record. |
| 9000000008 | Dermatology. NDF credential blank, Medicare says `M.D.`, so MD. |
| 9000000009 | Neurology, but the credential is PA: not an MD or DO. |
| 9000000010 | Neurology at ZIP 08999, which has no centroid: not located. |
| 9000000011 | Cardiology. 08999 is listed twice and is the Medicare ZIP, but has no centroid, so 07001 wins (located comes first). Its only MIPS score is 0 (nothing scorable submitted), so quality is NULL. |
| 9000000012 | Cardiology. Neither ZIP matches Medicare. 07003 is listed twice, so it wins, though its address id sorts later. Graduated this year: 0 years. |
| 9000000013 | Practice address in NY: filtered out while loading. |
| 9000000014 | Dermatology, no credential in either source: dropped. |
| 9000000016 | Enrolled as sleep medicine (unmapped) and pulmonary disease, so pulmonology. Graduation year in the future: NULL. Medicare credential `D.O., PH.D.`, so DO. |
| 9111111111 | MIPS row for an NPI outside the NJ extract: filtered out while loading. |

Medicare allowed amount per beneficiary: cardiology 20, 26.67, 60 and 8.33 (median
23.33); primary care 10 and 8.75 (median 9.375); dermatology and pulmonology one provider
each (index 1.0).

Census: Testville (90,000) and Sampleton (45,000) pass the 40,000 threshold. Washington
in Beta County is its county's largest municipality; another Washington exists in Alpha
County, so its name gets the county. Smallburg is too small. The population file is
Latin-1 (note `Smallbúrg`), like the real one.
