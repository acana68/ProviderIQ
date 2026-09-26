import { Link, NavLink, Outlet } from 'react-router'
import styles from './AppLayout.module.css'
import { Disclaimer } from './Disclaimer'

/** The frame around every page: header, the routed page, and the disclaimer footer. */
export function AppLayout() {
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
        <Outlet />
      </main>
      <footer className={styles.footer}>
        <Disclaimer />
      </footer>
    </div>
  )
}
