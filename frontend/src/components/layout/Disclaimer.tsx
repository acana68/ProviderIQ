import styles from './Disclaimer.module.css'

export const DISCLAIMER_TEXT =
  'Educational portfolio project. All provider data is synthetic. Not medical advice.'

export function Disclaimer() {
  return (
    <p className={styles.disclaimer} role="note">
      {DISCLAIMER_TEXT}
    </p>
  )
}
