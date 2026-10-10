import { useOutletContext } from 'react-router-dom'

export type AppWorkspaceContext = {
  organizationId: string
  workspaceName: string
  role: string
}

export function useAppWorkspace() {
  return useOutletContext<AppWorkspaceContext>()
}
