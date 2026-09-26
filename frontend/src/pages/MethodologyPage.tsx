import { Link } from 'react-router'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { useRankingWeights } from '../hooks/useReferenceData'
import { COMPONENT_NAMES } from '../types/provider'
import type { RankingWeightsResponse } from '../types/ranking'
import { PRIORITIES } from '../types/search'
import { formatWeight } from '../utils/format'
import { COMPONENT_LABELS, PRIORITY_LABELS } from '../utils/labels'
import styles from './MethodologyPage.module.css'

const REPO_URL = 'https://github.com/acana68/ProviderIQ'

const SECTIONS = [
  ['about', 'What ProviderIQ is'],
  ['ai', 'How AI is used'],
  ['factors', 'The five factors'],
  ['priorities', 'Priorities and weights'],
  ['standouts', 'How "Stands out for…" is chosen'],
  ['limitations', 'Limitations'],
] as const

const FACTORS: { factor: string; how: string; why: string }[] = [
  {
    factor: 'Quality',
    how: 'The quality score (0–100) as it is: 88 counts as 0.88.',
    why: "It's already a rating on a fixed scale, where 10 points mean the same anywhere, so it needs no reshaping.",
  },
  {
    factor: 'Experience',
    how: 'A logarithmic curve that levels off at 30 years: 5 years ≈ 0.52, 10 ≈ 0.70, 20 ≈ 0.89.',
    why: 'Early years matter most. Going from 2 to 10 years says far more than going from 20 to 28.',
  },
  {
    factor: 'Cost',
    how: 'Compared with the regional average: average cost scores 0.5, half the average scores 1, and 50% above it scores 0.',
    why: 'Prices differ by region, so a provider is judged against the local average, not a national figure.',
  },
  {
    factor: 'Volume',
    how: "The provider's patient-volume percentile within their own specialty.",
    why: 'Primary care sees thousands of patients a year and oncology hundreds, so raw counts across specialties would be meaningless.',
  },
  {
    factor: 'Distance',
    how: 'Compared with your search radius: next door scores 1, the edge of the radius scores 0.',
    why: '"Close" depends on the search: 5 miles is far in a 6-mile search but near in a 50-mile one.',
  },
]

export function MethodologyPage() {
  return (
    <article className={styles.page}>
      <title>Methodology · ProviderIQ</title>
      <header>
        <h1>Methodology</h1>
        <p className={styles.lead}>
          How ProviderIQ turns what you ask for into a ranked, explained list of providers.
        </p>
        <nav aria-label="On this page" className={styles.toc}>
          <ol>
            {SECTIONS.map(([id, title]) => (
              <li key={id}>
                <a href={`#${id}`}>{title}</a>
              </li>
            ))}
          </ol>
        </nav>
      </header>

      <section id="about" aria-labelledby="about-heading">
        <h2 id="about-heading">What ProviderIQ is</h2>
        <p>
          ProviderIQ is an educational portfolio project. It shows how a provider search could be
          transparent: describe what you need, check the filters, and get a ranked list in which
          every score can be taken apart and explained.
        </p>
        <p>
          <strong>All provider data is synthetic.</strong> The providers are generated, not real
          people, and nothing here is medical advice.
        </p>
      </section>

      <section id="ai" aria-labelledby="ai-heading">
        <h2 id="ai-heading">How AI is used</h2>
        <p>AI has one small job, and the rest of the app is ordinary, predictable code.</p>
        <ul className={styles.list}>
          <li>
            <strong>It only turns your sentence into filters</strong>, such as specialty, condition,
            location, minimums and priority.
          </li>
          <li>
            <strong>You can edit them.</strong> The filters appear in the search form, and nothing
            is searched until you press Search.
          </li>
          <li>
            <strong>It never ranks providers or touches the database.</strong> It never sees
            provider data. Ranking is deterministic code: the same search always gives the same
            order.
          </li>
          <li>
            <strong>There's a keyword fallback.</strong> If the AI is unavailable, slow, or answers
            with something invalid, simple keyword matching fills in the filters instead, and the
            page says "Keyword matching".
          </li>
        </ul>
      </section>

      <section id="factors" aria-labelledby="factors-heading">
        <h2 id="factors-heading">The five factors</h2>
        <p>
          Each factor is turned into a number from 0 to 1, where higher is always better, then
          multiplied by its weight and by 100. The points add up to the match score out of 100. A
          provider's score never depends on who else matched the search.
        </p>
        <div className={styles.scroll}>
          <table className={styles.table}>
            <caption className="visually-hidden">How each factor is scored</caption>
            <thead>
              <tr>
                <th scope="col">Factor</th>
                <th scope="col">How it's scored</th>
                <th scope="col">Why</th>
              </tr>
            </thead>
            <tbody>
              {FACTORS.map(({ factor, how, why }) => (
                <tr key={factor}>
                  <th scope="row">{factor}</th>
                  <td>{how}</td>
                  <td>{why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section id="priorities" aria-labelledby="priorities-heading">
        <h2 id="priorities-heading">Priorities and weights</h2>
        <p>
          The priority you pick decides how much each factor counts. These are the weights the
          ranking engine uses, loaded from it directly:
        </p>
        <WeightTable />
      </section>

      <section id="standouts" aria-labelledby="standouts-heading">
        <h2 id="standouts-heading">How "Stands out for…" is chosen</h2>
        <p>
          A result's explanation can start with "Stands out for…". It names the factor on which the
          provider ranks highest <strong>against the other providers in their specialty</strong>{' '}
          (their peer percentile), but only if they beat at least <strong>80%</strong> of those
          peers on it. Otherwise it says "No single standout factor", which is common by design.
        </p>
        <p>
          Distance has no peer group, so it only counts when the provider is within the nearest
          fifth of your radius. The sentence comes from fixed templates, not from AI, so it can only
          say what the data supports.
        </p>
        <p>
          <strong>These percentiles never affect the score.</strong> They only choose the wording;
          the score and the order are the same without them.
        </p>
      </section>

      <section id="limitations" aria-labelledby="limitations-heading">
        <h2 id="limitations-heading">Limitations</h2>
        <ul className={styles.list}>
          <li>
            <strong>Synthetic data.</strong> Every provider, score and rate is generated. None of it
            describes a real person or practice.
          </li>
          <li>
            <strong>A fixed list of about 25 cities.</strong> Searches can only be centered on those
            cities.
          </li>
          <li>
            <strong>Approximate locations.</strong> Distances are straight lines from the city
            center, not driving distances, and providers are placed at generated points around their
            city.
          </li>
          <li>
            <strong>Not medical advice.</strong> A score here can't tell you which provider is right
            for you. Talk to a medical professional.
          </li>
        </ul>
      </section>

      <footer className={styles.footer}>
        <p>
          The code, including the ranking engine and its tests, is on{' '}
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
          . <Link to="/">Start a search</Link>
        </p>
      </footer>
    </article>
  )
}

/** The weight profiles from GET /ranking/weights, one row per priority. */
function WeightTable() {
  const weights = useRankingWeights()

  if (weights.error) {
    return (
      <ErrorState title="Couldn't load the weights" error={weights.error} onRetry={weights.retry} />
    )
  }
  if (!weights.data) return <LoadingState label="Loading the weights…" />
  return <WeightTableBody weights={weights.data} />
}

function WeightTableBody({ weights }: { weights: RankingWeightsResponse }) {
  return (
    <>
      <div className={styles.scroll}>
        <table className={`${styles.table} ${styles.weights}`}>
          <caption className="visually-hidden">Weight of each factor, by priority</caption>
          <thead>
            <tr>
              <th scope="col">Priority</th>
              {COMPONENT_NAMES.map((name) => (
                <th key={name} scope="col" className={styles.number}>
                  {COMPONENT_LABELS[name]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PRIORITIES.map((priority) => (
              <tr key={priority}>
                <th scope="row">{PRIORITY_LABELS[priority]}</th>
                {COMPONENT_NAMES.map((name) => (
                  <td key={name} className={styles.number}>
                    {formatWeight(weights.profiles[priority][name])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <strong>Quality never drops below {formatWeight(weights.min_quality_weight)}.</strong> Even
        a search focused on cost or distance can't push a low-quality provider to the top just
        because they're cheap or close.
      </p>
      <p>
        Without a location there's no distance to score, so distance is dropped and the other
        weights are scaled up to add up to 100% again, keeping their proportions.
      </p>
    </>
  )
}
