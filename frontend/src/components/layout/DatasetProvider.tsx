import { type ReactNode, useMemo } from 'react'
import { useApiData, type Loader } from '../../hooks/useApiData'
import { DatasetContext, datasetState, type DatasetStatus } from '../../hooks/useDataset'
import { getDataset } from '../../services/datasetApi'
import type { DatasetInfo } from '../../types/dataset'

const loadDataset: Loader<DatasetInfo> = (signal) => getDataset({ signal })

/**
 * Fetches GET /dataset once and shares it with every page (see useDataset). AppLayout
 * holds the pages back until it has answered, so nothing is ever shown with the wrong
 * dataset's labels; if it fails, pages render with synthetic labels and a neutral footer.
 */
export function DatasetProvider({ children }: { children: ReactNode }) {
  const { data, error } = useApiData('dataset', loadDataset)
  const status: DatasetStatus = data ? 'ready' : error ? 'failed' : 'loading'
  const value = useMemo(() => datasetState(status, data), [status, data])
  return <DatasetContext value={value}>{children}</DatasetContext>
}
