import { createContext, useContext } from 'react'

export interface CrisisSupportState {
  /** True once a query suggested suicide or self-harm risk (POST /ai/parse-query's crisis). */
  visible: boolean
  /** Show the crisis banner. It then stays for the rest of the visit (see CrisisProvider). */
  show: () => void
}

/**
 * Filled by CrisisProvider (components/layout/CrisisProvider.tsx). Outside one, e.g. a test
 * rendering a single page, nothing is shown and show() does nothing.
 */
export const CrisisSupportContext = createContext<CrisisSupportState>({
  visible: false,
  show: () => {},
})

export function useCrisisSupport(): CrisisSupportState {
  return useContext(CrisisSupportContext)
}
