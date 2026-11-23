<script setup lang="ts">
/** Карточка потока: таблица офферов с долями, REMOVE/BRING BACK, пин доли, добавление через автокомплит.
 *
 * Правки мутируют stream на месте (состояние живёт на странице) и эмитят change —
 * страница помечает поток dirty. Редактируются только потоки со схемой landings:
 * у редиректа и действия Keitaro офферы не ротирует.
 */

import { computed, ref } from 'vue'

import type { OfferSearchItem } from '../api'
import { hasStarvedOffers, recalcShares, type UiOffer, type UiStream } from '../lib/streams'
import IconExternalLink from './IconExternalLink.vue'
import OfferAutocomplete from './OfferAutocomplete.vue'
import UiBadge from './UiBadge.vue'
import UiButton from './UiButton.vue'

const props = defineProps<{
  stream: UiStream
  dirty: boolean
  pushBlocked: boolean
  /** Идёт запрос к серверу: правки заблокированы, чтобы не потерялись при перечитывании */
  busy: boolean
}>()

const emit = defineEmits<{ change: [streamId: number] }>()

const selectedOffer = ref<OfferSearchItem | null>(null)
const addInput = ref<InstanceType<typeof OfferAutocomplete> | null>(null)

const editable = computed(() => props.stream.schema === 'landings')
const activeOffers = computed(() => props.stream.offers.filter((offer) => !offer.removed))
const removedOffers = computed(() => props.stream.offers.filter((offer) => offer.removed))
const totalShare = computed(() => activeOffers.value.reduce((sum, offer) => sum + offer.share, 0))
const pinnedCount = computed(() => activeOffers.value.filter((offer) => offer.pinned).length)
const starved = computed(() => hasStarvedOffers(props.stream))

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

/** Закрепить или открепить долю: сами доли не меняются, меняется только правило пересчёта. */
function togglePin(offer: UiOffer): void {
  offer.pinned = !offer.pinned
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
      preview_url: offer.preview_url,
      share: 0,
      removed: false,
      pinned: false,
    })
  }
  recalcShares(props.stream)
  selectedOffer.value = null
  addInput.value?.clear()
  touch()
}

function removeOffer(offer: UiOffer): void {
  offer.removed = true
  offer.pinned = false // у убранного оффера доли нет — закреплять нечего
  recalcShares(props.stream)
  touch()
}

function bringBack(offer: UiOffer): void {
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

    <template v-if="editable">
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
              <a
                v-if="offer.preview_url"
                class="card__preview"
                :href="offer.preview_url"
                target="_blank"
                rel="noopener"
                :aria-label="`Открыть оффер ${offer.offer_id} в новой вкладке`"
                :title="offer.preview_url"
              >
                <IconExternalLink />
              </a>
            </td>
            <td class="card__share-td">
              <div class="card__share-cell">
                <span class="card__share mono">{{ offer.removed ? '0%' : `${offer.share}%` }}</span>
                <button
                  type="button"
                  class="card__pin"
                  :class="{ 'card__pin--on': offer.pinned }"
                  :disabled="busy || offer.removed"
                  :aria-pressed="offer.pinned"
                  :aria-label="`${offer.pinned ? 'Открепить долю' : 'Закрепить долю'} оффера ${offer.offer_id}`"
                  :title="
                    offer.pinned
                      ? 'Доля закреплена — открепить'
                      : 'Закрепить долю: она не изменится при пересчёте'
                  "
                  @click="togglePin(offer)"
                >
                  <svg
                    class="card__pin-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.75"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                    focusable="false"
                  >
                    <path d="M9 3h6" />
                    <path d="M10 3v5.2L7.6 11h8.8L14 8.2V3" />
                    <path d="M5.5 11h13" />
                    <path d="M12 11v10" />
                  </svg>
                </button>
              </div>
            </td>
            <td class="card__actions">
              <UiButton
                v-if="!offer.removed"
                variant="danger"
                size="sm"
                :disabled="busy"
                @click="removeOffer(offer)"
              >
                REMOVE
              </UiButton>
              <UiButton
                v-else
                variant="secondary"
                size="sm"
                :disabled="busy"
                @click="bringBack(offer)"
              >
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
          {{ activeOffers.length }} active · {{ removedOffers.length }} removed<template v-if="pinnedCount"> · {{ pinnedCount }} pinned</template>
        </span>
      </footer>

      <div class="card__add">
        <div class="card__add-input">
          <OfferAutocomplete ref="addInput" :disabled="busy" @select="onSelect" />
        </div>
        <UiButton
          variant="primary"
          :disabled="busy || !selectedOffer || selectedIsActive"
          @click="addSelected"
        >
          ADD
        </UiButton>
        <span v-if="selectedIsActive" class="muted card__add-hint">уже в потоке</span>
      </div>

      <p v-if="dirty && pushBlocked" class="card__blocked">
        Нет активных офферов — PUSH недоступен, добавьте оффер
      </p>

      <p v-if="starved" class="muted card__blocked">
        Закреплённые офферы занимают всю долю — остальным достаётся 0%
      </p>
    </template>

    <p v-else class="muted card__note">
      {{ stream.schema === 'redirect' ? 'Редирект на URL' : 'Действие над трафиком' }} —
      ротация офферов к этому потоку не применяется
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

.card__table th.card__th-offer {
  text-align: left;
}

.card__table td {
  height: 44px;
  padding: 0;
  border-top: 1px solid var(--c-border);
}

.card__table tbody tr:hover {
  background: var(--c-surface);
}

.card__offer {
  font-size: 13px;
}

.card__offer > * + * {
  margin-left: 8px;
}

.card__oid {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.card__preview {
  display: inline-flex;
  padding: 2px 4px;
  vertical-align: middle;
  color: var(--c-text-muted);
}

.card__preview:hover {
  color: var(--c-text);
}

.card__share-td {
  text-align: right;
}

.card__share-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
}

.card__share {
  font-size: 14px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* пин доли: бледный — не закреплена, чёрный — закреплена */
.card__pin {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  color: var(--c-text-muted);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius);
  transition:
    color 0.12s ease,
    border-color 0.12s ease;
}

.card__pin:not(:disabled):hover {
  color: var(--c-text);
  border-color: var(--c-border-strong);
}

.card__pin--on {
  color: var(--c-text);
}

.card__pin:disabled {
  opacity: 0.4;
  cursor: default;
}

.card__pin-icon {
  width: 14px;
  height: 14px;
  transition: transform 0.12s ease;
}

/* закреплена: поворот на 45° — состояние видно не только по цвету */
.card__pin--on .card__pin-icon {
  transform: rotate(45deg);
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

/* специфичность как у .card__table td — иначе строка получит высоту 44px без отступов */
.card__table td.card__empty {
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

.card__note {
  font-size: 13px;
}
</style>
