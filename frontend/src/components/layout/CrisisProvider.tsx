import { type ReactNode, useCallback, useMemo, useState } from 'react'
import { CrisisSupportContext } from '../../hooks/useCrisisSupport'

/**
 * Whether to show the crisis banner (CrisisBanner, in AppLayout). Once shown it stays until
 * the page is reloaded: rewording the query, or searching, shouldn't take the helpline
 * away. Held in memory only: never stored, sent or logged.
 */
export function CrisisProvider({ children }: { children: ReactNode }) {
  const [visible, setVisible] = useState(false)
  const show = useCallback(() => setVisible(true), [])
  const value = useMemo(() => ({ visible, show }), [visible, show])
  return <CrisisSupportContext value={value}>{children}</CrisisSupportContext>
}
