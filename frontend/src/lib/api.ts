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

// 構造化フォーム入力
interface TravelPlanFormData {
  user_id: string
  destination: string
  start_date: string       // "YYYY-MM-DD"
  end_date: string         // "YYYY-MM-DD"
  departure_place?: string
  budget_total?: number
  num_people: number
  transportation?: string
  accommodation_type?: string
  free_text: string
}

// 新しい旅行企画フロー用
interface BasicTravelInfo {
  user_id: string
  area: string             // 観光エリア（例: 京都、箱根）
  start_date: string       // "YYYY-MM-DD"
  end_date: string         // "YYYY-MM-DD"
  num_people: number
  budget: number           // 予算（円）- 必須
  // 4カテゴリ（任意）
  activity_preferences?: string
  food_preferences?: string
  accommodation_type?: string
  transportation?: string
}

interface CollectedTravelInfo {
  area: string
  start_date: string
  end_date: string
  num_people: number
  budget?: number
  budget_per_person?: number
  transportation?: string
  accommodation_type?: string
  food_preferences?: string[]
  activity_preferences?: string[]
  must_visit?: string[]
  avoid?: string[]
  pace?: string            // ゆっくり / 普通 / アクティブ
  special_requests?: string
}

interface RequiredInfoStatus {
  has_activities: boolean  // 体験・観光
  has_food: boolean  // 食
  has_accommodation: boolean  // 宿
  has_transportation: boolean  // 交通
  category_count: number  // 収集済みカテゴリ数
  is_complete: boolean  // 2カテゴリ以上揃っているか
}

interface TravelGatheringResponse {
  session_id: string
  assistant_message: string
  collected_info: CollectedTravelInfo
  // 新しい必須情報管理
  required_info_status: RequiredInfoStatus
  all_required_satisfied: boolean  // 必須情報が全て揃ったか
  missing_required_info: string[]  // 不足している必須情報
  missing_optional_info: string[]  // 不足している任意情報
  // 既存フィールド（互換性）
  is_ready: boolean        // 情報収集が十分かどうか
  missing_info: string[]   // まだ収集していない情報のリスト
}

// ジオ情報付き旅程
interface GeoEnrichedPOI {
  name: string
  category: string
  latitude: number | null
  longitude: number | null
  description: string
}

interface GeoEnrichedDay {
  day_number: number
  pois: GeoEnrichedPOI[]
  route_geometry: { type: string; coordinates: number[][] } | null
  total_distance_km: number | null
  total_duration_minutes: number | null
}

interface GeoEnrichedItinerary {
  days: GeoEnrichedDay[]
}

// POI詳細情報
interface POIDetail {
  name: string
  category: string
  description: string | null
  location: string | null
  address: string | null
  rating: number | null
  review_count: number | null
  price_level: number | null
  price_range: string | null
  budget_per_person: number | null
  hours: Record<string, string> | null
  duration_minutes: number | null
  features: string[]
  tags: string[]
  experiences: string[]
  source_url: string | null
  source_name: string | null
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

  /**
   * ストリーミングでメッセージを送信
   * @param userId ユーザーID
   * @param message メッセージ
   * @param sessionId セッションID
   * @param onChunk チャンク受信時のコールバック
   * @param onSignals シグナル受信時のコールバック
   * @param onDone 完了時のコールバック
   * @param onError エラー時のコールバック
   */
  async sendMessageStream(
    userId: string,
    message: string,
    sessionId: string | undefined,
    onChunk: (content: string) => void,
    onSignals?: (signals: PreferenceSignal[]) => void,
    onDone?: (sessionId: string) => void,
    onError?: (error: string) => void,
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/preference/chat/stream`, {
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
      const error = await response.text()
      onError?.(error)
      throw new Error(error)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('Response body is not readable')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6)
            if (!jsonStr.trim()) continue

            try {
              const data = JSON.parse(jsonStr)
              switch (data.type) {
                case 'chunk':
                  onChunk(data.content)
                  break
                case 'signals':
                  onSignals?.(data.signals)
                  break
                case 'done':
                  onDone?.(data.session_id)
                  break
                case 'error':
                  onError?.(data.message)
                  break
              }
            } catch (e) {
              console.warn('Failed to parse SSE data:', jsonStr)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
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

  // ジオ情報付与
  async enrichItineraryGeo(itinerary: Itinerary, destination: string = ''): Promise<GeoEnrichedItinerary> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/geo/enrich-itinerary`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        itinerary: itinerary,
        destination: destination,
      }),
    })
    return response.json()
  },

  // 構造化フォームからプラン生成
  async submitTravelForm(data: TravelPlanFormData): Promise<TravelChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/plan-with-form`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
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

  // 新しい旅行企画フロー
  // 基本情報を送信してセッション開始
  async startTravelGathering(data: BasicTravelInfo): Promise<TravelGatheringResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/gathering/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
    return response.json()
  },

  // 情報収集の対話
  async sendGatheringMessage(
    userId: string,
    message: string,
    sessionId: string,
  ): Promise<TravelGatheringResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/gathering/chat`, {
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

  // 情報収集の対話（ストリーミング）
  async sendGatheringMessageStream(
    userId: string,
    message: string,
    sessionId: string,
    onChunk: (content: string) => void,
    onInfo?: (info: CollectedTravelInfo) => void,
    onDone?: (response: TravelGatheringResponse) => void,
    onError?: (error: string) => void,
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/travel/gathering/chat/stream`, {
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
      const error = await response.text()
      onError?.(error)
      throw new Error(error)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('Response body is not readable')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6)
            if (!jsonStr.trim()) continue

            try {
              const data = JSON.parse(jsonStr)
              switch (data.type) {
                case 'chunk':
                  onChunk(data.content)
                  break
                case 'info':
                  onInfo?.(data.collected_info)
                  break
                case 'done':
                  onDone?.(data)
                  break
                case 'error':
                  onError?.(data.message)
                  break
              }
            } catch (e) {
              console.warn('Failed to parse SSE data:', jsonStr)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },

  // 収集した情報でプラン生成開始
  async startPlanGeneration(
    userId: string,
    sessionId: string,
    collectedInfo: CollectedTravelInfo,
  ): Promise<TravelChatResponse> {
    const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/travel/plan/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        session_id: sessionId,
        collected_info: collectedInfo,
      }),
    })
    return response.json()
  },

  // POI詳細取得
  async getPOIDetail(
    poiName: string,
    destination?: string,
    category?: string,
  ): Promise<POIDetail> {
    const params = new URLSearchParams()
    if (destination) params.append('destination', destination)
    if (category) params.append('category', category)
    const queryString = params.toString()
    const url = `${API_BASE_URL}/api/travel/poi/${encodeURIComponent(poiName)}${queryString ? `?${queryString}` : ''}`
    const response = await fetchWithErrorHandling(url)
    return response.json()
  },
}

export type { User, UserProfile, PreferenceSignal, ChatResponse, TravelPlan, TravelChatResponse, LearningCompletionResponse, TravelFeedbackResponse, POI, ItineraryItem, DayPlan, Itinerary, LearnedPreference, UnifiedChatResponse, POIFeedbackType, POICategory, POIFeedbackResponse, WorkerHealth, LLMHealthResponse, LoginResponse, POISearchResult, CategorySearchRequest, CategorySearchResponse, AllCategorySearchResults, GeoEnrichedPOI, GeoEnrichedDay, GeoEnrichedItinerary, TravelPlanFormData, BasicTravelInfo, CollectedTravelInfo, RequiredInfoStatus, TravelGatheringResponse, POIDetail }
