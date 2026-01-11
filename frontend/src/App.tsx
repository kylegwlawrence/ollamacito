import { ThemeProvider } from './contexts/ThemeContext'
import { SettingsProvider } from './contexts/SettingsContext'
import { ToastProvider } from './contexts/ToastContext'
import { ViewProvider } from './contexts/ViewContext'
import { ProjectProvider } from './contexts/ProjectContext'
import { ChatProvider } from './contexts/ChatContext'
import { Sidebar } from './components/sidebar/Sidebar'
import { ToastContainer } from './components/common/ToastContainer'
import MainContent from './components/MainContent'
import './App.css'

function App() {
  return (
    <ThemeProvider>
      <SettingsProvider>
        <ToastProvider>
          <ViewProvider>
            <ProjectProvider>
              <ChatProvider>
                <div className="app">
                  <Sidebar />
                  <div className="app__main">
                    <MainContent />
                  </div>
                </div>
                <ToastContainer />
              </ChatProvider>
            </ProjectProvider>
          </ViewProvider>
        </ToastProvider>
      </SettingsProvider>
    </ThemeProvider>
  )
}

export default App
