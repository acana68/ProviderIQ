import { Route, Routes } from 'react-router'
import { AppLayout } from './components/layout/AppLayout'
import { CrisisProvider } from './components/layout/CrisisProvider'
import { DatasetProvider } from './components/layout/DatasetProvider'
import { MethodologyPage } from './pages/MethodologyPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PrivacyPage } from './pages/PrivacyPage'
import { ProviderDetailPage } from './pages/ProviderDetailPage'
import { ResultsPage } from './pages/ResultsPage'
import { SearchPage } from './pages/SearchPage'

/**
 * All routes, inside the shared layout, with the dataset and the crisis banner's state
 * shared by every page. The router itself is provided by main.tsx (or a test).
 */
export function App() {
  return (
    <DatasetProvider>
      <CrisisProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<SearchPage />} />
            <Route path="results" element={<ResultsPage />} />
            <Route path="providers/:providerId" element={<ProviderDetailPage />} />
            <Route path="methodology" element={<MethodologyPage />} />
            <Route path="privacy" element={<PrivacyPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </CrisisProvider>
    </DatasetProvider>
  )
}
