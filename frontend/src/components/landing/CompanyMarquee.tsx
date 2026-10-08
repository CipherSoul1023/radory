import { companies } from './landingAssets'

export function CompanyMarquee() {
  const companyLoop = [...companies, ...companies]

  return (
    <section
      className="marquee-section"
      aria-labelledby="company-marquee-title"
    >
      <div className="landing-container">
        <div className="marquee-title" id="company-marquee-title">
          Companies on your radar
        </div>
        <div className="marquee">
          <div className="track">
            {companyLoop.map((company, index) => (
              <div
                className="logo-card"
                key={`${company.name}-${index}`}
                aria-hidden={index >= companies.length}
              >
                <div className="logo-image-wrap">
                  <img
                    src={company.logo}
                    alt={index < companies.length ? `${company.name} logo` : ''}
                  />
                </div>
                <div>
                  <div className="logo-name">{company.name}</div>
                  <div className="logo-type">{company.type}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
