/** Строки потока в UI-состоянии страницы: офферы помечены removed вместо state. */

import type { StreamData } from '../api'

import { redistribute } from './shares'

export interface UiOffer {
  offer_id: number
  offer_name: string | null
  preview_url: string | null
  share: number
  removed: boolean
  /** Доля закреплена: не меняется, когда пересчитываются остальные офферы */
  pinned: boolean
}

export type UiStream = Omit<StreamData, 'offers'> & { offers: UiOffer[] }

/**
 * Пересчитать доли активных офферов после изменения состава потока.
 *
 * Закреплённые офферы сохраняют свою долю, остаток (100 − сумма закреплённых)
 * делится между остальными в порядке таблицы; лишний процент — первому.
 */
export function recalcShares(stream: UiStream): void {
  const active = stream.offers.filter((offer) => !offer.removed)
  const pinnedSum = active
    .filter((offer) => offer.pinned)
    .reduce((sum, offer) => sum + offer.share, 0)
  const free = active.filter((offer) => !offer.pinned)
  if (!free.length) return
  const shares = redistribute(free.length, Math.max(0, 100 - pinnedSum))
  free.forEach((offer, i) => {
    offer.share = shares[i]
  })
}

/** Доли закреплены так, что незакреплённым офферам ничего не остаётся. */
export function hasStarvedOffers(stream: UiStream): boolean {
  return stream.offers.some((offer) => !offer.removed && !offer.pinned && offer.share === 0)
}
