/**
 * Authentication and user types.
 */

export type UserRole = 'admin' | 'compliance_officer' | 'analyst' | 'auditor' | 'viewer'

export type JurisdictionCode = 'GLOBAL' | 'EU' | 'US' | 'INDIA' | 'HIPAA' | 'GDPR'

export interface UserProfile {
  id: string
  email: string
  role: UserRole
  jurisdiction: JurisdictionCode
  is_active: boolean
  created_at?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in_minutes: number
  user_id: string
  email: string
  role: UserRole
  jurisdiction: JurisdictionCode
}

export interface DemoAccount {
  label: string
  email: string
  role: UserRole
  jurisdiction: JurisdictionCode
  description: string
}
