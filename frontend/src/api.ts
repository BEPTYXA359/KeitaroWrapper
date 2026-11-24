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

  if (resp.status === 204) return undefined as T

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
  /** URL оффера; null, если у оффера нет http(s)-адреса */
  preview_url: string | null
}

export interface CreatedCampaignResponse {
  uuid: string
  keitaro_campaign_id: number
  name: string
  streams_created: number
  admin_url: string
}

export interface CampaignListItem {
  uuid: string
  name: string
  keitaro_campaign_id: number | null
  /** ISO 8601 с таймзоной */
  created_at: string
  admin_url: string | null
  /** Кампании больше нет в Keitaro (проверка при загрузке списка) */
  deleted_in_keitaro: boolean
}

export interface StreamFilter {
  name: string
  mode: string
  payload: string[]
}

export interface StreamOffer {
  offer_id: number
  offer_name: string | null
  preview_url: string | null
  share: number
  state: string
}

export interface StreamData {
  stream_id: number
  name: string
  position: number
  schema: string
  filter: StreamFilter | null
  offers: StreamOffer[]
}

export interface CampaignStreamsResponse {
  campaign: { name: string; keitaro_id: number; admin_url: string }
  streams: StreamData[]
}

export interface OfferShare {
  offer_id: number
  share: number
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
  listCampaigns: () => request<CampaignListItem[]>('/api/campaigns'),
  /** Убрать кампанию из локального списка (запись в Keitaro не трогается). */
  deleteCampaign: (uuid: string) => request<void>(`/api/campaigns/${uuid}`, { method: 'DELETE' }),
  /** Связать существующую кампанию Keitaro с приложением, чтобы открыть её в редакторе. */
  linkCampaign: (keitaroCampaignId: number) =>
    request<CampaignListItem>('/api/campaigns/link', {
      method: 'POST',
      body: JSON.stringify({ keitaro_campaign_id: keitaroCampaignId }),
    }),
  getCampaignStreams: (uuid: string) =>
    request<CampaignStreamsResponse>(`/api/campaigns/${uuid}/streams`),
  updateStreamOffers: (uuid: string, streamId: number, offers: OfferShare[]) =>
    request<Record<string, unknown>>(`/api/campaigns/${uuid}/streams/${streamId}`, {
      method: 'PUT',
      body: JSON.stringify({ offers }),
    }),
}
