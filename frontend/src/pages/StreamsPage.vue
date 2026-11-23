<script setup lang="ts">
/** Редактор потоков кампании: состояние всегда из Keitaro; правки локально (dirty) до PUSH. */

import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api, ApiError, type CampaignStreamsResponse, type OfferShare } from '../api'
import StreamCard from '../components/StreamCard.vue'
import UiButton from '../components/UiButton.vue'
import { toast } from '../composables/toast'
import type { UiStream } from '../lib/streams'

const route = useRoute()
const campaignUuid = route.params.uuid as string

const campaign = ref<CampaignStreamsResponse['campaign'] | null>(null)
const streams = ref<UiStream[]>([])
const dirtyIds = reactive(new Set<number>())
const loading = ref(false)
const pushing = ref(false)
const loaded = ref(false)

const anyDirty = computed(() => dirtyIds.size > 0)
// PUSH запрещён, если в каком-то dirty-потоке не осталось активных офферов
const pushBlocked = computed(() =>
  streams.value.some(
    (stream) => dirtyIds.has(stream.stream_id) && !stream.offers.some((offer) => !offer.removed),
  ),
)

function toUiStreams(data: CampaignStreamsResponse): UiStream[] {
  campaign.value = data.campaign
  return data.streams.map((stream) => ({
    ...stream,
    offers: stream.offers.map((offer) => ({
      offer_id: offer.offer_id,
      offer_name: offer.offer_name,
      share: offer.state === 'active' ? offer.share : 0,
      removed: offer.state !== 'active',
    })),
  }))
}

async function fetchStreams(): Promise<void> {
  loading.value = true
  try {
    const data = await api.getCampaignStreams(campaignUuid)
    streams.value = toUiStreams(data)
    dirtyIds.clear()
    loaded.value = true
  } catch (error) {
    toast.error(error instanceof ApiError ? error.detail : 'Не удалось загрузить потоки')
  } finally {
    loading.value = false
  }
}

async function pushAll(): Promise<void> {
  const dirty = streams.value.filter((stream) => dirtyIds.has(stream.stream_id))
  if (!dirty.length) return
  pushing.value = true
  try {
    for (const stream of dirty) {
      const offers: OfferShare[] = stream.offers
        .filter((offer) => !offer.removed)
        .map((offer) => ({ offer_id: offer.offer_id, share: offer.share }))
      await api.updateStreamOffers(campaignUuid, stream.stream_id, offers)
    }
    await fetchStreams()
    toast.info('Изменения применены')
  } catch (error) {
    toast.error(error instanceof ApiError ? error.detail : 'Не удалось применить изменения')
  } finally {
    pushing.value = false
  }
}

function markDirty(streamId: number): void {
  dirtyIds.add(streamId)
}

onMounted(() => {
  void fetchStreams()
})
</script>

<template>
  <section>
    <nav class="streams__crumbs muted">
      <router-link to="/" class="streams__crumb-link">Campaigns</router-link>
      <span class="streams__crumb-sep">/</span>
      <span>{{ campaign?.name ?? '…' }}</span>
      <span class="streams__crumb-sep">/</span>
      <span class="streams__crumb-current">Keitaro Streams</span>
    </nav>

    <div class="streams__head">
      <h1 class="page-title">Keitaro Streams</h1>
      <div class="streams__actions">
        <UiButton v-if="!anyDirty" variant="secondary" :loading="loading" @click="fetchStreams">
          FETCH STREAMS FROM KT
        </UiButton>
        <template v-else>
          <UiButton
            variant="primary"
            :loading="pushing"
            :disabled="pushBlocked"
            @click="pushAll"
          >
            PUSH TO KT
          </UiButton>
          <UiButton variant="secondary" :disabled="pushing" @click="fetchStreams">CANCEL</UiButton>
        </template>
        <UiButton v-if="campaign" variant="secondary" :href="campaign.admin_url" external>
          VIEW IN KT
          <svg
            class="streams__icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </UiButton>
      </div>
    </div>

    <p v-if="!loaded" class="muted">Загрузка…</p>
    <p v-else-if="!streams.length" class="muted streams__empty">В кампании нет потоков</p>
    <div v-else class="streams__list">
      <StreamCard
        v-for="stream in streams"
        :key="stream.stream_id"
        :stream="stream"
        :dirty="dirtyIds.has(stream.stream_id)"
        :push-blocked="pushBlocked"
        @change="markDirty"
      />
    </div>
  </section>
</template>

<style scoped>
.streams__crumbs {
  display: flex;
  align-items: center;
  font-size: 13px;
  margin-bottom: var(--space-4);
}

.streams__crumb-link {
  color: var(--c-text-muted);
}

.streams__crumb-link:hover {
  color: var(--c-text);
}

.streams__crumb-sep {
  padding: 0 4px;
}

.streams__crumb-current {
  color: var(--c-text);
}

.streams__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.streams__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.streams__icon {
  width: 14px;
  height: 14px;
}

.streams__empty {
  padding: 48px;
  text-align: center;
  font-size: 13px;
}

.streams__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
</style>
