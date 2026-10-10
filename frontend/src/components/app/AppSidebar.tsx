import {
  Activity,
  Building2,
  Flag,
  LayoutDashboard,
  Settings,
  Star,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import radoryLogo from '../../assets/landing/radory-logo.png'
import { APP_ROUTES, type AppRoutePath } from '../../services/appRoutes'

const navigationIcons: Record<AppRoutePath, typeof LayoutDashboard> = {
  '/app': LayoutDashboard,
  '/app/opportunities': Flag,
  '/app/companies': Building2,
  '/app/market-activity': Activity,
  '/app/watchlist': Star,
  '/app/settings': Settings,
}

export function AppSidebar() {
  return (
    <aside className="workspace-dashboard-sidebar">
      <NavLink to="/app" aria-label="Radory dashboard">
        <img
          className="workspace-dashboard-brand"
          src={radoryLogo}
          alt="Radory"
        />
      </NavLink>
      <nav
        className="workspace-dashboard-nav"
        aria-label="Workspace navigation"
      >
        {APP_ROUTES.map(({ label, path, end }) => {
          const Icon = navigationIcons[path]
          return (
            <NavLink
              className={({ isActive }) => (isActive ? 'active' : undefined)}
              end={end}
              key={path}
              to={path}
            >
              <Icon aria-hidden="true" size={21} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}
