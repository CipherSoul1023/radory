interface AuthVisualPanelProps {
  tag: string
  title: string
  accent: string
  description: string
  bullets: readonly string[]
}

export function AuthVisualPanel({
  tag,
  title,
  accent,
  description,
  bullets,
}: AuthVisualPanelProps) {
  return (
    <section className="auth-visual-pane" aria-label="City skyline">
      <div className="auth-edge-blur" aria-hidden="true" />
      <div className="auth-sky-blur" aria-hidden="true" />
      <div className="auth-visual-content">
        <div className="auth-visual-top">
          <div className="auth-visual-kicker">
            Commercial real estate intelligence
          </div>
        </div>
        <div className="auth-visual-copy">
          <div className="auth-visual-tag">{tag}</div>
          <h2>
            {title} <span>{accent}</span>
          </h2>
          <p>{description}</p>
          <div className="auth-bullets">
            {bullets.map((bullet) => (
              <div className="auth-bullet" key={bullet}>
                {bullet}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
