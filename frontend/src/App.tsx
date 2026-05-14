import { RouterProvider } from 'react-router-dom'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { router } from './router'
import { useSettingsAutoLoad } from './stores/settingsStore'
import { useProjectsAutoLoad } from './stores/projectsStore'
import { useThemeSync } from './stores/themeStore'
import './App.css'

function App() {
  useSettingsAutoLoad()
  useProjectsAutoLoad()
  useThemeSync()

  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  )
}

export default App
