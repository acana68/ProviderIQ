import { useEffect, useRef } from 'react'
import { useCrisisSupport } from '../../hooks/useCrisisSupport'
import styles from './CrisisBanner.module.css'

/**
 * Crisis helpline information, above every page once a query has suggested suicide or
 * self-harm risk. Calm rather than alarming, and it never blocks anything: the search
 * works exactly as before.
 */
export function CrisisBanner() {
  const { visible } = useCrisisSupport()
  const ref = useRef<HTMLElement>(null)

  // Bring it into view when it first appears; on a phone the page may be scrolled down to
  // the description box. role="alert" announces it to screen readers.
  useEffect(() => {
    if (visible) ref.current?.scrollIntoView?.({ block: 'nearest' })
  }, [visible])

  if (!visible) return null
  return (
    <aside ref={ref} className={styles.banner} role="alert" aria-label="Crisis support">
      <p className={styles.text}>
        <strong>
          If you're thinking about hurting yourself, you don't have to go through it alone.
        </strong>{' '}
        Call or text <a href="tel:988">988</a> (Suicide &amp; Crisis Lifeline, US). If you're in
        immediate danger, call <a href="tel:911">911</a>.
      </p>
    </aside>
  )
}
