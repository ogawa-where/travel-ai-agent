export enum ErrorCode {
  NETWORK_ERROR = 'NETWORK_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  NOT_FOUND = 'NOT_FOUND',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  TIMEOUT = 'TIMEOUT',
  UNKNOWN = 'UNKNOWN',
}

export class ApiError extends Error {
  code: ErrorCode
  statusCode?: number
  details?: string

  constructor(code: ErrorCode, message: string, statusCode?: number, details?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.statusCode = statusCode
    this.details = details
  }
}

export const getErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) {
    return error.message
  }

  if (error instanceof Error) {
    if (error.message.includes('fetch')) {
      return 'サーバーに接続できません。ネットワーク接続を確認してください。'
    }
    return error.message
  }

  return '予期しないエラーが発生しました。'
}

export const getErrorDetails = (error: unknown): string | null => {
  if (error instanceof ApiError && error.details) {
    return error.details
  }
  return null
}

export const parseApiError = async (response: Response): Promise<ApiError> => {
  const statusCode = response.status

  let details: string | undefined
  try {
    const body = await response.json()
    details = body.detail || body.message || JSON.stringify(body)
  } catch {
    details = await response.text().catch(() => undefined)
  }

  switch (statusCode) {
    case 400:
      return new ApiError(
        ErrorCode.VALIDATION_ERROR,
        '入力内容に問題があります。内容を確認してください。',
        statusCode,
        details
      )
    case 404:
      return new ApiError(
        ErrorCode.NOT_FOUND,
        'リソースが見つかりません。',
        statusCode,
        details
      )
    case 408:
    case 504:
      return new ApiError(
        ErrorCode.TIMEOUT,
        'リクエストがタイムアウトしました。しばらく待ってから再試行してください。',
        statusCode,
        details
      )
    case 500:
    case 502:
    case 503:
      return new ApiError(
        ErrorCode.SERVER_ERROR,
        'サーバーエラーが発生しました。しばらく待ってから再試行してください。',
        statusCode,
        details
      )
    default:
      return new ApiError(
        ErrorCode.UNKNOWN,
        `エラーが発生しました (${statusCode})`,
        statusCode,
        details
      )
  }
}

export const createNetworkError = (): ApiError => {
  return new ApiError(
    ErrorCode.NETWORK_ERROR,
    'サーバーに接続できません。ネットワーク接続を確認してください。'
  )
}
