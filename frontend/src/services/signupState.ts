const ACTIVE_SIGNUP_ATTEMPT = 'signup_attempt'
const NEW_SIGNUP_INTENT = 'new'

export type SignUpEntryAction =
  | 'reset-to-form'
  | 'show-form'
  | 'show-verification'
  | 'continue'

export function hasActiveSignUpAttempt(search: string | URLSearchParams) {
  const params =
    typeof search === 'string' ? new URLSearchParams(search) : search
  return params.get(ACTIVE_SIGNUP_ATTEMPT) === 'active'
}

export function hasNewSignUpIntent(search: string | URLSearchParams) {
  const params =
    typeof search === 'string' ? new URLSearchParams(search) : search
  return params.get(NEW_SIGNUP_INTENT) === '1'
}

export function withNewSignUpIntent(path: string) {
  const [pathname, search = ''] = path.split('?', 2)
  const params = new URLSearchParams(search)
  params.set(NEW_SIGNUP_INTENT, '1')
  return `${pathname}?${params.toString()}`
}

export function withActiveSignUpAttempt(path: string) {
  const [pathname, search = ''] = path.split('?', 2)
  const params = new URLSearchParams(search)
  params.set(ACTIVE_SIGNUP_ATTEMPT, 'active')
  return `${pathname}?${params.toString()}`
}

export function withoutSignUpAttemptMarkers(path: string) {
  const [pathname, search = ''] = path.split('?', 2)
  const params = new URLSearchParams(search)
  params.delete(ACTIVE_SIGNUP_ATTEMPT)
  params.delete(NEW_SIGNUP_INTENT)
  const remaining = params.toString()
  return `${pathname}${remaining ? `?${remaining}` : ''}`
}

export function signUpEntryAction({
  activeAttempt,
  invited,
  newSignup,
  status,
  needsEmailVerification,
}: {
  activeAttempt: boolean
  invited: boolean
  newSignup: boolean
  status: string | null | undefined
  needsEmailVerification: boolean
}): SignUpEntryAction {
  if (newSignup) return 'reset-to-form'
  if (!activeAttempt && !invited) return 'reset-to-form'
  if (status === 'complete') return 'continue'
  if (needsEmailVerification) return 'show-verification'
  return 'show-form'
}
