import { ThemeProvider } from './contexts/ThemeContext'
import { SettingsProvider } from './contexts/SettingsContext'
import { ToastProvider } from './contexts/ToastContext'
import { ViewProvider } from './contexts/ViewContext'
import { ProjectProvider } from './contexts/ProjectContext'
import { ChatProvider } from './contexts/ChatContext'
import { Sidebar } from './components/sidebar/Sidebar'
import { ToastContainer } from './components/common/ToastContainer'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import MainContent from './components/MainContent'
import './App.css'

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <SettingsProvider>
          <ToastProvider>
            <ViewProvider>
              <ProjectProvider>
                <ChatProvider>
                  <div className="app">
                    <ErrorBoundary
                      fallback={
                        <div style={{ padding: '2rem', textAlign: 'center' }}>
                          <p>Failed to load sidebar. Please refresh the page.</p>
                        </div>
                      }
                    >
                      <Sidebar />
                    </ErrorBoundary>
                    <div className="app__main">
                      <ErrorBoundary>
                        <MainContent />
                      </ErrorBoundary>
                    </div>
                  </div>
                  <ToastContainer />
                </ChatProvider>
              </ProjectProvider>
            </ViewProvider>
          </ToastProvider>
        </SettingsProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}

export default App
