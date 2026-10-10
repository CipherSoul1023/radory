import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import {
  AuthEntry,
  AuthReady,
  SsoCallbackPage,
  WorkspaceGate,
} from './components/auth/AuthRouting'
import { AcceptInvitationPage } from './pages/AcceptInvitationPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LandingPage } from './pages/LandingPage'
import { CompaniesPage } from './pages/CompaniesPage'
import { MarketActivityPage } from './pages/MarketActivityPage'
import { OpportunitiesPage } from './pages/OpportunitiesPage'
import { SettingsPage } from './pages/SettingsPage'
import { SignInPage } from './pages/SignInPage'
import { SignUpPage } from './pages/SignUpPage'
import { WatchlistPage } from './pages/WatchlistPage'
import { WorkspaceDashboardPage } from './pages/WorkspaceDashboardPage'

export default function App() {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const invitation =
    params.has('__clerk_ticket') || params.get('__clerk_status') === 'complete'
  const invitationSignUp =
    location.pathname === '/sign-up' &&
    params.has('__clerk_ticket') &&
    params.get('__clerk_status') === 'sign_up'
  if (
    invitation &&
    location.pathname !== '/accept-invitation' &&
    !invitationSignUp
  )
    return <Navigate to={`/accept-invitation${location.search}`} replace />
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/sign-in"
        element={
          <AuthReady>
            <AuthEntry>
              <SignInPage />
            </AuthEntry>
          </AuthReady>
        }
      />
      <Route
        path="/sign-up"
        element={
          <AuthReady>
            {invitationSignUp ? (
              <SignUpPage />
            ) : (
              <AuthEntry>
                <SignUpPage />
              </AuthEntry>
            )}
          </AuthReady>
        }
      />
      <Route
        path="/forgot-password"
        element={
          <AuthReady>
            <ForgotPasswordPage />
          </AuthReady>
        }
      />
      <Route
        path="/sso-callback"
        element={
          <AuthReady>
            <SsoCallbackPage />
          </AuthReady>
        }
      />
      <Route
        path="/accept-invitation"
        element={
          <AuthReady>
            <AcceptInvitationPage />
          </AuthReady>
        }
      />
      {['/auth/continue', '/setup-workspace'].map((path) => (
        <Route
          key={path}
          path={path}
          element={
            <AuthReady>
              <WorkspaceGate />
            </AuthReady>
          }
        />
      ))}
      <Route
        path="/app"
        element={
          <AuthReady>
            <WorkspaceGate />
          </AuthReady>
        }
      >
        <Route index element={<WorkspaceDashboardPage />} />
        <Route path="opportunities" element={<OpportunitiesPage />} />
        <Route path="companies" element={<CompaniesPage />} />
        <Route path="market-activity" element={<MarketActivityPage />} />
        <Route path="watchlist" element={<WatchlistPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Route>
    </Routes>
  )
}
