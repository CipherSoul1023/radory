import { Link } from 'react-router-dom'

export function CallToAction() {
  return (
    <section className="cta-section">
      <div className="landing-container">
        <div className="cta-box">
          <h2>Find the opportunity before everyone else does.</h2>
          <p>
            Build your brokerage radar and start monitoring the companies,
            markets and commercial real estate events that matter to you.
          </p>
          <Link className="btn btn-primary" to="/sign-up">
            Build your radar
            <svg
              className="landing-icon"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M5 12h14" />
              <path d="M13 6l6 6-6 6" />
            </svg>
          </Link>
        </div>
      </div>
    </section>
  )
}
