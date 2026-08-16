import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  healthCheck,
  getStoredUser,
  clearStoredAuth,
  type HealthResponse,
} from './services/api'
import type { UserProfile } from './types/auth'
import type { Citation } from './types/chat'
import { ChatPanel } from './features/chat/ChatPanel'
import { DocumentUpload } from './features/documents/DocumentUpload'
import { DocumentList } from './features/documents/DocumentList'
import { QueryPanel } from './features/query/QueryPanel'
import { ObservabilityPanel } from './features/observability/ObservabilityPanel'
import { CitationDrawer } from './features/citations/CitationDrawer'
import { AuthModal } from './features/auth/AuthModal'
import './App.css'

// ── Health badge ───────────────────────────────────────────────────────────────
function HealthBadge({
  data,
  isLoading,
  isError,
}: {
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
      {isHealthy ? 'System Healthy' : 'Database Unreachable'}
    </div>
  )
}

type MainTab = 'chat' | 'documents' | 'query' | 'observability'

export default function App() {
  const [activeTab, setActiveTab] = useState<MainTab>('chat')
  const [refreshKey, setRefreshKey] = useState(0)
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => getStoredUser())

  const { data: healthData, isLoading: healthLoading, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: healthCheck,
    refetchInterval: 15_000,
  })

  // Synchronize authentication on mount
  useEffect(() => {
    const user = getStoredUser()
    if (user) {
      setCurrentUser(user)
    }
  }, [])

  const handleUploadSuccess = () => {
    setRefreshKey((k) => k + 1)
  }

  const handleLogout = () => {
    clearStoredAuth()
    setCurrentUser(null)
  }

  const handleAuthSuccess = (user: UserProfile) => {
    setCurrentUser(user)
  }

  return (
    <div className="app">
      {/* ── Top Header ─────────────────────────────────────────────────────── */}
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">⚖</span>
            <div className="logo-text-group">
              <span className="logo-text">AegisAI</span>
              <span className="logo-tagline">Regulated Document Intelligence</span>
            </div>
          </div>
        </div>

        <div className="header-right">
          <HealthBadge
            data={healthData}
            isLoading={healthLoading}
            isError={healthError}
          />

          {currentUser ? (
            <button
              className="user-status-btn"
              onClick={() => setAuthModalOpen(true)}
              title="View account profile and permissions"
            >
              <span className="user-icon">👤</span>
              <span className="user-email-text">{currentUser.email}</span>
              <span className="user-role-pill">{currentUser.role}</span>
              <span className="user-jur-pill">{currentUser.jurisdiction}</span>
            </button>
          ) : (
            <button
              className="btn-auth-trigger"
              onClick={() => setAuthModalOpen(true)}
            >
              🔐 Sign In / Personas
            </button>
          )}

          <span className="milestone-badge">M7 Observability</span>
        </div>
      </header>

      {/* ── Main Navigation Tabs ───────────────────────────────────────────── */}
      <nav className="tab-nav" role="tablist" aria-label="Main navigation">
        <button
          id="tab-chat"
          role="tab"
          aria-selected={activeTab === 'chat'}
          className={`tab-btn ${activeTab === 'chat' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <span className="tab-icon">💬</span> AI Policy Assistant
        </button>

        <button
          id="tab-documents"
          role="tab"
          aria-selected={activeTab === 'documents'}
          className={`tab-btn ${activeTab === 'documents' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          <span className="tab-icon">📁</span> Document Management
        </button>

        <button
          id="tab-query"
          role="tab"
          aria-selected={activeTab === 'query'}
          className={`tab-btn ${activeTab === 'query' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('query')}
        >
          <span className="tab-icon">🔍</span> Raw Vector Search
        </button>

        <button
          id="tab-observability"
          role="tab"
          aria-selected={activeTab === 'observability'}
          className={`tab-btn ${activeTab === 'observability' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('observability')}
        >
          <span className="tab-icon">📊</span> Telemetry & Drift
        </button>
      </nav>

      {/* ── Main Workspace Content ──────────────────────────────────────────── */}
      <main className="main" role="main">
        {activeTab === 'chat' && (
          <ChatPanel
            currentUser={currentUser}
            onOpenCitation={(citation) => setActiveCitation(citation)}
            onOpenAuth={() => setAuthModalOpen(true)}
          />
        )}

        {activeTab === 'documents' && (
          <div className="documents-layout">
            <DocumentUpload onSuccess={handleUploadSuccess} />
            <DocumentList refreshKey={refreshKey} />
          </div>
        )}

        {activeTab === 'query' && <QueryPanel />}

        {activeTab === 'observability' && (
          <ObservabilityPanel
            currentUser={currentUser}
            onOpenAuth={() => setAuthModalOpen(true)}
          />
        )}
      </main>


      {/* ── Interactive Citation Inspector Drawer ──────────────────────────── */}
      <CitationDrawer
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />

      {/* ── Authentication & Persona Modal ─────────────────────────────────── */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        currentUser={currentUser}
        onAuthSuccess={handleAuthSuccess}
        onLogout={handleLogout}
      />
    </div>
  )
}
