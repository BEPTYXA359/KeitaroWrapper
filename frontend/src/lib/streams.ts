/** Строки потока в UI-состоянии страницы: офферы помечены removed вместо state. */

import type { StreamData } from '../api'

import { redistribute } from './shares'

export interface UiOffer {
  offer_id: number
  offer_name: string | null
  share: number
  removed: boolean
}

export type UiStream = Omit<StreamData, 'offers'> & { offers: UiOffer[] }

/** Пересчитать доли активных офферов; порядок долей = порядок в таблице. */
export function recalcShares(stream: UiStream): void {
  const active = stream.offers.filter((offer) => !offer.removed)
  const shares = redistribute(active.length)
  active.forEach((offer, i) => {
    offer.share = shares[i]
  })
}
