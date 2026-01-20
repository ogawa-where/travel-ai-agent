const STORAGE_KEYS = {
  USER_ID: 'travel-ai-agent:user-id',
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
