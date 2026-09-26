import type { ReactNode } from 'react'
import styles from './states.module.css'

interface EmptyStateProps {
  title: string
  children?: ReactNode
}

export function EmptyState({ title, children }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <p className={styles.title}>{title}</p>
      {children && <div>{children}</div>}
    </div>
  )
}
