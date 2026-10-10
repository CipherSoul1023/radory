import { useClerk, useUser } from '@clerk/react'
import { useQuery } from '@tanstack/react-query'
import { Building2, LogOut, UserRound, UsersRound } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useAuthenticatedRequest } from '../services/api'
import { useAppWorkspace } from '../services/appWorkspace'
import {
  formatWorkspaceRole,
  presentBrokerageProfile,
  type BrokerageProfile,
} from '../services/settings'

function SettingsField({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="settings-field">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function ValueList({
  values,
  empty = 'None selected',
}: {
  values: string[]
  empty?: string
}) {
  if (!values.length)
    return <span className="settings-empty-value">{empty}</span>
  return (
    <span className="settings-value-list">
      {values.map((value) => (
        <span key={value}>{value}</span>
      ))}
    </span>
  )
}

function ProfileLoading() {
  return (
    <div
      className="settings-loading"
      role="status"
      aria-label="Loading brokerage profile"
    >
      <span />
      <span />
      <span />
      <span />
    </div>
  )
}

function BrokerageProfileSection({ profile }: { profile: BrokerageProfile }) {
  const presented = presentBrokerageProfile(profile)

  return (
    <section
      className="settings-section"
      aria-labelledby="brokerage-profile-heading"
    >
      <div className="settings-section-heading">
        <span>
          <Building2 aria-hidden="true" size={20} />
        </span>
        <div>
          <h2 id="brokerage-profile-heading">Brokerage Profile</h2>
          <p>Your saved targeting profile and opportunity preferences.</p>
        </div>
      </div>

      <dl className="settings-details-grid">
        <SettingsField label="Brokerage name">
          {profile.brokerage_name}
        </SettingsField>
        <SettingsField label="Property sectors">
          <ValueList values={presented.propertySectors} />
        </SettingsField>
        <SettingsField label="Country">{profile.country}</SettingsField>
        <SettingsField label="Primary market">
          {profile.primary_market}
        </SettingsField>
        <SettingsField label="Submarkets">
          <ValueList
            values={presented.submarkets}
            empty="No submarkets selected"
          />
        </SettingsField>
        <SettingsField label="Tenant industries">
          <ValueList values={presented.tenantIndustries} />
        </SettingsField>
        <SettingsField label="Prospecting horizon">
          {presented.prospectingHorizon}
        </SettingsField>
        <SettingsField label="Opportunity types">
          <ValueList values={presented.opportunityTypes} />
        </SettingsField>
        <SettingsField label="Priority factors">
          <ValueList values={presented.priorityFactors} />
        </SettingsField>
      </dl>

      <div className="settings-transaction-block">
        <h3>Transaction size</h3>
        <dl className="settings-transaction-grid">
          <SettingsField label="Minimum">
            {presented.transactionSizes.minimum}
          </SettingsField>
          <SettingsField label="Ideal minimum">
            {presented.transactionSizes.idealMinimum}
          </SettingsField>
          <SettingsField label="Ideal maximum">
            {presented.transactionSizes.idealMaximum}
          </SettingsField>
          <SettingsField label="Maximum">
            {presented.transactionSizes.maximum}
          </SettingsField>
        </dl>
      </div>
    </section>
  )
}

export function SettingsPage() {
  const { organizationId, workspaceName, role } = useAppWorkspace()
  const request = useAuthenticatedRequest()
  const { isLoaded: userLoaded, user } = useUser()
  const { signOut } = useClerk()
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState('')
  const profile = useQuery({
    queryKey: ['brokerage-profile', organizationId],
    queryFn: () =>
      request<BrokerageProfile>('/api/workspace/brokerage-profile'),
    retry: 1,
  })
  const accountName =
    user?.fullName ||
    [user?.firstName, user?.lastName].filter(Boolean).join(' ') ||
    'Not provided'
  const accountEmail = user?.primaryEmailAddress?.emailAddress || 'Not provided'
  const roleLabel = formatWorkspaceRole(role)

  async function logOut() {
    setSigningOut(true)
    setSignOutError('')
    try {
      await signOut({ redirectUrl: '/' })
    } catch {
      setSignOutError('Unable to log out. Please try again.')
      setSigningOut(false)
    }
  }

  return (
    <section className="app-content-page settings-page">
      <header className="app-page-heading">
        <p className="app-page-eyebrow">Workspace preferences</p>
        <h1>Settings</h1>
        <p>Review your brokerage profile, account and active workspace.</p>
      </header>

      <div className="settings-sections">
        {profile.isPending ? (
          <section className="settings-section">
            <ProfileLoading />
          </section>
        ) : profile.isError ? (
          <section className="settings-section settings-error" role="alert">
            <h2>Unable to load your brokerage profile</h2>
            <p>
              Radory could not retrieve the saved profile for this workspace.
            </p>
            <button type="button" onClick={() => void profile.refetch()}>
              Try again
            </button>
          </section>
        ) : (
          <BrokerageProfileSection profile={profile.data} />
        )}

        <section className="settings-section" aria-labelledby="account-heading">
          <div className="settings-section-heading">
            <span>
              <UserRound aria-hidden="true" size={20} />
            </span>
            <div>
              <h2 id="account-heading">Account</h2>
              <p>Your Clerk account information for this signed-in session.</p>
            </div>
          </div>
          {userLoaded ? (
            <dl className="settings-details-grid settings-account-grid">
              <SettingsField label="Name">{accountName}</SettingsField>
              <SettingsField label="Email address">
                {accountEmail}
              </SettingsField>
              <SettingsField label="Workspace role">{roleLabel}</SettingsField>
            </dl>
          ) : (
            <ProfileLoading />
          )}
        </section>

        <section
          className="settings-section"
          aria-labelledby="workspace-heading"
        >
          <div className="settings-section-heading">
            <span>
              <UsersRound aria-hidden="true" size={20} />
            </span>
            <div>
              <h2 id="workspace-heading">Workspace</h2>
              <p>The active brokerage workspace for this session.</p>
            </div>
          </div>
          <dl className="settings-details-grid settings-account-grid">
            <SettingsField label="Workspace">{workspaceName}</SettingsField>
            <SettingsField label="Role">{roleLabel}</SettingsField>
            <SettingsField label="Membership">Active</SettingsField>
            <SettingsField label="Product focus">
              Tenant representation
            </SettingsField>
          </dl>
          <p className="settings-support-note">
            Radory currently supports tenant-representation workflows.
          </p>
        </section>

        <section
          className="settings-section settings-session"
          aria-labelledby="session-heading"
        >
          <div>
            <h2 id="session-heading">Account session</h2>
            <p>Sign out of Radory on this device.</p>
            {signOutError && (
              <p className="settings-signout-error" role="alert">
                {signOutError}
              </p>
            )}
          </div>
          <button
            className="settings-logout"
            disabled={signingOut}
            onClick={() => void logOut()}
            type="button"
          >
            <LogOut aria-hidden="true" size={18} />
            {signingOut ? 'Logging out…' : 'Log out'}
          </button>
        </section>
      </div>
    </section>
  )
}
