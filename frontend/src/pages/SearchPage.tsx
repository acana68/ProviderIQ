import { type FormEvent, useId, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { CriteriaEditor } from '../components/search/CriteriaEditor'
import { NaturalLanguageSearch } from '../components/search/NaturalLanguageSearch'
import type { ParseQueryResponse, ParserUsed, SearchCriteria } from '../types/search'
import {
  INITIAL_CRITERIA,
  criteriaForEditor,
  criteriaForSearch,
  criteriaFromParsed,
} from '../utils/criteria'
import { criteriaToSearchParams, searchParamsToCriteria } from '../utils/searchParams'
import styles from './SearchPage.module.css'

export function SearchPage() {
  const navigate = useNavigate()
  // Starts from the URL, so "Change search" on the results page comes back to the same
  // criteria (the URL is only read once; editing doesn't write it back).
  const [params] = useSearchParams()
  const [fromUrl] = useState(() => searchParamsToCriteria(params))
  const [criteria, setCriteria] = useState<SearchCriteria>(() => criteriaForEditor(fromUrl))
  // Set once the criteria came from Interpret. They stay "nl" even if edited afterwards:
  // the description is still where they came from.
  const [parserUsed, setParserUsed] = useState<ParserUsed | null>(fromUrl.parser_used ?? null)
  const headingId = useId()

  function handleParsed(result: ParseQueryResponse) {
    setCriteria(criteriaFromParsed(result.criteria))
    setParserUsed(result.parser_used)
  }

  function handleReset() {
    setCriteria(INITIAL_CRITERIA)
    setParserUsed(null)
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const origin: SearchCriteria = parserUsed
      ? { source: 'nl', parser_used: parserUsed }
      : { source: 'manual' }
    const params = criteriaToSearchParams({ ...criteriaForSearch(criteria), ...origin })
    navigate(`/results?${params}`)
  }

  return (
    <div className={styles.page}>
      <header>
        <h1>ProviderIQ</h1>
        <p className={styles.lead}>
          Find and compare healthcare providers by quality, experience, cost, and distance.
        </p>
      </header>

      <NaturalLanguageSearch onParsed={handleParsed} />

      <form className={styles.card} aria-labelledby={headingId} onSubmit={handleSearch}>
        <h2 id={headingId} className={styles.cardHeading}>
          Search criteria
        </h2>
        <CriteriaEditor value={criteria} onChange={setCriteria} />
        <div className={styles.actions}>
          <button type="button" className={styles.secondary} onClick={handleReset}>
            Reset
          </button>
          <button type="submit" className={styles.primary}>
            Search providers
          </button>
        </div>
      </form>
    </div>
  )
}
