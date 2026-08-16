import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  getObservabilityOverview,
  getDriftReport,
  getRecentTraces,
  type ObservabilityOverview,
  type DriftReport,
  type RequestTrace,
  type UserProfile,
} from '../../services/api'

interface ObservabilityPanelProps {
  currentUser: UserProfile | null
  onOpenAuth: () => void
}

export function ObservabilityPanel({ currentUser, onOpenAuth }: ObservabilityPanelProps) {
  const [selectedTrace, setSelectedTrace] = useState<RequestTrace | null>(null)
  const [activeSubTab, setActiveSubTab] = useState<'overview' | 'drift' | 'traces'>('overview')

  const hasAccess = currentUser?.role === 'admin' || currentUser?.role === 'auditor'

  // Overview KPIs
  const {
    data: overview,
    isLoading: overviewLoading,
    isError: overviewError,
    refetch: refetchOverview,
  } = useQuery<ObservabilityOverview>({
    queryKey: ['observability-overview'],
    queryFn: getObservabilityOverview,
    enabled: hasAccess,
    refetchInterval: 10_000,
  })

  // Drift Report
  const {
    data: driftReport,
    isLoading: driftLoading,
    isError: driftError,
    refetch: refetchDrift,
  } = useQuery<DriftReport>({
    queryKey: ['observability-drift'],
    queryFn: () => getDriftReport(),
    enabled: hasAccess,
    refetchInterval: 15_000,
  })

  // Recent Traces
  const {
    data: recentTraces,
    isLoading: tracesLoading,
    isError: tracesError,
    refetch: refetchTraces,
  } = useQuery<RequestTrace[]>({
    queryKey: ['observability-traces'],
    queryFn: () => getRecentTraces(50),
    enabled: hasAccess,
    refetchInterval: 10_000,
  })

  if (!currentUser) {
    return (
      <div className="obs-access-restricted">
        <div className="obs-lock-icon">🔒</div>
        <h2>Authentication Required</h2>
        <p>You must sign in as an <strong>Administrator</strong> or <strong>Auditor</strong> to view production observability telemetry and quality drift reports.</p>
        <button className="btn-primary" onClick={onOpenAuth}>
          🔐 Sign In / Personas
        </button>
      </div>
    )
  }

  if (!hasAccess) {
    return (
      <div className="obs-access-restricted">
        <div className="obs-lock-icon">🚫</div>
        <h2>Access Restricted (403 Forbidden)</h2>
        <p>Your current role (<strong>{currentUser.role}</strong>) does not have permission to view enterprise telemetry logs or drift analytics.</p>
        <p className="obs-subtext">Telemetry access is strictly restricted to <strong>admin</strong> and <strong>auditor</strong> roles under AegisAI security policies.</p>
        <button className="btn-secondary" onClick={onOpenAuth}>
          Switch to Admin Persona
        </button>
      </div>
    )
  }

  return (
    <div className="observability-container">
      {/* ── Sub Navigation ─────────────────────────────────────────────────── */}
      <div className="obs-header-bar">
        <div className="obs-title-group">
          <h2>📊 Enterprise Observability & Quality Drift</h2>
          <span className="obs-badge-live">● Live Monitoring Active</span>
        </div>
        <div className="obs-tabs-nav">
          <button
            className={`obs-subtab-btn ${activeSubTab === 'overview' ? 'obs-subtab-btn--active' : ''}`}
            onClick={() => setActiveSubTab('overview')}
          >
            📈 Telemetry Overview
          </button>
          <button
            className={`obs-subtab-btn ${activeSubTab === 'drift' ? 'obs-subtab-btn--active' : ''}`}
            onClick={() => setActiveSubTab('drift')}
          >
            ⚖ M6 Quality Drift
          </button>
          <button
            className={`obs-subtab-btn ${activeSubTab === 'traces' ? 'obs-subtab-btn--active' : ''}`}
            onClick={() => setActiveSubTab('traces')}
          >
            🔍 Sanitized Traces ({recentTraces?.length ?? 0})
          </button>
        </div>
      </div>

      {/* ── Overview Sub-Tab ───────────────────────────────────────────────── */}
      {activeSubTab === 'overview' && (
        <div className="obs-tab-content">
          {overviewLoading && <div className="obs-loading">Loading telemetry KPIs…</div>}
          {overviewError && (
            <div className="obs-error">
              Unable to load telemetry metrics. <button onClick={() => refetchOverview()}>Retry</button>
            </div>
          )}

          {overview && (
            <>
              <div className="obs-kpi-grid">
                <div className="obs-kpi-card">
                  <div className="obs-kpi-label">Total Monitored Queries</div>
                  <div className="obs-kpi-val">{overview.total_requests}</div>
                  <div className="obs-kpi-sub">End-to-End Traced</div>
                </div>

                <div className="obs-kpi-card">
                  <div className="obs-kpi-label">Latency p50 / p95 / p99</div>
                  <div className="obs-kpi-val">
                    {overview.latency_p50_ms.toFixed(0)} <span className="obs-unit">/ {overview.latency_p95_ms.toFixed(0)} / {overview.latency_p99_ms.toFixed(0)} ms</span>
                  </div>
                  <div className="obs-kpi-sub">Monotonic Timer</div>
                </div>

                <div className="obs-kpi-card">
                  <div className="obs-kpi-label">Token Consumption</div>
                  <div className="obs-kpi-val">
                    {(overview.total_tokens / 1000).toFixed(1)}k <span className="obs-unit">tokens</span>
                  </div>
                  <div className="obs-kpi-sub">Prompt + Output</div>
                </div>

                <div className="obs-kpi-card">
                  <div className="obs-kpi-label">Estimated Dollar Cost</div>
                  <div className="obs-kpi-val">
                    ${overview.total_cost_usd.toFixed(4)}
                  </div>
                  <div className="obs-kpi-sub">Model Rate Cards</div>
                </div>

                <div className="obs-kpi-card">
                  <div className="obs-kpi-label">Abstention Rate</div>
                  <div className="obs-kpi-val">
                    {(overview.abstention_rate * 100).toFixed(1)}%
                  </div>
                  <div className="obs-kpi-sub">Calibrated & Grounded</div>
                </div>

                <div className="obs-kpi-card">
                  <div className="obs-kpi-label">Guardrail Block Rate</div>
                  <div className="obs-kpi-val">
                    {(overview.guardrail_block_rate * 100).toFixed(1)}%
                  </div>
                  <div className="obs-kpi-sub">Injection Defenses</div>
                </div>
              </div>

              {/* Privacy Architecture Notice */}
              <div className="obs-privacy-banner">
                <span className="obs-shield-icon">🛡️</span>
                <div>
                  <strong>Privacy-Preserving Telemetry Architecture:</strong> User queries are hashed with <strong>SHA-256</strong>. Raw queries, prompt texts, and confidential document passages are strictly excluded from telemetry payloads.
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── M6 Quality Drift Sub-Tab ─────────────────────────────────────────── */}
      {activeSubTab === 'drift' && (
        <div className="obs-tab-content">
          {driftLoading && <div className="obs-loading">Evaluating baseline quality drift…</div>}
          {driftError && (
            <div className="obs-error">
              Unable to load drift metrics. <button onClick={() => refetchDrift()}>Retry</button>
            </div>
          )}

          {driftReport && (
            <>
              <div className={`obs-drift-status-banner obs-drift-status--${driftReport.overall_drift_status.toLowerCase()}`}>
                <div className="obs-drift-status-title">
                  System Drift Status: <strong>{driftReport.overall_drift_status}</strong>
                </div>
                <div className="obs-drift-status-meta">
                  Baseline: <code>{driftReport.baseline_version}</code> | Samples: <strong>{driftReport.sample_count}</strong> (Min required: {driftReport.min_samples_required})
                </div>
              </div>

              <div className="obs-table-wrapper">
                <table className="obs-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>M6 Baseline</th>
                      <th>Current Live</th>
                      <th>Delta</th>
                      <th>Delta %</th>
                      <th>Threshold</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {driftReport.metrics.map((m) => (
                      <tr key={m.metric_name}>
                        <td className="obs-metric-name">
                          <code>{m.metric_name}</code>
                        </td>
                        <td>{m.baseline_value.toFixed(4)}</td>
                        <td>{m.current_value.toFixed(4)}</td>
                        <td className={m.delta < 0 && m.direction === 'higher_is_better' ? 'obs-delta--neg' : 'obs-delta--pos'}>
                          {m.delta >= 0 ? `+${m.delta.toFixed(4)}` : m.delta.toFixed(4)}
                        </td>
                        <td>
                          {m.delta_pct >= 0 ? `+${m.delta_pct.toFixed(2)}%` : `${m.delta_pct.toFixed(2)}%`}
                        </td>
                        <td>±{m.threshold_pct}%</td>
                        <td>
                          <span className={`obs-tag obs-tag--${m.status.toLowerCase()}`}>
                            {m.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Sanitized Traces Sub-Tab ────────────────────────────────────────── */}
      {activeSubTab === 'traces' && (
        <div className="obs-tab-content">
          {tracesLoading && <div className="obs-loading">Loading recent traces…</div>}
          {tracesError && (
            <div className="obs-error">
              Unable to load traces. <button onClick={() => refetchTraces()}>Retry</button>
            </div>
          )}

          {recentTraces && recentTraces.length === 0 && (
            <div className="obs-empty">
              No traces recorded yet. Ask questions in the AI Policy Assistant to generate telemetry.
            </div>
          )}

          {recentTraces && recentTraces.length > 0 && (
            <div className="obs-table-wrapper">
              <table className="obs-table">
                <thead>
                  <tr>
                    <th>Request ID</th>
                    <th>Query SHA-256 Hash</th>
                    <th>Role / Jur</th>
                    <th>Total Latency</th>
                    <th>Tokens</th>
                    <th>Cost</th>
                    <th>Citations</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTraces.map((t) => (
                    <tr key={t.request_id}>
                      <td>
                        <code className="obs-req-id">{t.request_id.slice(0, 8)}…</code>
                      </td>
                      <td>
                        <code className="obs-query-hash" title={t.query_hash}>
                          {t.query_hash.slice(0, 12)}…{t.query_hash.slice(-6)}
                        </code>
                      </td>
                      <td>
                        <span className="obs-role-jur">
                          {t.user_role || 'anon'} ({t.jurisdiction || 'GLOBAL'})
                        </span>
                      </td>
                      <td>{t.total_latency_ms.toFixed(0)} ms</td>
                      <td>{t.tokens_and_cost.total_tokens}</td>
                      <td>${t.tokens_and_cost.estimated_cost_usd.toFixed(4)}</td>
                      <td>
                        {t.citation_count > 0 ? (
                          <span className="obs-tag obs-tag--pass">{t.citation_count} Cited</span>
                        ) : (
                          <span className="obs-tag obs-tag--muted">0 Cited</span>
                        )}
                      </td>
                      <td>
                        {t.guardrail_blocked ? (
                          <span className="obs-tag obs-tag--blocked">Blocked</span>
                        ) : t.abstained ? (
                          <span className="obs-tag obs-tag--abstained">Abstained</span>
                        ) : (
                          <span className="obs-tag obs-tag--success">Answered</span>
                        )}
                      </td>
                      <td>
                        <button
                          className="obs-inspect-btn"
                          onClick={() => setSelectedTrace(t)}
                        >
                          Inspect Spans
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Span Inspector Modal ────────────────────────────────────────────── */}
      {selectedTrace && (
        <div className="modal-overlay" onClick={() => setSelectedTrace(null)}>
          <div className="modal-content obs-trace-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>🔍 Trace Spans: <code>{selectedTrace.request_id}</code></h3>
              <button className="btn-close" onClick={() => setSelectedTrace(null)}>✕</button>
            </div>

            <div className="modal-body">
              <div className="obs-modal-meta">
                <div><strong>Query SHA-256:</strong> <code>{selectedTrace.query_hash}</code></div>
                <div><strong>Total Duration:</strong> {selectedTrace.total_latency_ms.toFixed(1)} ms</div>
                <div><strong>Tokens:</strong> {selectedTrace.tokens_and_cost.total_tokens} ({selectedTrace.tokens_and_cost.input_tokens} in / {selectedTrace.tokens_and_cost.output_tokens} out)</div>
                <div><strong>Cost:</strong> ${selectedTrace.tokens_and_cost.estimated_cost_usd.toFixed(6)}</div>
              </div>

              <h4>Pipeline Spans ({selectedTrace.spans?.length || 0})</h4>
              <div className="obs-span-list">
                {selectedTrace.spans && selectedTrace.spans.length > 0 ? (
                  selectedTrace.spans.map((s) => (
                    <div key={s.span_id} className="obs-span-item">
                      <div className="obs-span-header">
                        <span className="obs-span-name"><code>{s.name}</code></span>
                        <span className="obs-span-dur">{s.latency_ms.toFixed(2)} ms</span>
                        <span className={`obs-tag obs-tag--${s.status.toLowerCase()}`}>{s.status}</span>
                      </div>
                      {Object.keys(s.metadata || {}).length > 0 && (
                        <pre className="obs-span-meta">
                          {JSON.stringify(s.metadata, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="obs-span-breakdown-list">
                    {Object.entries(selectedTrace.latency_breakdown_ms || {}).map(([name, ms]) => (
                      <div key={name} className="obs-span-breakdown-item">
                        <span><code>{name}</code></span>
                        <span>{ms.toFixed(2)} ms</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setSelectedTrace(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
