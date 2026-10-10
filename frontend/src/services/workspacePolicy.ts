export type Membership = {
  organization: { id: string; name: string }
  role: string
}
export type WorkspaceDecision =
  | { kind: 'setup' }
  | { kind: 'invitation-pending' }
  | { kind: 'choose' }
  | { kind: 'activate'; organizationId: string }
  | { kind: 'app'; organizationId: string }

// Called only after a fresh, complete membership fetch. A failed request is never zero memberships.
export function workspaceDecision(
  memberships: Membership[],
  activeId: string | null | undefined,
  invited: boolean,
): WorkspaceDecision {
  if (!memberships.length)
    return { kind: invited ? 'invitation-pending' : 'setup' }
  if (
    activeId &&
    memberships.some(({ organization }) => organization.id === activeId)
  )
    return { kind: 'app', organizationId: activeId }
  if (memberships.length === 1)
    return { kind: 'activate', organizationId: memberships[0].organization.id }
  return { kind: 'choose' }
}
