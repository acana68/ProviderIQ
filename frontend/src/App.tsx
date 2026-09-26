import { Route, Routes } from 'react-router'
import { AppLayout } from './components/layout/AppLayout'
import { MethodologyPage } from './pages/MethodologyPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProviderDetailPage } from './pages/ProviderDetailPage'
import { ResultsPage } from './pages/ResultsPage'
import { SearchPage } from './pages/SearchPage'

/** All routes, inside the shared layout. The router itself is provided by main.tsx (or a test). */
export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<SearchPage />} />
        <Route path="results" element={<ResultsPage />} />
        <Route path="providers/:providerId" element={<ProviderDetailPage />} />
        <Route path="methodology" element={<MethodologyPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
