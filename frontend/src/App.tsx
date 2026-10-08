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
import { SignInPage } from './pages/SignInPage'
import { SignUpPage } from './pages/SignUpPage'

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
      {['/auth/continue', '/setup-workspace', '/app'].map((path) => (
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
    </Routes>
  )
}
