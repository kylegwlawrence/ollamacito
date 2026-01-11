import { ThemeProvider } from './contexts/ThemeContext'
import { SettingsProvider } from './contexts/SettingsContext'
import { ViewProvider } from './contexts/ViewContext'
import { ProjectProvider } from './contexts/ProjectContext'
import { ChatProvider } from './contexts/ChatContext'
import { Sidebar } from './components/sidebar/Sidebar'
import MainContent from './components/MainContent'
import './App.css'

function App() {
  return (
    <ThemeProvider>
      <SettingsProvider>
        <ViewProvider>
          <ProjectProvider>
            <ChatProvider>
              <div className="app">
                <Sidebar />
                <div className="app__main">
                  <MainContent />
                </div>
              </div>
            </ChatProvider>
          </ProjectProvider>
        </ViewProvider>
      </SettingsProvider>
    </ThemeProvider>
  )
}

export default App
