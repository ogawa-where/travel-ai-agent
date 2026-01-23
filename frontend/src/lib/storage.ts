const STORAGE_KEYS = {
  USER_ID: 'travel-ai-agent:user-id',
  USERNAME: 'travel-ai-agent:username',
} as const

export const storage = {
  getUserId(): string | null {
    try {
      return localStorage.getItem(STORAGE_KEYS.USER_ID)
    } catch {
      return null
    }
  },

  setUserId(userId: string): void {
    try {
      localStorage.setItem(STORAGE_KEYS.USER_ID, userId)
    } catch {
      console.warn('Failed to save user ID to localStorage')
    }
  },

  clearUserId(): void {
    try {
      localStorage.removeItem(STORAGE_KEYS.USER_ID)
    } catch {
      console.warn('Failed to clear user ID from localStorage')
    }
  },

  getUsername(): string | null {
    try {
      return localStorage.getItem(STORAGE_KEYS.USERNAME)
    } catch {
      return null
    }
  },

  setUsername(username: string): void {
    try {
      localStorage.setItem(STORAGE_KEYS.USERNAME, username)
    } catch {
      console.warn('Failed to save username to localStorage')
    }
  },

  clearUsername(): void {
    try {
      localStorage.removeItem(STORAGE_KEYS.USERNAME)
    } catch {
      console.warn('Failed to clear username from localStorage')
    }
  },

  clearAll(): void {
    try {
      Object.values(STORAGE_KEYS).forEach((key) => {
        localStorage.removeItem(key)
      })
    } catch {
      console.warn('Failed to clear localStorage')
    }
  },
}
