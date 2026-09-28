import { useDataset } from '../../hooks/useDataset'
import styles from './Disclaimer.module.css'

export const DISCLAIMER_TEXT =
  'Educational portfolio project. All provider data is synthetic. Not medical advice.'
/** The footer for real CMS data, which must not claim the data is synthetic. */
export const CMS_DISCLAIMER_TEXT =
  'Educational portfolio project. Provider data is public CMS data. Not medical advice.'
/** Until GET /dataset answers, or if it fails: true of either dataset. */
export const NEUTRAL_DISCLAIMER_TEXT = 'Educational portfolio project. Not medical advice.'

export function Disclaimer() {
  const { status, isCms } = useDataset()
  let text = NEUTRAL_DISCLAIMER_TEXT
  if (status === 'ready') text = isCms ? CMS_DISCLAIMER_TEXT : DISCLAIMER_TEXT
  return (
    <p className={styles.disclaimer} role="note">
      {text}
    </p>
  )
}
