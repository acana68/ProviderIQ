import type { DatasetInfo } from '../src/types/dataset'
import type {
  ConditionSummary,
  MetricFlags,
  ScoredProviderDetail,
  SpecialtySummary,
} from '../src/types/provider'
import type { Location, SearchResult } from '../src/types/search'
import { jsonResponse, mockFetch } from './utils'

export const SPECIALTIES: SpecialtySummary[] = [
  { id: 1, slug: 'cardiology', name: 'Cardiology', provider_count: 162 },
  { id: 3, slug: 'dermatology', name: 'Dermatology', provider_count: 134 },
]
export const CARDIOLOGY_CONDITIONS: ConditionSummary[] = [
  { id: 1, slug: 'heart-failure', name: 'Heart failure' },
  { id: 2, slug: 'atrial-fibrillation', name: 'Atrial fibrillation' },
]
export const DERMATOLOGY_CONDITIONS: ConditionSummary[] = [
  { id: 3, slug: 'psoriasis', name: 'Psoriasis' },
  { id: 4, slug: 'eczema', name: 'Eczema' },
]
export const CITIES: Location[] = [
  { city: 'Chicago', state: 'IL' },
  { city: 'New York', state: 'NY' },
]

/** Every metric reported: every synthetic provider. */
export const SYNTHETIC_FLAGS: MetricFlags = {
  quality_score: 'reported',
  years_experience: 'reported',
  cost_index: 'reported',
  complication_rate: 'reported',
  readmission_rate: 'reported',
}

/** GET /dataset's peer_nouns (backend/app/services/explanation.py PEER_NOUNS). */
export const PEER_NOUNS: Record<string, string> = {
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

/** GET /dataset for synthetic data, as the backend answers it. */
export const SYNTHETIC_DATASET: DatasetInfo = {
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
}

/** GET /dataset for the CMS data, as the backend answers it. */
export const CMS_DATASET: DatasetInfo = {
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
}

/**
 * A CMS clinician (invented; the NPI starts with 9, which no real one does): no MIPS score,
 * so quality is imputed; new-patient status and rates unknown; spending lower than 85% of
 * cardiologists.
 */
export const CMS_RESULT: SearchResult = {
  provider: {
    id: 21,
    npi: '9000000002',
    data_source: 'cms',
    display_name: 'Dr. Bob Testperson, DO',
    specialty: { slug: 'cardiology', name: 'Cardiology' },
    subspecialty: null,
    city: 'Newark',
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
  score: {
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
      // CMS spending is scored as its percentile: 85% of peers spend more.
      {
        name: 'cost',
        raw: 0.812,
        normalized: 0.85,
        weight: 0.176,
        contribution: 15,
        imputed: false,
      },
      {
        name: 'volume',
        raw: 0.4,
        normalized: 0.4,
        weight: 0.176,
        contribution: 7.1,
        imputed: false,
      },
    ],
  },
  explanation:
    'Stands out for lower Medicare spending per patient (lower than 85% of cardiologists). MIPS final score not reported, 36 years since medical school.',
}

/** A second CMS clinician: everything missing that can be (experience, spending). */
export const CMS_RESULT_UNREPORTED: SearchResult = {
  provider: {
    ...CMS_RESULT.provider,
    id: 22,
    npi: '9000000012',
    display_name: 'Dr. Ann Testperson, MD',
    years_experience: null,
    quality_score: 65,
    cost_index: null,
    metric_flags: {
      ...CMS_RESULT.provider.metric_flags,
      quality_score: 'reported',
      years_experience: 'imputed',
      cost_index: 'imputed',
    },
  },
  distance_miles: null,
  score: {
    overall: 60.1,
    components: [
      {
        name: 'quality',
        raw: 65,
        normalized: 0.65,
        weight: 0.412,
        contribution: 26.8,
        imputed: false,
      },
      {
        name: 'experience',
        raw: 27,
        normalized: 0.96,
        weight: 0.235,
        contribution: 22.6,
        imputed: true,
      },
      { name: 'cost', raw: 1, normalized: 0.5, weight: 0.176, contribution: 8.8, imputed: true },
      {
        name: 'volume',
        raw: 0.1,
        normalized: 0.1,
        weight: 0.176,
        contribution: 1.8,
        imputed: false,
      },
    ],
  },
  explanation:
    'No single standout factor. Years since medical school not reported, Medicare spending per patient not reported.',
}

/** CMS_RESULT's clinician on the detail page, scored for a balanced search. */
export const CMS_SCORED_DETAIL: ScoredProviderDetail = {
  ...CMS_RESULT.provider,
  zip_code: '07102',
  latitude: 40.73,
  longitude: -74.17,
  patient_volume: 944,
  complication_rate: null,
  readmission_rate: null,
  conditions: [],
  distance_miles: null,
  score: CMS_RESULT.score,
  explanation: CMS_RESULT.explanation,
}

export type Handler = (init?: RequestInit) => Response | Promise<Response>

const REFERENCE_ROUTES: Record<string, Handler> = {
  'GET /api/v1/dataset': () => jsonResponse(SYNTHETIC_DATASET),
  'GET /api/v1/specialties': () => jsonResponse(SPECIALTIES),
  'GET /api/v1/conditions': () =>
    jsonResponse([...CARDIOLOGY_CONDITIONS, ...DERMATOLOGY_CONDITIONS]),
  'GET /api/v1/conditions?specialty=cardiology': () => jsonResponse(CARDIOLOGY_CONDITIONS),
  'GET /api/v1/conditions?specialty=dermatology': () => jsonResponse(DERMATOLOGY_CONDITIONS),
  'GET /api/v1/cities': () => jsonResponse(CITIES),
}

/** Overrides for routeFetch: the API when the database holds the CMS data. */
export const CMS_ROUTES: Record<string, Handler> = {
  'GET /api/v1/dataset': () => jsonResponse(CMS_DATASET),
  'GET /api/v1/conditions': () => jsonResponse([]),
  'GET /api/v1/conditions?specialty=cardiology': () => jsonResponse([]),
  'GET /api/v1/cities': () =>
    jsonResponse([
      { city: 'Newark', state: 'NJ' },
      { city: 'Trenton', state: 'NJ' },
    ]),
}

/**
 * A fake API: answers by "METHOD url" (e.g. "POST /api/v1/search"), with the reference
 * data endpoints built in, and fails loudly on anything unexpected.
 */
export function routeFetch(routes: Record<string, Handler> = {}) {
  return mockFetch().mockImplementation(async (input, init) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const handler = routes[key] ?? REFERENCE_ROUTES[key]
    if (!handler) throw new Error(`Unexpected request: ${key}`)
    return handler(init)
  })
}

/** The parsed JSON bodies of every call to one URL, in order. */
export function requestBodies(fetchSpy: ReturnType<typeof mockFetch>, url: string): unknown[] {
  return fetchSpy.mock.calls
    .filter(([input]) => String(input) === url)
    .map(([, init]) => JSON.parse(init?.body as string))
}
