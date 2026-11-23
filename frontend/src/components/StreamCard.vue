<script setup lang="ts">
/** Карточка потока: таблица офферов с долями, REMOVE/BRING BACK, добавление через автокомплит.
 *
 * Правки мутируют stream на месте (состояние живёт на странице) и эмитят change —
 * страница помечает поток dirty.
 */

import { computed, ref } from 'vue'

import type { OfferSearchItem } from '../api'
import { recalcShares, type UiStream } from '../lib/streams'
import OfferAutocomplete from './OfferAutocomplete.vue'
import UiBadge from './UiBadge.vue'
import UiButton from './UiButton.vue'

const props = defineProps<{
  stream: UiStream
  dirty: boolean
  pushBlocked: boolean
}>()

const emit = defineEmits<{ change: [streamId: number] }>()

const selectedOffer = ref<OfferSearchItem | null>(null)
const addInput = ref<InstanceType<typeof OfferAutocomplete> | null>(null)

const activeOffers = computed(() => props.stream.offers.filter((offer) => !offer.removed))
const removedOffers = computed(() => props.stream.offers.filter((offer) => offer.removed))
const totalShare = computed(() => activeOffers.value.reduce((sum, offer) => sum + offer.share, 0))

const selectedIsActive = computed(
  () =>
    selectedOffer.value != null &&
    activeOffers.value.some((offer) => offer.offer_id === selectedOffer.value!.id),
)

function touch(): void {
  emit('change', props.stream.stream_id)
}

function onSelect(offer: OfferSearchItem | null): void {
  selectedOffer.value = offer
}

function addSelected(): void {
  const offer = selectedOffer.value
  if (!offer) return
  const existing = props.stream.offers.find((item) => item.offer_id === offer.id)
  if (existing && !existing.removed) return
  if (existing) {
    existing.removed = false // повторное добавление removed-оффера = возврат
  } else {
    props.stream.offers.push({
      offer_id: offer.id,
      offer_name: offer.name,
      share: 0,
      removed: false,
    })
  }
  recalcShares(props.stream)
  selectedOffer.value = null
  addInput.value?.clear()
  touch()
}

function removeOffer(offer: { removed: boolean }): void {
  offer.removed = true
  recalcShares(props.stream)
  touch()
}

function bringBack(offer: { removed: boolean }): void {
  offer.removed = false
  recalcShares(props.stream)
  touch()
}
</script>

<template>
  <section class="card" :class="{ 'card--dirty': dirty }">
    <header class="card__head">
      <h2 class="card__title">Stream: {{ stream.name }}</h2>
      <span class="mono muted card__pos">#{{ stream.position }}</span>
      <UiBadge v-if="stream.filter" variant="neutral">
        <span class="mono card__filter">
          {{ stream.filter.name }}: {{ stream.filter.payload.join(',') }}
        </span>
      </UiBadge>
      <span class="mono muted card__sid">stream_id {{ stream.stream_id }}</span>
      <UiBadge v-if="dirty" variant="solid">unsaved</UiBadge>
    </header>

    <table class="card__table">
      <thead>
        <tr>
          <th class="card__th-offer"><span class="visually-hidden">Offer</span></th>
          <th class="card__th-share">Share</th>
          <th class="card__th-actions">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="offer in stream.offers"
          :key="offer.offer_id"
          :class="{ 'card__row--removed': offer.removed }"
        >
          <td class="card__offer">
            <span class="mono muted card__oid">[{{ offer.offer_id }}]</span>
            <span class="card__oname">{{ offer.offer_name ?? '' }}</span>
          </td>
          <td class="card__share mono">{{ offer.removed ? '0%' : `${offer.share}%` }}</td>
          <td class="card__actions">
            <UiButton v-if="!offer.removed" variant="danger" size="sm" @click="removeOffer(offer)">
              REMOVE
            </UiButton>
            <UiButton v-else variant="secondary" size="sm" @click="bringBack(offer)">
              BRING BACK
            </UiButton>
          </td>
        </tr>
        <tr v-if="!stream.offers.length">
          <td colspan="3" class="muted card__empty">В потоке нет офферов — добавьте первый</td>
        </tr>
      </tbody>
    </table>

    <footer class="card__foot">
      <span class="mono card__sum">Σ {{ totalShare }}%</span>
      <span class="muted card__count">
        {{ activeOffers.length }} active · {{ removedOffers.length }} removed
      </span>
    </footer>

    <div class="card__add">
      <div class="card__add-input">
        <OfferAutocomplete ref="addInput" @select="onSelect" />
      </div>
      <UiButton
        variant="primary"
        :disabled="!selectedOffer || selectedIsActive"
        @click="addSelected"
      >
        ADD
      </UiButton>
      <span v-if="selectedIsActive" class="muted card__add-hint">уже в потоке</span>
    </div>

    <p v-if="dirty && pushBlocked" class="muted card__blocked">
      Нет активных офферов — PUSH недоступен, добавьте оффер
    </p>
  </section>
</template>

<style scoped>
.card {
  position: relative;
  padding: var(--space-4);
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
}

/* dirty: рамка чёрная + полоса 4px слева + бейдж UNSAVED */
.card--dirty {
  border-color: var(--c-border-strong);
}

.card--dirty::before {
  content: '';
  position: absolute;
  top: -1px;
  bottom: -1px;
  left: -1px;
  width: 4px;
  background: var(--c-surface-dark);
}

.card__head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: var(--space-3);
}

.card__title {
  font-size: 14px;
  font-weight: 600;
}

.card__pos,
.card__sid {
  font-size: 12px;
}

.card__filter {
  font-size: 10px;
  letter-spacing: 0.04em;
}

.card__table {
  width: 100%;
  border-collapse: collapse;
}

.card__table th {
  padding: var(--space-1) 0;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-text-muted);
  text-align: right;
}

.card__th-offer {
  text-align: left;
}

.card__table td {
  height: 44px;
  padding: 0;
  border-top: 1px solid var(--c-border);
}

.card__table tr:hover {
  background: var(--c-surface);
}

.card__offer {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.card__oid {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.card__share {
  text-align: right;
  font-size: 14px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.card__actions {
  text-align: right;
}

.card__row--removed {
  opacity: 0.55;
}

.card__row--removed .card__oname {
  text-decoration: line-through;
}

.card__row--removed .card__share {
  color: var(--c-text-muted);
}

.card__empty {
  height: auto;
  padding: var(--space-4) 0;
  font-size: 13px;
}

.card__foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: var(--space-2);
}

.card__sum {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.card__count {
  font-size: 12px;
}

.card__add {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.card__add-input {
  flex: 1;
}

.card__add-hint {
  font-size: 12px;
  line-height: var(--control-h);
  white-space: nowrap;
}

.card__blocked {
  margin-top: var(--space-2);
  font-size: 12px;
}
</style>
