const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface HealthResponse {
  status: string
}

interface PreferenceSignal {
  id: string
  user_id: string
  category: string
  tag: string
  weight: number
  evidence: string
  created_at: string
  updated_at: string
}

interface UserProfile {
  id: string
  user_id: string
  summary: string
  created_at: string
  updated_at: string
}

interface User {
  id: string
  created_at: string
  updated_at: string
  profile: UserProfile | null
  preference_signals: PreferenceSignal[]
}

interface ChatResponse {
  user_id: string
  session_id: string
  assistant_message: string
  updated_signals: PreferenceSignal[]
}

export const api = {
  async healthCheck(): Promise<HealthResponse> {
    const response = await fetch(`${API_BASE_URL}/health`)
    if (!response.ok) {
      throw new Error('Health check failed')
    }
    return response.json()
  },

  async createUser(): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/preference/users`, {
      method: 'POST',
    })
    if (!response.ok) {
      throw new Error('Failed to create user')
    }
    return response.json()
  },

  async getUser(userId: string): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/preference/users/${userId}`)
    if (!response.ok) {
      throw new Error('Failed to get user')
    }
    return response.json()
  },

  async startChat(userId: string): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/api/preference/chat/start?user_id=${userId}`, {
      method: 'POST',
    })
    if (!response.ok) {
      throw new Error('Failed to start chat')
    }
    return response.json()
  },

  async sendMessage(userId: string, message: string, sessionId?: string): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/api/preference/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        message: message,
        session_id: sessionId,
      }),
    })
    if (!response.ok) {
      throw new Error('Failed to send message')
    }
    return response.json()
  },

  async getUserSignals(userId: string): Promise<PreferenceSignal[]> {
    const response = await fetch(`${API_BASE_URL}/api/preference/users/${userId}/signals`)
    if (!response.ok) {
      throw new Error('Failed to get user signals')
    }
    return response.json()
  },
}

export type { User, UserProfile, PreferenceSignal, ChatResponse }
