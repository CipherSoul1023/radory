import { Link } from 'react-router-dom'
import { dashboardLeads, expandingCompanies, radoryLogo } from './landingAssets'

function ArrowIcon() {
  return (
    <svg className="landing-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14" />
      <path d="M13 6l6 6-6 6" />
    </svg>
  )
}

function PlayIcon() {
  return (
    <svg className="landing-icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M10 8l6 4-6 4z" />
    </svg>
  )
}

function ProductDashboard() {
  return (
    <div className="dashboard" aria-label="Radory product dashboard preview">
      <aside className="dash-side">
        <div className="dash-logo">
          <img className="dash-logo-image" src={radoryLogo} alt="Radory" />
        </div>
        <div className="dash-nav">
          <div className="active">Home</div>
          <div>Opportunities</div>
          <div>Market Activity</div>
          <div>Watchlist</div>
          <div>Companies</div>
        </div>
      </aside>

      <div className="dash-main">
        <div className="dash-search">
          ⌕ Search companies, markets, or signals...
        </div>
        <div className="dash-title">
          <h3>Priority Opportunities</h3>
          <span className="viewall">View all →</span>
        </div>

        <div className="lead-list">
          {dashboardLeads.map((lead) => (
            <div className="lead" key={lead.name}>
              <div className="lead-company">
                <div className="tiny-logo">
                  <img src={lead.logo} alt="" />
                </div>
                <div>
                  <strong>{lead.name}</strong>
                  <small>{lead.location}</small>
                </div>
              </div>
              <span className="pill">{lead.move}</span>
              <span>{lead.window}</span>
              <span className="score">{lead.score}</span>
            </div>
          ))}
        </div>

        <div className="dash-bottom">
          <div className="mini">
            <h4>Market Activity</h4>
            <div className="market-wrap">
              <div>
                <div className="market-number">312</div>
                <div className="market-cap">notable moves</div>
              </div>
              <div className="mini-bars" aria-hidden="true">
                {[18, 31, 26, 39, 32, 45, 35].map((height, index) => (
                  <i key={index} style={{ height }} />
                ))}
              </div>
            </div>
          </div>

          <div className="mini">
            <h4>Expanding Companies</h4>
            <div className="mini-companies">
              {expandingCompanies.map((company) => (
                <div className="mini-company" key={company.name}>
                  <div className="mini-company-left">
                    <div className="mini-logo">
                      <img src={company.logo} alt="" />
                    </div>
                    <div>
                      <strong>{company.name}</strong>
                      <span>{company.signal}</span>
                    </div>
                  </div>
                  <div>
                    <span>{company.growth}</span>
                    <div className="score">{company.score}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function Hero() {
  return (
    <header className="hero">
      <div className="landing-container nav">
        <a className="brand" href="#top" aria-label="Radory home">
          <img className="brand-logo-image" src={radoryLogo} alt="Radory" />
        </a>

        <nav className="navlinks" aria-label="Main navigation">
          <a href="#product">Product</a>
          <a href="#how">How it Works</a>
          <a href="#market">Market Activity</a>
          <a href="#watchlist">Watchlist</a>
        </nav>

        <div className="navactions">
          <Link className="linkbtn" to="/sign-in">
            Sign in
          </Link>
          <Link className="btn btn-primary" to="/sign-up">
            Get Started
            <ArrowIcon />
          </Link>
        </div>
      </div>

      <div className="landing-container hero-grid" id="top">
        <div className="hero-copy">
          <div className="eyebrow">Commercial real estate intelligence</div>
          <h1>
            Know who's about <span>to need space.</span>
          </h1>
          <p>
            Radory tracks occupier signals and detects commercial real estate
            decision windows before they become obvious opportunities.
          </p>

          <div className="hero-actions">
            <Link className="btn btn-primary" to="/sign-up">
              Start finding opportunities
              <ArrowIcon />
            </Link>
            <a className="btn btn-outline" href="#how">
              <PlayIcon />
              See how it works
            </a>
          </div>

          <div className="hero-bullets">
            <span>⌁ Earlier insights</span>
            <span>▥ Better outreach</span>
            <span>◎ Bigger opportunities</span>
          </div>
        </div>

        <ProductDashboard />
      </div>
    </header>
  )
}
