import { useState } from 'react'

interface TextFieldProps {
  id: string
  label: string
  placeholder: string
  autoComplete: string
  required?: boolean
}

type PasswordFieldProps = TextFieldProps

export function GoogleButton({
  onClick,
  disabled,
}: {
  onClick?: () => void
  disabled?: boolean
}) {
  return (
    <button
      className="auth-google"
      type="button"
      onClick={onClick}
      disabled={disabled}
    >
      <span className="auth-google-mark" aria-hidden="true">
        G
      </span>
      Continue with Google
    </button>
  )
}

export function EmailField({
  id,
  label,
  placeholder,
  autoComplete,
  required = true,
}: TextFieldProps) {
  return (
    <div className="auth-field">
      <label htmlFor={id}>{label}</label>
      <div className="auth-input-wrap">
        <span className="auth-input-icon" aria-hidden="true">
          ✉
        </span>
        <input
          id={id}
          name={id}
          type="email"
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
        />
      </div>
    </div>
  )
}

export function PasswordField({
  id,
  label,
  placeholder,
  autoComplete,
}: PasswordFieldProps) {
  const [isVisible, setIsVisible] = useState(false)

  return (
    <div className="auth-field">
      <label htmlFor={id}>{label}</label>
      <div className="auth-input-wrap">
        <span className="auth-input-icon" aria-hidden="true">
          ▣
        </span>
        <input
          id={id}
          name={id}
          type={isVisible ? 'text' : 'password'}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required
        />
        <button
          className="auth-show-password"
          type="button"
          onClick={() => setIsVisible((visible) => !visible)}
          aria-label={`${isVisible ? 'Hide' : 'Show'} ${label.toLowerCase()}`}
        >
          {isVisible ? 'Hide' : 'Show'}
        </button>
      </div>
    </div>
  )
}
