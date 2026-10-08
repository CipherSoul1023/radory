import { CallToAction } from '../components/landing/CallToAction'
import { CompanyMarquee } from '../components/landing/CompanyMarquee'
import {
  Benefits,
  HowItWorks,
  ProductModules,
  ProductOverview,
} from '../components/landing/ContentSections'
import { Hero } from '../components/landing/Hero'
import '../components/landing/landing.css'

export function LandingPage() {
  return (
    <main className="landing-page">
      <Hero />
      <CompanyMarquee />
      <HowItWorks />
      <ProductOverview />
      <Benefits />
      <ProductModules />
      <CallToAction />
    </main>
  )
}
