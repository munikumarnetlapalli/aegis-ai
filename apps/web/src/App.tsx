import { useQuery } from '@tanstack/react-query'
import { healthCheck, type HealthResponse } from './services/api'
import './App.css'

// ── Health badge component ─────────────────────────────────────────────────────
function HealthBadge({ data, isLoading, isError }: {
  data: HealthResponse | undefined
  isLoading: boolean
  isError: boolean
}) {
  if (isLoading) {
    return (
      <div className="badge badge--loading">
        <span className="dot dot--pulse" />
        Connecting…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="badge badge--error">
        <span className="dot dot--error" />
        Backend unreachable
      </div>
    )
  }

  const isHealthy = data.status === 'healthy'

  return (
    <div className={`badge ${isHealthy ? 'badge--healthy' : 'badge--error'}`}>
      <span className={`dot ${isHealthy ? 'dot--healthy' : 'dot--error'}`} />
      {isHealthy ? 'System healthy' : 'Database unreachable'}
    </div>
  )
}

// ── Stack trace component ──────────────────────────────────────────────────────
function StackTrace({ data }: { data: HealthResponse | undefined }) {
  const steps = [
    { label: 'Browser', ok: true },
    { label: 'React', ok: true },
    { label: 'GET /health', ok: !!data },
    { label: 'FastAPI', ok: !!data },
    { label: 'PostgreSQL', ok: data?.database === 'connected' },
    { label: '"healthy"', ok: data?.status === 'healthy' },
  ]

  return (
    <div className="stack-trace">
      {steps.map((step, i) => (
        <div key={step.label} className="stack-step">
          <div className={`stack-node ${step.ok ? 'stack-node--ok' : 'stack-node--waiting'}`}>
            {step.label}
          </div>
          {i < steps.length - 1 && (
            <div className={`stack-arrow ${step.ok ? 'stack-arrow--ok' : ''}`}>↓</div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── App ────────────────────────────────────────────────────────────────────────
export default function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: healthCheck,
    refetchInterval: 15_000,   // re-check every 15 s
  })

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <span className="logo-icon">⚖</span>
          <span className="logo-text">AegisAI</span>
        </div>
        <span className="milestone-badge">M1 Foundation</span>
      </header>

      <main className="main">
        <h1 className="title">Foundation Stack</h1>
        <p className="subtitle">
          M1 health check — verifying the full chain from browser to database.
        </p>

        <HealthBadge data={data} isLoading={isLoading} isError={isError} />

        <StackTrace data={data} />

        {data && (
          <div className="detail-card">
            <h2>Health response</h2>
            <pre className="json-block">
              {JSON.stringify(data, null, 2)}
            </pre>
            <p className="detail-hint">
              Backend version: <code>{data.version}</code>
            </p>
          </div>
        )}

        <p className="next-step">
          ✓ M1 complete — next: M2 Document ingestion
        </p>
      </main>
    </div>
  )
}
