import { useView } from '@/contexts/ViewContext'
import { ChatContainer } from './chat/ChatContainer'
import { ProjectDetail } from './projects/ProjectDetail'
import { ProjectSettings } from './projects/ProjectSettings'

const MainContent = () => {
  const { viewType } = useView()

  switch (viewType) {
    case 'chat':
      return <ChatContainer />
    case 'project-detail':
      return <ProjectDetail />
    case 'project-settings':
      return <ProjectSettings />
    default:
      return <ChatContainer />
  }
}

export default MainContent
