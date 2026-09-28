import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { useDataset } from '../../hooks/useDataset'
import { GITHUB_URL } from '../../utils/links'
import { LoadingState } from '../common/LoadingState'
import styles from './AppLayout.module.css'
import { CrisisBanner } from './CrisisBanner'
import { DatasetBanner } from './DatasetBanner'
import { Disclaimer } from './Disclaimer'
import { ErrorBoundary } from './ErrorBoundary'

/** Pages set in the narrower reading column; every other page uses the standard one. */
const READING_PATHS = ['/methodology', '/privacy']

/**
 * The frame around every page: header, the routed page, and the footer. The page and the
 * banners above it (crisis support once a query calls for it, then the CMS data banner)
 * share one column, so they line up.
 *
 * Until GET /dataset answers, the page isn't rendered at all (only a neutral loading
 * state): everything on it may depend on which dataset it is.
 */
export function AppLayout() {
  // Changes on every navigation, even to the same path, so any navigation clears a crash.
  const { key, pathname } = useLocation()
  const { status } = useDataset()
  const reading = READING_PATHS.includes(pathname)
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
        <div className={reading ? `${styles.column} ${styles.reading}` : styles.column}>
          <CrisisBanner />
          {status === 'loading' ? (
            <LoadingState />
          ) : (
            <>
              <DatasetBanner />
              <ErrorBoundary resetKey={key}>
                <Outlet />
              </ErrorBoundary>
            </>
          )}
        </div>
      </main>
      <footer className={styles.footer}>
        <Disclaimer />
        <nav aria-label="Footer" className={styles.footerNav}>
          <Link to="/privacy">Privacy</Link>
          <a href={GITHUB_URL}>GitHub</a>
        </nav>
      </footer>
    </div>
  )
}
