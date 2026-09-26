import { useParams } from 'react-router'

export function ProviderDetailPage() {
  const { providerId } = useParams<{ providerId: string }>()

  return (
    <section>
      <title>Provider · ProviderIQ</title>
      <h1>Provider {providerId}</h1>
      <p>Provider details, score breakdown, and explanation will appear here.</p>
    </section>
  )
}
