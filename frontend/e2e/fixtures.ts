/**
 * The API as each dataset answers it, for the browser checks. Reference data (specialties,
 * conditions, cities) comes from the repo's own CSVs, so the lists are the real ones; the
 * providers are invented (CMS ones too: NPIs starting with 9, which no real clinician has),
 * with long names and texts on purpose, since those are what break narrow layouts.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import type { DatasetInfo } from '../src/types/dataset'
import type {
  ConditionSummary,
  MetricFlags,
  ProviderDetail,
  ProviderScore,
  ScoredProviderDetail,
  SpecialtySummary,
} from '../src/types/provider'
import type { RankingWeightsResponse } from '../src/types/ranking'
import type { Location, SearchResponse, SearchResult } from '../src/types/search'

const DATA_DIR = fileURLToPath(new URL('../../data/', import.meta.url))

/** A simple CSV (no quoted commas in these files) as one object per row. */
function readCsv(path: string): Record<string, string>[] {
  const [header, ...rows] = readFileSync(`${DATA_DIR}${path}`, 'utf-8').trim().split(/\r?\n/)
  const columns = header!.split(',')
  return rows.map((row) => {
    const values = row.split(',')
    return Object.fromEntries(columns.map((column, i) => [column, values[i] ?? '']))
  })
}

export interface ApiFixture {
  dataset: DatasetInfo
  specialties: SpecialtySummary[]
  /** GET /conditions, by ?specialty= ('' for all). */
  conditions: (specialty: string) => ConditionSummary[]
  cities: Location[]
  search: SearchResponse
  /** GET /providers/{id}, plain and with a score. */
  details: Map<number, { plain: ProviderDetail; scored: ScoredProviderDetail }>
  weights: RankingWeightsResponse
}

const SPECIALTY_ROWS = readCsv('reference/specialties.csv')
const SPECIALTY_NAMES = new Map(SPECIALTY_ROWS.map((row) => [row.slug!, row.name!]))
const specialties = (counts: number[]): SpecialtySummary[] =>
  SPECIALTY_ROWS.map((row, i) => ({
    id: i + 1,
    slug: row.slug!,
    name: row.name!,
    provider_count: counts[i % counts.length]!,
  }))

const CONDITION_ROWS = readCsv('reference/conditions.csv').map((row, i) => ({
  id: i + 1,
  slug: row.slug!,
  name: row.name!,
  specialties: row.specialties!.split(';'),
}))

const cities = (path: string): Location[] =>
  readCsv(path).map((row) => ({ city: row.name!, state: row.state! }))

const PEER_NOUNS: Record<string, string> = {
  cardiology: 'cardiologists',
  orthopedics: 'orthopedists',
  dermatology: 'dermatologists',
  neurology: 'neurologists',
  oncology: 'oncologists',
  'primary-care': 'primary care doctors',
  endocrinology: 'endocrinologists',
  gastroenterology: 'gastroenterologists',
  pulmonology: 'pulmonologists',
  psychiatry: 'psychiatrists',
}

const WEIGHTS: RankingWeightsResponse = {
  profiles: {
    balanced: { quality: 0.35, experience: 0.2, cost: 0.15, volume: 0.15, distance: 0.15 },
    quality: { quality: 0.55, experience: 0.2, cost: 0.05, volume: 0.1, distance: 0.1 },
    cost: { quality: 0.25, experience: 0.1, cost: 0.45, volume: 0.05, distance: 0.15 },
    experience: { quality: 0.25, experience: 0.45, cost: 0.1, volume: 0.1, distance: 0.1 },
    distance: { quality: 0.25, experience: 0.1, cost: 0.1, volume: 0.05, distance: 0.5 },
  },
  min_quality_weight: 0.25,
}

const CARDIOLOGY = { slug: 'cardiology', name: SPECIALTY_NAMES.get('cardiology')! }

// --- Synthetic ---------------------------------------------------------------------------

const SYNTHETIC_FLAGS: MetricFlags = {
  quality_score: 'reported',
  years_experience: 'reported',
  cost_index: 'reported',
  complication_rate: 'reported',
  readmission_rate: 'reported',
}

const SYNTHETIC_SCORE: ProviderScore = {
  overall: 82.4,
  components: [
    {
      name: 'quality',
      raw: 91.2,
      normalized: 0.912,
      weight: 0.35,
      contribution: 31.9,
      imputed: false,
    },
    {
      name: 'experience',
      raw: 27,
      normalized: 0.97,
      weight: 0.2,
      contribution: 19.4,
      imputed: false,
    },
    { name: 'cost', raw: 0.86, normalized: 0.64, weight: 0.15, contribution: 9.6, imputed: false },
    {
      name: 'volume',
      raw: 0.81,
      normalized: 0.81,
      weight: 0.15,
      contribution: 12.2,
      imputed: false,
    },
    {
      name: 'distance',
      raw: 6.4,
      normalized: 0.744,
      weight: 0.15,
      contribution: 11.2,
      imputed: false,
    },
  ],
}

const SYNTHETIC_NAMES = [
  'Dr. Alexandria Montgomery-Vanderbilt, MD, PhD',
  'Dr. Maya Patel, DO',
  'Dr. Christopher Oyelaran-Whitfield, MD',
]

function syntheticResult(id: number, name: string): SearchResult {
  return {
    provider: {
      id,
      npi: null,
      data_source: 'synthetic',
      display_name: name,
      specialty: CARDIOLOGY,
      subspecialty: 'Cardiac Electrophysiology and Interventional Cardiology',
      city: 'New York',
      state: 'NY',
      years_experience: 27,
      quality_score: 91.2,
      cost_index: 0.86,
      accepting_new_patients: id % 2 === 0,
      metric_flags: SYNTHETIC_FLAGS,
    },
    distance_miles: 6.4,
    score: SYNTHETIC_SCORE,
    explanation:
      'Stands out for quality (91.2; higher than 94% of cardiologists) and experience (27 years; more experienced than 88% of cardiologists). Slightly below average on cost.',
  }
}

const SYNTHETIC_RESULTS = SYNTHETIC_NAMES.map((name, i) => syntheticResult(i + 1, name))

function syntheticDetail(result: SearchResult) {
  const plain: ProviderDetail = {
    ...result.provider,
    zip_code: '10016',
    latitude: 40.745,
    longitude: -73.978,
    patient_volume: 2345,
    complication_rate: 0.0464,
    readmission_rate: 0.0812,
    conditions: CONDITION_ROWS.filter((c) => c.specialties.includes('cardiology')).map(
      ({ slug, name }) => ({ slug, name }),
    ),
  }
  const scored: ScoredProviderDetail = {
    ...plain,
    distance_miles: result.distance_miles,
    score: result.score,
    explanation: result.explanation,
  }
  return { plain, scored }
}

export const SYNTHETIC: ApiFixture = {
  dataset: {
    source: 'synthetic',
    label: 'Synthetic demo data',
    description: 'Fictional providers generated with a fixed random seed.',
    as_of: null,
    available_metrics: [
      'quality_score',
      'years_experience',
      'cost_index',
      'patient_volume',
      'complication_rate',
      'readmission_rate',
    ],
    metric_labels: {
      quality_score: 'Quality score',
      years_experience: 'Years of experience',
      cost_index: 'Cost',
      patient_volume: 'Patient volume',
      complication_rate: 'Complication rate',
      readmission_rate: 'Readmission rate',
    },
    metric_short_labels: {
      quality_score: 'Quality',
      years_experience: 'Experience',
      cost_index: 'Cost',
      patient_volume: 'Volume',
      complication_rate: 'Complications',
      readmission_rate: 'Readmissions',
    },
    has_conditions: true,
    disclaimer: 'Synthetic demo data: these providers are fictional.',
    min_spending_patients: null,
    peer_nouns: PEER_NOUNS,
  },
  specialties: specialties([162, 134, 151, 149, 140, 171, 139, 150, 152, 152]),
  conditions: (specialty) =>
    CONDITION_ROWS.filter((c) => !specialty || c.specialties.includes(specialty)).map(
      ({ id, slug, name }) => ({ id, slug, name }),
    ),
  cities: cities('reference/cities.csv'),
  search: {
    items: SYNTHETIC_RESULTS,
    page: 1,
    page_size: 20,
    total: 45,
    total_pages: 3,
    priority: 'balanced',
    sort: 'match',
    weights_used: { quality: 0.35, experience: 0.2, cost: 0.15, volume: 0.15, distance: 0.15 },
  },
  details: new Map(SYNTHETIC_RESULTS.map((r) => [r.provider.id, syntheticDetail(r)])),
  weights: WEIGHTS,
}

// --- CMS (New Jersey) ----------------------------------------------------------------------

const CMS_SCORE: ProviderScore = {
  overall: 71.2,
  components: [
    {
      name: 'quality',
      raw: 90.3,
      normalized: 0.903,
      weight: 0.412,
      contribution: 37.2,
      imputed: true,
    },
    {
      name: 'experience',
      raw: 36,
      normalized: 1,
      weight: 0.235,
      contribution: 23.5,
      imputed: false,
    },
    { name: 'cost', raw: 0.812, normalized: 0.85, weight: 0.176, contribution: 15, imputed: false },
    { name: 'volume', raw: 0.4, normalized: 0.4, weight: 0.176, contribution: 7.1, imputed: false },
  ],
}

const CMS_NAMES = [
  'Dr. Bartholomew Testperson-Kowalczyk, DO',
  'Dr. Ann Testperson, MD',
  'Dr. Oluwaseun Testperson, MD, FACC',
]

function cmsResult(id: number, name: string): SearchResult {
  return {
    provider: {
      id,
      npi: `90000000${String(id).padStart(2, '0')}`,
      data_source: 'cms',
      display_name: name,
      specialty: CARDIOLOGY,
      subspecialty: null,
      city: 'Hasbrouck Heights',
      state: 'NJ',
      years_experience: 36,
      quality_score: null,
      cost_index: 0.8123,
      accepting_new_patients: null,
      metric_flags: {
        quality_score: 'imputed',
        years_experience: 'reported',
        cost_index: 'reported',
        complication_rate: 'not_reported',
        readmission_rate: 'not_reported',
      },
    },
    distance_miles: null,
    score: CMS_SCORE,
    explanation:
      'Stands out for lower Medicare spending per patient (lower than 85% of cardiologists). MIPS final score not reported, 36 years since medical school.',
  }
}

const CMS_RESULTS = CMS_NAMES.map((name, i) => cmsResult(21 + i, name))

function cmsDetail(result: SearchResult) {
  const plain: ProviderDetail = {
    ...result.provider,
    zip_code: '07604',
    latitude: 40.86,
    longitude: -74.08,
    patient_volume: 944,
    complication_rate: null,
    readmission_rate: null,
    conditions: [],
  }
  const scored: ScoredProviderDetail = {
    ...plain,
    distance_miles: null,
    score: result.score,
    explanation: result.explanation,
  }
  return { plain, scored }
}

export const CMS: ApiFixture = {
  dataset: {
    source: 'cms_nj',
    label: 'CMS public data: New Jersey',
    description: 'Real New Jersey physicians in 10 specialties, from public CMS data.',
    as_of: '2026-09-26',
    available_metrics: ['quality_score', 'years_experience', 'cost_index', 'patient_volume'],
    metric_labels: {
      quality_score: 'MIPS final score',
      years_experience: 'Years since medical school',
      cost_index: 'Medicare spending per patient',
      patient_volume: 'Medicare patients',
    },
    metric_short_labels: {
      quality_score: 'MIPS score',
      years_experience: 'Years in medicine',
      cost_index: 'Spending',
      patient_volume: 'Patients',
    },
    has_conditions: false,
    min_spending_patients: 30,
    peer_nouns: PEER_NOUNS,
    disclaimer:
      'Real public CMS data about real clinicians, covering Medicare fee-for-service patients only. Scores are illustrative, computed by ProviderIQ from that data, and are not a rating or endorsement of any clinician by ProviderIQ or CMS.',
  },
  specialties: specialties([1008, 212, 540, 380, 610, 2900, 150, 460, 300, 511]),
  conditions: () => [],
  cities: cities('cms/cities_nj.csv'),
  search: {
    items: CMS_RESULTS,
    page: 1,
    page_size: 20,
    total: 1008,
    total_pages: 51,
    priority: 'balanced',
    sort: 'match',
    weights_used: { quality: 0.412, experience: 0.235, cost: 0.176, volume: 0.176 },
  },
  details: new Map(CMS_RESULTS.map((r) => [r.provider.id, cmsDetail(r)])),
  weights: WEIGHTS,
}

export const DATASETS = { synthetic: SYNTHETIC, cms: CMS } as const
export type DatasetName = keyof typeof DATASETS
