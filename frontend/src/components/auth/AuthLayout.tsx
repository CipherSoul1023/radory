import type { ReactNode } from 'react'
import { AuthBrand } from './AuthBrand'
import { AuthVisualPanel } from './AuthVisualPanel'
import './auth.css'

interface AuthLayoutProps {
  children: ReactNode
  visual: {
    tag: string
    title: string
    accent: string
    description: string
    bullets: readonly string[]
  }
}

export function AuthLayout({ children, visual }: AuthLayoutProps) {
  return (
    <main className="auth-shell">
      <section className="auth-pane">
        <div className="auth-wrap">
          <AuthBrand />
          {children}
        </div>
      </section>
      <AuthVisualPanel {...visual} />
    </main>
  )
}
