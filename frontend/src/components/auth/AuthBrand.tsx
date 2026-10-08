import { Link } from 'react-router-dom'
import radoryLogo from '../../assets/landing/radory-logo.png'

export function AuthBrand() {
  return (
    <Link
      className="auth-brand"
      to="/"
      aria-label="Return to the Radory home page"
    >
      <img src={radoryLogo} alt="Radory" />
    </Link>
  )
}
