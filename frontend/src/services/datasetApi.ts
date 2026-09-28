import type { DatasetInfo } from '../types/dataset'
import { apiGet, type RequestOptions } from './apiClient'

/** Which dataset the database holds, with its labels and disclaimer. */
export function getDataset(options?: RequestOptions): Promise<DatasetInfo> {
  return apiGet<DatasetInfo>('/dataset', options)
}
