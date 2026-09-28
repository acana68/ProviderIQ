import { createContext, useContext } from 'react'
import type { DatasetInfo } from '../types/dataset'
import type { SpecialtyRef } from '../types/provider'
import { labelsFor, type Labels } from '../utils/labels'

/** loading: GET /dataset hasn't answered. failed: it errored. ready: it answered. */
export type DatasetStatus = 'loading' | 'ready' | 'failed'

export interface DatasetState {
  status: DatasetStatus
  /** GET /dataset's answer; null until it's ready, or if it failed. */
  dataset: DatasetInfo | null
  /** True once the dataset is known to be real CMS data. */
  isCms: boolean
  /** False only when the dataset is known to have no conditions (CMS). */
  hasConditions: boolean
  /** Synthetic labels unless the dataset is CMS (including while loading, or on failure). */
  labels: Labels
  /** Fewest patients for CMS spending per patient to be reported; null if not known. */
  minSpendingPatients: number | null
  /** "cardiologists": the specialty's providers, as the explanations name them. */
  peerNoun: (specialty: SpecialtyRef) => string
}

export function datasetState(status: DatasetStatus, dataset: DatasetInfo | null): DatasetState {
  const nouns = dataset?.peer_nouns ?? {}
  return {
    status,
    dataset,
    isCms: dataset?.source === 'cms_nj',
    hasConditions: dataset?.has_conditions !== false,
    labels: labelsFor(dataset),
    minSpendingPatients: dataset?.min_spending_patients ?? null,
    peerNoun: (specialty) => nouns[specialty.slug] ?? `${specialty.name} providers`,
  }
}

/**
 * Filled by DatasetProvider (components/layout/DatasetProvider.tsx). Outside one, e.g. a
 * test rendering a single page, it's the synthetic dataset, ready.
 */
export const DatasetContext = createContext<DatasetState>(datasetState('ready', null))

/** The dataset the app is showing, fetched once for the whole app. */
export function useDataset(): DatasetState {
  return useContext(DatasetContext)
}
