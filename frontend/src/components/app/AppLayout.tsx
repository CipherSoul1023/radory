import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import type { AppWorkspaceContext } from '../../services/appWorkspace'
import { AppContentLoader } from './AppContentLoader'
import { AppSidebar } from './AppSidebar'
import { AppTopbar } from './AppTopbar'
import '../appShell.css'

export function AppLayout({
  organizationId,
  workspaceName,
  role,
}: AppWorkspaceContext) {
  return (
    <div className="workspace-dashboard">
      <AppSidebar />
      <main className="workspace-dashboard-main">
        <AppTopbar workspaceName={workspaceName} />
        <Suspense fallback={<AppContentLoader />}>
          <Outlet context={{ organizationId, workspaceName, role }} />
        </Suspense>
      </main>
    </div>
  )
}
