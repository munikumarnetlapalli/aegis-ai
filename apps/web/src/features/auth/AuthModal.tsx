import { useState } from 'react'
import { loginUser, registerUser } from '../../services/api'
import type { UserProfile, UserRole, JurisdictionCode } from '../../types/auth'

interface Props {
  isOpen: boolean
  onClose: () => void
  currentUser: UserProfile | null
  onAuthSuccess: (user: UserProfile) => void
  onLogout: () => void
}

interface DemoAccount {
  name: string
  email: string
  pass: string
  role: UserRole
  jurisdiction: JurisdictionCode
  desc: string
}

const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    name: 'System Admin',
    email: 'admin@aegis.local',
    pass: 'AdminDev2026!Secure',
    role: 'admin',
    jurisdiction: 'GLOBAL',
    desc: 'Full administrative access across all jurisdictions and documents.',
  },
  {
    name: 'Compliance Officer (EU)',
    email: 'compliance_officer_eu@test.local',
    pass: 'TestPassword123!',
    role: 'compliance_officer',
    jurisdiction: 'EU',
    desc: 'GDPR & EU policy compliance officer. Isolated to EU/GLOBAL documents.',
  },
  {
    name: 'Senior Analyst (US)',
    email: 'analyst_us@test.local',
    pass: 'TestPassword123!',
    role: 'analyst',
    jurisdiction: 'US',
    desc: 'US claims and underwriting analyst. Isolated to US/GLOBAL documents.',
  },
  {
    name: 'Internal Auditor (Global)',
    email: 'auditor_global@test.local',
    pass: 'TestPassword123!',
    role: 'auditor',
    jurisdiction: 'GLOBAL',
    desc: 'Audit and inspection authority across multi-regional records.',
  },
  {
    name: 'Standard Viewer',
    email: 'attacker-verify-fix@test.local',
    pass: 'TestPassword123!',
    role: 'viewer',
    jurisdiction: 'EU',
    desc: 'Public read-only account with safe default permissions.',
  },
]

export function AuthModal({
  isOpen,
  onClose,
  currentUser,
  onAuthSuccess,
  onLogout,
}: Props) {
  const [tab, setTab] = useState<'login' | 'register' | 'demo'>('demo')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [jurisdiction, setJurisdiction] = useState('GLOBAL')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const token = await loginUser(email.trim(), password)
      onAuthSuccess({
        id: token.user_id,
        email: token.email,
        role: token.role,
        jurisdiction: token.jurisdiction,
        is_active: true,
      })
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSuccessMsg(null)

    try {
      await registerUser(email.trim(), password, jurisdiction)
      setSuccessMsg('Account created successfully! You can now log in.')
      setTab('login')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const handleQuickDemoLogin = async (acc: DemoAccount) => {
    setLoading(true)
    setError(null)
    try {
      const token = await loginUser(acc.email, acc.pass)
      onAuthSuccess({
        id: token.user_id,
        email: token.email,
        role: token.role,
        jurisdiction: token.jurisdiction,
        is_active: true,
      })
      onClose()
    } catch {
      // If seed user doesn't exist, register and login
      try {
        await registerUser(acc.email, acc.pass, acc.jurisdiction)
        const token = await loginUser(acc.email, acc.pass)
        onAuthSuccess({
          id: token.user_id,
          email: token.email,
          role: token.role,
          jurisdiction: token.jurisdiction,
          is_active: true,
        })
        onClose()
      } catch (regErr: unknown) {
        setError(regErr instanceof Error ? regErr.message : 'Failed to login demo account')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        {/* ── Modal Header ──────────────────────────────────────────────── */}
        <div className="modal-header">
          <div className="modal-title-group">
            <span className="auth-icon">🔐</span>
            <h3 className="modal-title">Security & Identity</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        {/* ── Current Active Session (if logged in) ────────────────────── */}
        {currentUser ? (
          <div className="auth-profile-card">
            <div className="profile-badge-row">
              <span className="profile-role-badge profile-role-badge--active">
                Role: <strong>{currentUser.role.toUpperCase()}</strong>
              </span>
              <span className="profile-jur-badge">
                Jurisdiction: <strong>{currentUser.jurisdiction}</strong>
              </span>
            </div>
            <div className="profile-email">
              Signed in as: <code>{currentUser.email}</code>
            </div>
            <div className="profile-notice">
              <span className="info-icon">ℹ</span> All document retrieval and answer generation is strictly isolated to your server-verified role and regional jurisdiction.
            </div>
            <div className="modal-actions">
              <button
                className="btn btn--danger"
                onClick={() => {
                  onLogout()
                  onClose()
                }}
              >
                Sign Out
              </button>
              <button className="btn btn--secondary" onClick={onClose}>
                Close
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* ── Tabs ─────────────────────────────────────────────────── */}
            <div className="auth-tabs" role="tablist">
              <button
                className={`auth-tab-btn ${tab === 'demo' ? 'auth-tab-btn--active' : ''}`}
                onClick={() => { setTab('demo'); setError(null) }}
              >
                ⚡ Fast Demo Accounts
              </button>
              <button
                className={`auth-tab-btn ${tab === 'login' ? 'auth-tab-btn--active' : ''}`}
                onClick={() => { setTab('login'); setError(null) }}
              >
                Sign In
              </button>
              <button
                className={`auth-tab-btn ${tab === 'register' ? 'auth-tab-btn--active' : ''}`}
                onClick={() => { setTab('register'); setError(null) }}
              >
                Register
              </button>
            </div>

            {/* ── Notifications ────────────────────────────────────────── */}
            {error && <div className="auth-alert auth-alert--error">{error}</div>}
            {successMsg && <div className="auth-alert auth-alert--success">{successMsg}</div>}

            {/* ── Demo Accounts Switcher ──────────────────────────────── */}
            {tab === 'demo' && (
              <div className="demo-accounts-list">
                <p className="demo-hint">
                  Click any verified test persona to immediately authenticate. Role and jurisdiction are strictly derived server-side via cryptographic JWT.
                </p>
                {DEMO_ACCOUNTS.map((acc) => (
                  <button
                    key={acc.email}
                    className="demo-account-card"
                    disabled={loading}
                    onClick={() => handleQuickDemoLogin(acc)}
                  >
                    <div className="demo-card-top">
                      <span className="demo-account-name">{acc.name}</span>
                      <div className="demo-pill-group">
                        <span className="pill pill--role">{acc.role}</span>
                        <span className="pill pill--jur">{acc.jurisdiction}</span>
                      </div>
                    </div>
                    <div className="demo-account-email">{acc.email}</div>
                    <div className="demo-account-desc">{acc.desc}</div>
                  </button>
                ))}
              </div>
            )}

            {/* ── Login Form ──────────────────────────────────────────── */}
            {tab === 'login' && (
              <form className="auth-form" onSubmit={handleLoginSubmit}>
                <label className="form-label" htmlFor="login-email">
                  Email Address
                </label>
                <input
                  id="login-email"
                  type="email"
                  required
                  className="form-input"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />

                <label className="form-label" htmlFor="login-password">
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  required
                  className="form-input"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />

                <button
                  type="submit"
                  className="btn btn--primary btn--full"
                  disabled={loading}
                >
                  {loading ? 'Authenticating…' : 'Sign In'}
                </button>
              </form>
            )}

            {/* ── Register Form ───────────────────────────────────────── */}
            {tab === 'register' && (
              <form className="auth-form" onSubmit={handleRegisterSubmit}>
                <label className="form-label" htmlFor="reg-email">
                  Email Address
                </label>
                <input
                  id="reg-email"
                  type="email"
                  required
                  className="form-input"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />

                <label className="form-label" htmlFor="reg-password">
                  Password (min 8 characters)
                </label>
                <input
                  id="reg-password"
                  type="password"
                  required
                  minLength={8}
                  className="form-input"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />

                <label className="form-label" htmlFor="reg-jurisdiction">
                  Assigned Regional Jurisdiction
                </label>
                <select
                  id="reg-jurisdiction"
                  className="form-select"
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                >
                  <option value="GLOBAL">GLOBAL (Multi-Region)</option>
                  <option value="EU">EU (GDPR Compliance)</option>
                  <option value="US">US (Federal & State)</option>
                  <option value="HIPAA">HIPAA (Healthcare)</option>
                  <option value="INDIA">INDIA (DPDP Act)</option>
                </select>

                <p className="form-hint">
                  Note: Public registration safely assigns the default <code>viewer</code> role. Elevated roles (Admin, Compliance Officer) must be provisioned by an administrator.
                </p>

                <button
                  type="submit"
                  className="btn btn--primary btn--full"
                  disabled={loading}
                >
                  {loading ? 'Creating Account…' : 'Create Account'}
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  )
}
