import { RouterProvider } from 'react-router-dom'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { router } from './router'
import { useSettingsAutoLoad } from './stores/settingsStore'
import { useProjectsAutoLoad } from './stores/projectsStore'
import './App.css'

function App() {
  // Hydrate the global stores on first mount; routes assume they are loaded.
  useSettingsAutoLoad()
  useProjectsAutoLoad()

  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  )
}

export default App
