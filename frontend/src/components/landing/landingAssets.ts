import aureliumLogo from '../../assets/landing/aurelium.png'
import cloudNineLogo from '../../assets/landing/cloud-nine.png'
import dataForgeLogo from '../../assets/landing/dataforge.png'
import helixHealthLogo from '../../assets/landing/helix-health.png'
import luminaWorksLogo from '../../assets/landing/lumina-works.png'
import nexoraLogo from '../../assets/landing/nexora.png'
import northstarAiLogo from '../../assets/landing/northstar-ai.png'
import payGridLogo from '../../assets/landing/paygrid.png'
import radoryLogo from '../../assets/landing/radory-logo.png'
import tandemCloudLogo from '../../assets/landing/tandem-cloud.png'
import vertexLabsLogo from '../../assets/landing/vertex-labs.png'

export { radoryLogo }

export const companies = [
  { name: 'Nexora', type: 'Technology', logo: nexoraLogo },
  { name: 'Vertex Labs', type: 'AI & Analytics', logo: vertexLabsLogo },
  { name: 'DataForge', type: 'Data Infrastructure', logo: dataForgeLogo },
  { name: 'Aurelium', type: 'Fintech', logo: aureliumLogo },
  { name: 'CloudNine', type: 'Cloud Services', logo: cloudNineLogo },
  { name: 'PayGrid', type: 'Payments', logo: payGridLogo },
  { name: 'Helix Health', type: 'Healthcare', logo: helixHealthLogo },
  {
    name: 'Lumina Works',
    type: 'Professional Services',
    logo: luminaWorksLogo,
  },
  { name: 'Northstar AI', type: 'AI Platform', logo: northstarAiLogo },
  { name: 'Tandem Cloud', type: 'SaaS Infrastructure', logo: tandemCloudLogo },
] as const

export const dashboardLeads = [
  {
    name: 'Nexora',
    location: 'Sandton',
    move: 'Expanding',
    window: '6–12 months',
    score: 89,
    logo: nexoraLogo,
  },
  {
    name: 'Vertex Labs',
    location: 'Rosebank',
    move: 'Relocation',
    window: '6–12 months',
    score: 82,
    logo: vertexLabsLogo,
  },
  {
    name: 'DataForge',
    location: 'Waterfall',
    move: 'Expanding',
    window: '12–18 months',
    score: 78,
    logo: dataForgeLogo,
  },
] as const

export const expandingCompanies = [
  {
    name: 'Aurelium',
    signal: 'Hiring',
    growth: '+2,400',
    score: 92,
    logo: aureliumLogo,
  },
  {
    name: 'Northstar AI',
    signal: 'Hiring',
    growth: '+1,200',
    score: 88,
    logo: northstarAiLogo,
  },
  {
    name: 'Tandem Cloud',
    signal: 'Expanding',
    growth: '+800',
    score: 76,
    logo: tandemCloudLogo,
  },
] as const
