/** Типизированный клиент к /api*: единая обработка ошибок. */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      ...init,
    })
  } catch {
    // fetch падает только при проблемах сети/DNS
    throw new ApiError(0, 'Бэкенд недоступен — проверьте, что uvicorn запущен')
  }

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body: unknown = await resp.json()
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        const d = (body as { detail: unknown }).detail
        detail = typeof d === 'string' ? d : JSON.stringify(d)
      }
    } catch {
      // тело не JSON — остаётся HTTP-код
    }
    throw new ApiError(resp.status, detail)
  }

  return (await resp.json()) as T
}

// --- Типы ответов ---

export interface HealthResponse {
  status: string
  database: string
}

export interface ConfigResponse {
  campaign_prefix: string
}

export interface OfferSearchItem {
  id: number
  name: string
  state: string | null
}

export interface CreatedCampaignResponse {
  uuid: string
  keitaro_campaign_id: number
  name: string
  streams_created: number
  admin_url: string
}

// --- Эндпоинты ---

export const api = {
  health: () => request<HealthResponse>('/api/health'),
  config: () => request<ConfigResponse>('/api/config'),
  createCampaign: (payload: { name: string; geo: string; offer_id: number }) =>
    request<CreatedCampaignResponse>('/api/campaigns', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  searchOffers: (q: string) =>
    request<OfferSearchItem[]>(`/api/offers/search?q=${encodeURIComponent(q)}`),
}
