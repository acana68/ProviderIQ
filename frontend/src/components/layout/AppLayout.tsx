import { Link, NavLink, Outlet, useLocation } from 'react-router'
import styles from './AppLayout.module.css'
import { Disclaimer } from './Disclaimer'
import { ErrorBoundary } from './ErrorBoundary'

/** The frame around every page: header, the routed page, and the disclaimer footer. */
export function AppLayout() {
  // Changes on every navigation, even to the same path, so any navigation clears a crash.
  const { key } = useLocation()
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.bar}>
          <Link to="/" className={styles.brand}>
            ProviderIQ
          </Link>
          <nav aria-label="Main">
            <NavLink
              to="/methodology"
              className={({ isActive }) =>
                isActive ? `${styles.navLink} ${styles.active}` : styles.navLink
              }
            >
              Methodology
            </NavLink>
          </nav>
        </div>
      </header>
      <main className={styles.main}>
        <ErrorBoundary resetKey={key}>
          <Outlet />
        </ErrorBoundary>
      </main>
      <footer className={styles.footer}>
        <Disclaimer />
      </footer>
    </div>
  )
}
