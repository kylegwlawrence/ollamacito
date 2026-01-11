import { useView } from '@/contexts/ViewContext'
import { ChatContainer } from './chat/ChatContainer'
import { ProjectDetail } from './projects/ProjectDetail'
import { ProjectSettings } from './projects/ProjectSettings'
import { ErrorBoundary } from './common/ErrorBoundary'

const MainContent = () => {
  const { viewType, navigateToChat } = useView()

  switch (viewType) {
    case 'chat':
      return (
        <ErrorBoundary onReset={() => navigateToChat()}>
          <ChatContainer />
        </ErrorBoundary>
      )
    case 'project-detail':
      return (
        <ErrorBoundary onReset={() => navigateToChat()}>
          <ProjectDetail />
        </ErrorBoundary>
      )
    case 'project-settings':
      return (
        <ErrorBoundary onReset={() => navigateToChat()}>
          <ProjectSettings />
        </ErrorBoundary>
      )
    default:
      return (
        <ErrorBoundary onReset={() => navigateToChat()}>
          <ChatContainer />
        </ErrorBoundary>
      )
  }
}

export default MainContent
