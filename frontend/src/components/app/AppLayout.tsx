import { Outlet } from 'react-router-dom'
import type { AppWorkspaceContext } from '../../services/appWorkspace'
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
        <Outlet context={{ organizationId, workspaceName, role }} />
      </main>
    </div>
  )
}
