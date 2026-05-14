/**
 * App routes (PLAN_NEW.md Phase 5).
 *
 * The previous custom ViewContext switch is gone; each top-level view is
 * its own URL so refresh works, deep-links work, and browser back/forward
 * navigate as expected.
 */
import { createBrowserRouter, Outlet } from 'react-router-dom'

import { ConfirmDialog } from './components/common/ConfirmDialog'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { ToastContainer } from './components/common/ToastContainer'
import { Sidebar } from './components/sidebar/Sidebar'
import { ChatContainer } from './components/chat/ChatContainer'
import { ProjectDetail } from './components/projects/ProjectDetail'
import { AppSettings } from './components/settings/AppSettings'

/**
 * Shell layout: persistent sidebar + a main pane that renders the active
 * route. Each route also gets its own ErrorBoundary so a crash in one
 * view does not blow away the sidebar.
 */
const RootLayout = () => {
  return (
    <>
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
            <Outlet />
          </ErrorBoundary>
        </div>
      </div>
      <ToastContainer />
      <ConfirmDialog />
    </>
  )
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <ChatContainer /> },
      { path: 'chats/:chatId', element: <ChatContainer /> },
      { path: 'projects/:projectId', element: <ProjectDetail /> },
      { path: 'settings', element: <AppSettings /> },
    ],
  },
])
