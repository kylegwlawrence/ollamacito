import { RouterProvider } from 'react-router-dom'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { router } from './router'
import { useSettingsAutoLoad } from './stores/settingsStore'
import { useProjectsAutoLoad } from './stores/projectsStore'
import { useRagServersAutoLoad } from './stores/ragServersStore'
import { useThemeSync } from './stores/themeStore'
import './App.css'

function App() {
  useSettingsAutoLoad()
  useProjectsAutoLoad()
  useRagServersAutoLoad()
  useThemeSync()

  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  )
}

export default App
