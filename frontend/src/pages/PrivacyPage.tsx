import { Link } from 'react-router'
import { GITHUB_URL } from '../utils/links'
import styles from './PrivacyPage.module.css'

/**
 * What happens to what people type and do, in plain language. Every statement here must
 * stay true of the code: search_logs' columns (backend/app/models/search_log.py), the
 * parse-query log line (backend/app/api/routes/ai.py), the access logs
 * (backend/app/core/middleware.py, frontend/nginx.conf) and the rate limiters.
 */
export function PrivacyPage() {
  return (
    <article className={styles.page}>
      <title>Privacy · ProviderIQ</title>
      <h1>Privacy</h1>
      <p className={styles.lead}>
        The short version: ProviderIQ has no accounts, and it doesn't keep what you type.
      </p>

      <section aria-labelledby="accounts">
        <h2 id="accounts">No accounts</h2>
        <p>
          There's no sign-up or sign-in, and ProviderIQ sets no cookies. Your search criteria are
          part of the page address, so they end up in your browser history like any other page.
        </p>
      </section>

      <section aria-labelledby="typing">
        <h2 id="typing">What you type</h2>
        <p>
          When you use "Describe what you need", your text is sent to Anthropic's API (Claude) for
          one purpose: turning it into search filters that you can review before searching. If AI
          interpretation is switched off, it's matched against keywords on ProviderIQ's own server
          instead. Anthropic handles what it receives under its own policies.
        </p>
        <p>
          ProviderIQ doesn't store or log that text. If it suggests you might be in crisis, the page
          shows helpline information; that isn't recorded either.
        </p>
      </section>

      <section aria-labelledby="logs">
        <h2 id="logs">What ProviderIQ records</h2>
        <p>For each search, a few anonymous details, to understand how the tool is used:</p>
        <ul className={styles.list}>
          <li>whether it came from the description box or the search form</li>
          <li>whether AI or keyword matching interpreted it</li>
          <li>the specialty, the state, the priority and the sort order you chose</li>
          <li>how many providers matched, and how long it took</li>
        </ul>
        <p>
          Never the text you typed, a condition, a city, or anything that identifies you. The server
          logs note which address was requested, the result and how long it took, without your
          search criteria or your IP address.
        </p>
        <p>
          To stop anyone sending too many requests, your IP address is held in memory for about a
          minute to count them. It's never stored, although the web server's error log can include
          it when a request is turned away.
        </p>
      </section>

      <section aria-labelledby="data">
        <h2 id="data">Where the provider data comes from</h2>
        <p>
          By default the providers are synthetic: fictional people generated for this demo. An
          optional mode uses real public data about New Jersey clinicians from the Centers for
          Medicare &amp; Medicaid Services (CMS); a banner on every page says so whenever it's on.
          No data about patients is used. More in the <Link to="/methodology">methodology</Link>.
        </p>
      </section>

      <section aria-labelledby="advice">
        <h2 id="advice">Not medical advice</h2>
        <p>
          ProviderIQ is an educational portfolio project. Its scores are illustrative, not a rating
          or a recommendation, and nothing here is medical advice. If you need care, talk to a
          licensed healthcare professional. In an emergency, call 911.
        </p>
      </section>

      <p className={styles.contact}>
        Questions? Open an issue on <a href={`${GITHUB_URL}/issues`}>GitHub</a>.
      </p>
    </article>
  )
}
