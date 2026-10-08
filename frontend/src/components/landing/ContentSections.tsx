const steps = [
  {
    number: 1,
    icon: '◎',
    title: 'Track company signals',
    copy: 'Monitor hiring, funding, office footprints, leadership changes and more.',
  },
  {
    number: 2,
    icon: '▥',
    title: 'Detect real-estate decision windows',
    copy: 'Identify when occupiers are approaching a likely real estate move.',
  },
  {
    number: 3,
    icon: '➤',
    title: 'Act on ranked opportunities',
    copy: 'Get prioritized companies with context so you know who to call and when.',
  },
] as const

const productFeatures = [
  {
    icon: '⌕',
    title: 'Opportunities',
    copy: 'Ranked companies likely to make a real estate move.',
  },
  {
    icon: '▥',
    title: 'Market Activity',
    copy: 'Track notable leases, expansions and relocations across markets.',
  },
  {
    icon: '▱',
    title: 'Watchlist',
    copy: 'Keep an eye on your target accounts and get real-time updates.',
  },
  {
    icon: '▦',
    title: 'Company Intelligence',
    copy: 'Deep company profiles with hiring, locations, leadership and more.',
  },
] as const

const opportunityRows = [
  ['Nexora', 'Expanding', 'Sandton', '6–12 months', '89'],
  ['Vertex Labs', 'Relocation', 'Rosebank', '6–12 months', '82'],
  ['DataForge', 'Expanding', 'Waterfall', '12–18 months', '78'],
  ['Aurelium', 'Renewing', 'Sandton', '6–12 months', '74'],
  ['CloudNine', 'Expanding', 'Midrand', '6–12 months', '72'],
] as const

const benefits = [
  {
    icon: '⌖',
    title: 'Spot hot submarkets earlier',
    copy: 'See where occupier activity is building before it becomes obvious.',
  },
  {
    icon: '◉',
    title: 'Monitor occupiers across your territory',
    copy: 'Track target accounts and competitive occupiers over time.',
  },
  {
    icon: '◎',
    title: 'Prioritize outreach with context',
    copy: 'Know who deserves your attention and why.',
  },
  {
    icon: '▥',
    title: 'Turn scattered signals into insight',
    copy: 'Focus on what matters instead of searching across dozens of sources.',
  },
] as const

const modules = [
  {
    icon: '▤',
    title: 'Personalized Feed',
    copy: 'A feed tailored to your brokerage profile.',
  },
  {
    icon: '▱',
    title: 'Watchlist',
    copy: 'Track companies you want Radory to monitor.',
  },
  {
    icon: '◉',
    title: 'Brokerage Profile',
    copy: 'Define your markets, deal sizes and target occupiers.',
  },
  {
    icon: '▥',
    title: 'Market Activity',
    copy: 'Understand movement across your company radar.',
  },
  {
    icon: '◎',
    title: 'Companies Radar',
    copy: 'Explore companies relevant to your brokerage.',
  },
] as const

export function HowItWorks() {
  return (
    <section className="section" id="how">
      <div className="landing-container how-grid">
        <div>
          <div className="section-label">How it works</div>
          <h2 className="section-title">From signals to signed leases.</h2>
          <p className="section-copy">
            Radory continuously tracks company, people, and market activity to
            surface real estate decision windows — so your team can get in front
            of opportunities early.
          </p>
        </div>
        <div className="steps">
          {steps.map((step) => (
            <article className="card" key={step.number}>
              <div className="step-top">
                <span className="num">{step.number}</span>
                <span className="accent-symbol" aria-hidden="true">
                  {step.icon}
                </span>
              </div>
              <h3>{step.title}</h3>
              <p>{step.copy}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function ProductPreview() {
  return (
    <div className="product-shot" aria-label="Radory opportunities preview">
      <div className="product-window">
        <div className="product-top">
          <div className="product-search">
            ⌕ Search companies, markets, or keywords...
          </div>
        </div>
        <div className="product-body">
          <div className="prod-head">
            <h3>Opportunities</h3>
            <button className="filter-btn" type="button">
              Filters
            </button>
          </div>
          <div className="filters">
            {['All', 'Expanding', 'Relocating', 'Renewing', 'High intent'].map(
              (filter, index) => (
                <span
                  className={`filter${index === 0 ? ' active' : ''}`}
                  key={filter}
                >
                  {filter}
                </span>
              ),
            )}
          </div>
          <div className="opportunity-table">
            {opportunityRows.map(
              ([company, status, location, window, score]) => (
                <div className="opportunity-row" key={company}>
                  <strong>{company}</strong>
                  <span className="opportunity-status">{status}</span>
                  <span className="hide-mobile">{location}</span>
                  <span className="hide-mobile">{window}</span>
                  <span className="score">{score}</span>
                </div>
              ),
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export function ProductOverview() {
  return (
    <section className="section product-section" id="product">
      <div className="landing-container product-grid">
        <ProductPreview />
        <div>
          <div className="section-label">The product</div>
          <h2 className="section-title">
            A complete view of commercial real estate opportunity.
          </h2>
          <p className="section-copy">
            Radory brings together company intelligence, market activity and
            your custom watchlist — all in one powerful platform built for
            tenant-rep brokers.
          </p>
          <div className="feature-grid">
            {productFeatures.map((feature) => (
              <article className="feature" key={feature.title}>
                <div className="feature-icon" aria-hidden="true">
                  {feature.icon}
                </div>
                <h4>{feature.title}</h4>
                <p>{feature.copy}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

export function Benefits() {
  return (
    <section className="benefits" id="market">
      <div className="landing-container">
        <div className="center">
          <div className="section-label">Why brokers use Radory</div>
          <h2 className="section-title compact-title">
            Turn market signals into a competitive advantage.
          </h2>
        </div>
        <div className="benefit-grid">
          {benefits.map((benefit) => (
            <article className="benefit" key={benefit.title}>
              <div className="accent-symbol" aria-hidden="true">
                {benefit.icon}
              </div>
              <h4>{benefit.title}</h4>
              <p>{benefit.copy}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

export function ProductModules() {
  return (
    <section className="section" id="watchlist">
      <div className="landing-container">
        <div className="modules-head">
          <div>
            <div className="section-label">Product modules</div>
            <h2 className="section-title compact-title">
              A platform built for how you work.
            </h2>
          </div>
          <a className="explore-link" href="#product">
            Explore all features →
          </a>
        </div>
        <div className="module-grid">
          {modules.map((module) => (
            <article className="module" key={module.title}>
              <div className="feature-icon" aria-hidden="true">
                {module.icon}
              </div>
              <h4>{module.title}</h4>
              <p>{module.copy}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
