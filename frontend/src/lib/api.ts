import { parseApiError, createNetworkError } from './errors'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const fetchWithErrorHandling = async (url: string, options?: RequestInit): Promise<Response> => {
  try {
    const response = await fetch(url, options)
    if (!response.ok) {
      throw await parseApiError(response)
    }
    return response
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw createNetworkError()
    }
    throw error
  }
}

interface HealthResponse {
  status: string
}

interface LoginResponse {
  user: User
  is_new_user: boolean
  message: string
}

interface WorkerHealth {
  host: string
  role: string
  healthy: boolean
  consecutive_failures: number
}

interface LLMHealthResponse {
  healthy: number
  total: number
  all_healthy: boolean
  any_healthy: boolean
  workers: WorkerHealth[]
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
  username: string | null
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

// 旅行企画モード用インターフェース
interface POI {
  name: string
  category: string
  location: string
  description: string
  price_range: string
  duration_minutes: number | null
  opening_hours: string
  rating: number | null
  tags: string[]
  source_url: string
}

interface ItineraryItem {
  time_start: string
  time_end: string
  poi: POI
  notes: string
  travel_from_previous: string
}

interface DayPlan {
  day_number: number
  date: string | null
  theme: string
  items: ItineraryItem[]
  accommodation: POI | null
}

interface Itinerary {
  title: string
  summary: string
  days: DayPlan[]
  total_budget_estimate: number | null
  highlights: string[]
}

interface TravelPlan {
  id: string
  request_id: string
  itinerary: Itinerary
  rationale: string
  score: number
  score_breakdown: Record<string, number>
  version: number
  is_selected: boolean
  created_at: string
}

interface TravelChatResponse {
  user_id: string
  session_id: string
  assistant_message: string
  plan_request_id: string | null
  plan: TravelPlan | null
  status: string
}

interface LearningCompletionResponse {
  user_id: string
  session_id: string
  profile_summary: string
  total_signals: number
  consolidated_signals: number
  removed_signals: string[]
  message: string
}

interface TravelFeedbackResponse {
  user_id: string
  plan_id: string
  updated_signals_count: number
  profile_updated: boolean
  message: string
}

// 統合チャット用インターフェース
interface LearnedPreference {
  category: string
  tag: string
  weight: number
  is_new: boolean
}

interface UnifiedChatResponse {
  user_id: string
  session_id: string
  assistant_message: string
  intent: 'travel_planning' | 'general_chat'
  learned_preferences: LearnedPreference[]
  plan: TravelPlan | null
  plan_status: string | null
}

// POIフィードバック用インターフェース
type POIFeedbackType = 'good' | 'bad'
type POICategory = 'activity' | 'food' | 'hotel'

interface POIFeedbackResponse {
  user_id: string
  plan_id: string
  poi_name: string
  feedback_type: POIFeedbackType
  learned_preference: LearnedPreference | null
  message: string
}

// カテゴリ別検索用インターフェース
interface POISearchResult {
  name: string
  category: POICategory
  location: string
  description: string
  price_range: string
  duration_minutes: number | null
  opening_hours: string
  rating: number | null
  tags: string[]
  source_url: string
  relevance_score: number
  source_name: string
}

interface CategorySearchRequest {
  destination: string
  keywords?: string[]
  constraints?: Record<string, unknown>
}

interface CategorySearchResponse {
  category: POICategory
  destination: string
  items: POISearchResult[]
  total_count: number
  search_time_ms: number
  source: string
}

interface AllCategorySearchResults {
  activity: CategorySearchResponse | null
  food: CategorySearchResponse | null
  hotel: CategorySearchResponse | null
}

export const api = {
  async healthCheck(): Promise<HealthResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/health`)
    return response.json()
  },

  async getLLMHealth(force: boolean = false): Promise<LLMHealthResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/observability/health/llm?force=${force}`)
    return response.json()
  },

  async login(username: string): Promise<LoginResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username }),
    })
    return response.json()
  },

  async checkUsername(username: string): Promise<{ exists: boolean }> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/auth/check/${encodeURIComponent(username)}`)
    return response.json()
  },

  async createUser(): Promise<User> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/preference/users`, {
      method: 'POST',
    })
    return response.json()
  },

  async getUser(userId: string): Promise<User> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/preference/users/${userId}`)
    return response.json()
  },

  async startChat(userId: string): Promise<ChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/preference/chat/start?user_id=${userId}`, {
      method: 'POST',
    })
    return response.json()
  },

  async sendMessage(userId: string, message: string, sessionId?: string): Promise<ChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/preference/chat`, {
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
    return response.json()
  },

  async getUserSignals(userId: string): Promise<PreferenceSignal[]> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/preference/users/${userId}/signals`)
    return response.json()
  },

  // 旅行企画モード
  async startTravelChat(userId: string): Promise<TravelChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/chat/start?user_id=${userId}`, {
      method: 'POST',
    })
    return response.json()
  },

  async sendTravelMessage(userId: string, message: string, sessionId?: string): Promise<TravelChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/chat`, {
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
    return response.json()
  },

  async getTravelPlan(planId: string): Promise<TravelPlan> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/plan/${planId}`)
    return response.json()
  },

  // 長期記憶関連
  async completeLearning(userId: string, sessionId: string): Promise<LearningCompletionResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/preference/learning/complete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        session_id: sessionId,
      }),
    })
    return response.json()
  },

  async sendFeedback(userId: string, planId: string, feedback: string): Promise<TravelFeedbackResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        plan_id: planId,
        feedback: feedback,
      }),
    })
    return response.json()
  },

  // 統合チャット
  async startUnifiedChat(userId: string): Promise<UnifiedChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/chat/start?user_id=${userId}`, {
      method: 'POST',
    })
    return response.json()
  },

  async sendUnifiedMessage(userId: string, message: string, sessionId?: string): Promise<UnifiedChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/chat`, {
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
    return response.json()
  },

  // POIフィードバック
  async sendPOIFeedback(
    userId: string,
    planId: string,
    poiName: string,
    poiCategory: POICategory,
    feedbackType: POIFeedbackType,
    poiTags: string[] = []
  ): Promise<POIFeedbackResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/poi-feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        plan_id: planId,
        poi_name: poiName,
        poi_category: poiCategory,
        feedback_type: feedbackType,
        poi_tags: poiTags,
      }),
    })
    return response.json()
  },

  // カテゴリ別検索
  async searchActivities(request: CategorySearchRequest): Promise<CategorySearchResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/search/activity`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })
    return response.json()
  },

  async searchFoods(request: CategorySearchRequest): Promise<CategorySearchResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/search/food`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })
    return response.json()
  },

  async searchHotels(request: CategorySearchRequest): Promise<CategorySearchResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/search/hotel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })
    return response.json()
  },

  // 全カテゴリ並列検索
  async searchAllCategories(request: CategorySearchRequest): Promise<AllCategorySearchResults> {
    const [activity, food, hotel] = await Promise.allSettled([
      this.searchActivities(request),
      this.searchFoods(request),
      this.searchHotels(request),
    ])

    return {
      activity: activity.status === 'fulfilled' ? activity.value : null,
      food: food.status === 'fulfilled' ? food.value : null,
      hotel: hotel.status === 'fulfilled' ? hotel.value : null,
    }
  },
}

export type { User, UserProfile, PreferenceSignal, ChatResponse, TravelPlan, TravelChatResponse, LearningCompletionResponse, TravelFeedbackResponse, POI, ItineraryItem, DayPlan, Itinerary, LearnedPreference, UnifiedChatResponse, POIFeedbackType, POICategory, POIFeedbackResponse, WorkerHealth, LLMHealthResponse, LoginResponse, POISearchResult, CategorySearchRequest, CategorySearchResponse, AllCategorySearchResults }
