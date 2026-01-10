import { ThemeProvider } from './contexts/ThemeContext'
import { ChatProvider } from './contexts/ChatContext'
import { SettingsProvider } from './contexts/SettingsContext'
import { Sidebar } from './components/sidebar/Sidebar'
import { ChatContainer } from './components/chat/ChatContainer'
import './App.css'

function App() {
  return (
    <ThemeProvider>
      <SettingsProvider>
        <ChatProvider>
          <div className="app">
            <Sidebar />
            <div className="app__main">
              <ChatContainer />
            </div>
          </div>
        </ChatProvider>
      </SettingsProvider>
    </ThemeProvider>
  )
}

export default App
