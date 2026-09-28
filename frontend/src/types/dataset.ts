// Mirrors backend/app/schemas/dataset.py.

export type DatasetSource = 'synthetic' | 'cms_nj'

export type MetricName =
  | 'quality_score'
  | 'years_experience'
  | 'cost_index'
  | 'patient_volume'
  | 'complication_rate'
  | 'readmission_rate'

/** GET /dataset: which dataset the database holds, and how to label it. */
export interface DatasetInfo {
  source: DatasetSource
  label: string
  description: string
  /** When the CMS files were downloaded (YYYY-MM-DD); null for synthetic data. */
  as_of: string | null
  /** Metrics the dataset publishes; the others are null for every provider. */
  available_metrics: MetricName[]
  /** Each available metric's name as this dataset means it. */
  metric_labels: Partial<Record<MetricName, string>>
  /** The same, short enough for a button ("Spending"); the full one goes in its tooltip. */
  metric_short_labels: Partial<Record<MetricName, string>>
  has_conditions: boolean
  disclaimer: string
  /** Fewest patients for spending per patient to be reported; null without such a rule. */
  min_spending_patients: number | null
  /** Specialty slug -> plural noun ("cardiologists"). Others are "<Name> providers". */
  peer_nouns: Record<string, string>
}
