/** Закрепления долей (пины) — состояние редактора, Keitaro их не хранит.
 *
 * Живут в localStorage браузера: переживают перезагрузку страницы и FETCH,
 * но не переносятся между браузерами и машинами.
 */

import type { UiStream } from './streams'

type StoredPins = Record<string, number[]>

function storageKey(campaignUuid: string): string {
  return `keitaro-wrapper:pins:${campaignUuid}`
}

/** Пины кампании из localStorage: stream_id -> множество закреплённых offer_id. */
export function loadPins(campaignUuid: string): Map<number, Set<number>> {
  const result = new Map<number, Set<number>>()
  try {
    const raw = localStorage.getItem(storageKey(campaignUuid))
    if (!raw) return result
    const stored: StoredPins = JSON.parse(raw)
    for (const [streamId, offerIds] of Object.entries(stored)) {
      if (Array.isArray(offerIds)) {
        result.set(Number(streamId), new Set(offerIds.map(Number)))
      }
    }
  } catch {
    // повреждённый JSON или недоступный localStorage — считаем, что пинов нет
  }
  return result
}

/** Сохранить текущие закрепления (заодно чистятся пины исчезнувших офферов). */
export function savePins(campaignUuid: string, streams: UiStream[]): void {
  const stored: StoredPins = {}
  for (const stream of streams) {
    const ids = stream.offers.filter((offer) => offer.pinned).map((offer) => offer.offer_id)
    if (ids.length) stored[String(stream.stream_id)] = ids
  }
  try {
    localStorage.setItem(storageKey(campaignUuid), JSON.stringify(stored))
  } catch {
    // localStorage недоступен (приватный режим, квота) — пины просто не переживут перезагрузку
  }
}
