import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <section>
      <title>Page not found · ProviderIQ</title>
      <h1>Page not found</h1>
      <p>That page doesn't exist.</p>
      <Link to="/">Back to search</Link>
    </section>
  )
}
