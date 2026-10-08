import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

type ClerkResult = { error: unknown }

export function hasInvitationContext(
  search: string | URLSearchParams,
): boolean {
  const params =
    typeof search === 'string' ? new URLSearchParams(search) : search
  return (
    params.get('invitation') === '1' ||
    params.has('__clerk_ticket') ||
    params.get('__clerk_status') === 'complete'
  )
}

export function withInvitationContext(path: string, invited: boolean): string {
  if (!invited) return path
  const [pathname, search = ''] = path.split('?', 2)
  const params = new URLSearchParams(search)
  params.set('invitation', '1')
  return `${pathname}?${params.toString()}`
}

export async function checkClerk(result: Promise<ClerkResult>) {
  const { error } = await result
  if (error) throw error
}

export function authError(error: unknown): string {
  if (error && typeof error === 'object') {
    // Clerk's longMessage is intended for end users. Never render raw errors or tokens.
    if ('longMessage' in error && typeof error.longMessage === 'string')
      return error.longMessage
    if ('errors' in error && Array.isArray(error.errors)) {
      const message = error.errors[0]?.longMessage
      if (typeof message === 'string') return message
    }
    if ('code' in error) {
      const messages: Record<string, string> = {
        form_password_incorrect:
          'That password is incorrect. Please try again.',
        form_identifier_not_found:
          'We couldn’t find that account. Check your email or create an account.',
        form_code_incorrect: 'That code is incorrect. Please try again.',
        verification_expired: 'That code has expired. Request a new code.',
        form_password_pwned:
          'Choose a different password. This password has appeared in a data breach.',
        too_many_requests:
          'Too many attempts. Please wait a moment before trying again.',
      }
      if (typeof error.code === 'string' && messages[error.code])
        return messages[error.code]
    }
  }
  return 'We could not complete that request. Please try again.'
}

export function useAuthAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function run(action: () => Promise<void>) {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (cause) {
      setError(authError(cause))
    } finally {
      setBusy(false)
    }
  }
  return { busy, error, setError, run }
}

export function useAuthDestination(invited = false) {
  const navigate = useNavigate()
  return ({ decorateUrl }: { decorateUrl: (url: string) => string }) => {
    const destination = decorateUrl(
      withInvitationContext('/auth/continue', invited),
    )
    if (destination.startsWith('http')) window.location.assign(destination)
    else navigate(destination, { replace: true })
  }
}

export function field(form: HTMLFormElement, name: string) {
  return String(new FormData(form).get(name) ?? '')
}
