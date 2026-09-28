import { Link } from 'react-router'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { useDataset } from '../hooks/useDataset'
import { useRankingWeights } from '../hooks/useReferenceData'
import { COMPONENT_NAMES } from '../types/provider'
import type { RankingWeightsResponse } from '../types/ranking'
import { PRIORITIES } from '../types/search'
import { formatWeight } from '../utils/format'
import type { Labels } from '../utils/labels'
import styles from './MethodologyPage.module.css'

const REPO_URL = 'https://github.com/acana68/ProviderIQ'
const DATA_QUALITY_URL = `${REPO_URL}/blob/main/docs/data-quality.md`

type Section = readonly [id: string, title: string]

const SECTIONS: Section[] = [
  ['about', 'What ProviderIQ is'],
  ['ai', 'How AI is used'],
  ['factors', 'The five factors'],
  ['priorities', 'Priorities and weights'],
  ['standouts', 'How "Stands out for…" is chosen'],
  ['limitations', 'Limitations'],
]
/** With real (CMS) data, "About the real data" comes right after "What ProviderIQ is". */
const CMS_SECTIONS: Section[] = [
  ...SECTIONS.slice(0, 1),
  ['real-data', 'About the real data'],
  ...SECTIONS.slice(1),
]

interface Factor {
  factor: string
  how: string
  why: string
}

const DISTANCE_FACTOR: Factor = {
  factor: 'Distance',
  how: 'Compared with your search radius: next door scores 1, the edge of the radius scores 0.',
  why: '"Close" depends on the search: 5 miles is far in a 6-mile search but near in a 50-mile one.',
}

const FACTORS: Factor[] = [
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
  DISTANCE_FACTOR,
]

/** The same five factors as the CMS data scores them, named by `labels`. */
function cmsFactors(labels: Labels): Factor[] {
  const names = labels.components
  return [
    {
      factor: names.quality,
      how: "The clinician's MIPS final score (0–100) as it is: 88 counts as 0.88. A clinician without one is scored as their specialty's median.",
      why: "It's already on a fixed scale. Scoring a missing score as the median keeps missing data neutral.",
    },
    {
      factor: names.experience,
      how: 'Years since graduating from medical school, on a logarithmic curve that levels off at 30 years.',
      why: 'Early years matter most. It counts residency too, so it overstates independent practice a little.',
    },
    {
      factor: names.cost,
      how: 'The share of New Jersey clinicians in the same specialty who spend more per Medicare patient: lower spending scores higher.',
      why: 'Real spending is very uneven, so a fixed scale would pin about a third of clinicians at the extremes. A ranking within the specialty stays fair.',
    },
    {
      factor: names.volume,
      how: "The clinician's Medicare-patient count as a percentile within their specialty.",
      why: 'Specialties see very different numbers of patients, and only Medicare patients are counted.',
    },
    DISTANCE_FACTOR,
  ]
}

export function MethodologyPage() {
  const { dataset, isCms, labels, minSpendingPatients } = useDataset()
  const sections = isCms ? CMS_SECTIONS : SECTIONS
  const factors = isCms ? cmsFactors(labels) : FACTORS
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
            {sections.map(([id, title]) => (
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
        {isCms ? (
          <p>
            <strong>The providers are real New Jersey physicians</strong>, from public CMS data.
            Scores are computed by ProviderIQ to illustrate the method. They aren't a rating or
            endorsement of any clinician by ProviderIQ or CMS, and nothing here is medical advice.
          </p>
        ) : (
          <p>
            <strong>All provider data is synthetic.</strong> The providers are generated, not real
            people, and nothing here is medical advice.
          </p>
        )}
      </section>

      {isCms && (
        <RealDataSection
          asOf={dataset?.as_of ?? null}
          labels={labels}
          minSpendingPatients={minSpendingPatients}
        />
      )}

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
              {factors.map(({ factor, how, why }) => (
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
        <WeightTable labels={labels} isCms={isCms} />
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
        {isCms ? (
          <p>
            <strong>
              Apart from {labels.components.cost}, these percentiles never affect the score.
            </strong>{' '}
            Spending is scored as a percentile within the specialty, so the same percentile is both
            its score and its wording. A value that wasn't reported never makes a clinician stand
            out.
          </p>
        ) : (
          <p>
            <strong>These percentiles never affect the score.</strong> They only choose the wording;
            the score and the order are the same without them.
          </p>
        )}
      </section>

      <section id="limitations" aria-labelledby="limitations-heading">
        <h2 id="limitations-heading">Limitations</h2>
        {isCms ? <CmsLimitations /> : <SyntheticLimitations />}
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

/** "About the real data": where each number comes from and how gaps are handled. */
interface RealDataSectionProps {
  asOf: string | null
  labels: Labels
  /** From GET /dataset; null if it didn't say. */
  minSpendingPatients: number | null
}

function RealDataSection({ asOf, labels, minSpendingPatients }: RealDataSectionProps) {
  const names = labels.metrics
  return (
    <section id="real-data" aria-labelledby="real-data-heading">
      <h2 id="real-data-heading">About the real data</h2>
      <p>
        Every clinician is a New Jersey MD or DO in one of ten specialties who billed Medicare in
        2024{asOf && <> (files downloaded {asOf})</>}. The data comes from:
      </p>
      <ul className={styles.list}>
        <li>
          <strong>Doctors and Clinicians National Downloadable File</strong> (CMS Provider Data
          Catalog): name, specialty, practice ZIP code and medical school graduation year.
        </li>
        <li>
          <strong>PY 2024 Clinician Public Reporting: Overall MIPS Performance</strong> (CMS
          Provider Data Catalog): MIPS final scores.
        </li>
        <li>
          <strong>Medicare Physician &amp; Other Practitioners – by Provider</strong>, calendar year
          2024 (data.cms.gov): Medicare patients and Medicare allowed amounts.
        </li>
        <li>
          <strong>U.S. Census Bureau</strong> Gazetteer files and population estimates: ZIP code
          locations and the cities you can search from.
        </li>
      </ul>

      <h3 className={styles.subheading}>What each number really measures</h3>
      <dl className={styles.definitions}>
        <dt>{names.quality_score}</dt>
        <dd>
          CMS's Merit-based Incentive Payment System score (0–100) for 2024. It's a payment program
          score that blends quality measures, improvement activities, interoperability and cost, not
          a direct measure of how good someone's care is. Clinicians exempt from MIPS, or in some
          alternative payment models, have none.
        </dd>
        <dt>{names.years_experience}</dt>
        <dd>Years since graduating from medical school, so residency counts too.</dd>
        <dt>{names.cost_index}</dt>
        <dd>
          What Medicare allowed for the clinician's medical (non-drug) services, per Medicare
          patient, compared with other New Jersey clinicians in the same specialty. It isn't a
          price, and it isn't adjusted for how sick the patients are.
        </dd>
        <dt>{names.patient_volume}</dt>
        <dd>
          Medicare fee-for-service patients seen in 2024. Medicare Advantage, Medicaid and privately
          insured patients aren't counted.
        </dd>
        <dt>Not published per clinician</dt>
        <dd>Complication and readmission rates, conditions treated, and new-patient status.</dd>
      </dl>

      <h3 className={styles.subheading}>How gaps and quirks are handled</h3>
      <ul className={styles.list}>
        <li>
          <strong>A MIPS final score of 0 counts as not reported.</strong> Under CMS's scoring rules
          it means nothing that could be scored was submitted, not that care was as bad as possible.
        </li>
        <li>
          <strong>Spending leaves out Part B drugs</strong> (chemotherapy, infusions, injections),
          which mostly reflect the condition being treated rather than the clinician's choices. It
          is scored as a percentile: the share of specialty peers who spend more.
        </li>
        <li>
          <strong>
            {minSpendingPatients === null
              ? 'Spending needs enough patients.'
              : `Spending needs at least ${minSpendingPatients} patients.`}
          </strong>{' '}
          With fewer, one unusually sick or healthy patient decides the average, so it's treated as
          not reported. It's also not reported when CMS suppressed the amounts for privacy.
        </li>
        <li>
          <strong>A missing value is scored as the specialty median</strong> and shown as "Not
          reported". Leaving the factor out would reward missing data, and scoring it as zero would
          punish clinicians for what CMS didn't publish. The median is neutral: it never beats a
          real above-median value. A missing value never makes a clinician stand out, and a search
          can be limited to clinicians with a quality score.
        </li>
      </ul>
      <p>
        Row counts, match rates and every dropped record are in the{' '}
        <a href={DATA_QUALITY_URL} target="_blank" rel="noreferrer">
          data-quality report
        </a>
        .
      </p>
    </section>
  )
}

function SyntheticLimitations() {
  return (
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
        <strong>Approximate locations.</strong> Distances are straight lines from the city center,
        not driving distances, and providers are placed at generated points around their city.
      </li>
      <li>
        <strong>Not medical advice.</strong> A score here can't tell you which provider is right for
        you. Talk to a medical professional.
      </li>
    </ul>
  )
}

function CmsLimitations() {
  return (
    <ul className={styles.list}>
      <li>
        <strong>Medicare only.</strong> Patient counts and spending cover Medicare fee-for-service
        patients in 2024, not a clinician's whole practice.
      </li>
      <li>
        <strong>Partial coverage.</strong> Many clinicians have no MIPS score, and some have no
        usable spending figure. Those are scored as their specialty's median.
      </li>
      <li>
        <strong>Approximate locations.</strong> Clinicians are placed at the center of their
        practice ZIP code, and distances are straight lines from the city center.
      </li>
      <li>
        <strong>Not a rating, and not medical advice.</strong> A score here can't tell you which
        clinician is right for you. Talk to a medical professional.
      </li>
    </ul>
  )
}

/** The weight profiles from GET /ranking/weights, one row per priority. */
function WeightTable({ labels, isCms }: { labels: Labels; isCms: boolean }) {
  const weights = useRankingWeights()

  if (weights.error) {
    return (
      <ErrorState title="Couldn't load the weights" error={weights.error} onRetry={weights.retry} />
    )
  }
  if (!weights.data) return <LoadingState label="Loading the weights…" />
  return <WeightTableBody weights={weights.data} labels={labels} isCms={isCms} />
}

function WeightTableBody({
  weights,
  labels,
  isCms,
}: {
  weights: RankingWeightsResponse
  labels: Labels
  isCms: boolean
}) {
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
                  {labels.components[name]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PRIORITIES.map((priority) => (
              <tr key={priority}>
                <th scope="row">{labels.priorities[priority]}</th>
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
        <strong>
          {labels.components.quality} never drops below {formatWeight(weights.min_quality_weight)}.
        </strong>{' '}
        {isCms
          ? "Even a search focused on spending or distance can't push a clinician with a low MIPS score to the top just because they spend less or are close."
          : "Even a search focused on cost or distance can't push a low-quality provider to the top just because they're cheap or close."}
      </p>
      <p>
        Without a location there's no distance to score, so distance is dropped and the other
        weights are scaled up to add up to 100% again, keeping their proportions.
      </p>
    </>
  )
}
