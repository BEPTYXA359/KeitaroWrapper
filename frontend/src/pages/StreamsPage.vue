<script setup lang="ts">
/** Редактор потоков кампании: состояние всегда из Keitaro; правки локально (dirty) до PUSH. */

import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, ApiError, type CampaignStreamsResponse, type OfferShare } from '../api'
import IconExternalLink from '../components/IconExternalLink.vue'
import StreamCard from '../components/StreamCard.vue'
import UiButton from '../components/UiButton.vue'
import { toast } from '../composables/toast'
import { loadPins, savePins } from '../lib/pins'
import type { UiStream } from '../lib/streams'

const route = useRoute()
const campaignUuid = route.params.uuid as string

const campaign = ref<CampaignStreamsResponse['campaign'] | null>(null)
const streams = ref<UiStream[]>([])
const dirtyIds = reactive(new Set<number>())
const loading = ref(false)
const pushing = ref(false)
const loaded = ref(false)
const loadError = ref('')

const anyDirty = computed(() => dirtyIds.size > 0)
// во время запроса правки запрещены: перечитывание заменит состояние, и они потеряются
const busy = computed(() => loading.value || pushing.value)
// PUSH запрещён, если в каком-то dirty-потоке не осталось активных офферов
const pushBlocked = computed(() =>
  streams.value.some(
    (stream) => dirtyIds.has(stream.stream_id) && !stream.offers.some((offer) => !offer.removed),
  ),
)

// Пины переживают перезагрузку страницы: при любом изменении сохраняем их в localStorage
watch(streams, () => savePins(campaignUuid, streams.value), { deep: true })

function errorText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.detail : fallback
}

/** Ответ API -> UI-состояние страницы. */
function toUiStreams(data: CampaignStreamsResponse): UiStream[] {
  campaign.value = data.campaign
  // Пин — состояние редактора, Keitaro его не хранит: закрепления восстанавливаются
  // из localStorage, для исчезнувших из потока офферов — сбрасываются.
  const savedPins = loadPins(campaignUuid)
  return data.streams.map((stream) => {
    const pinned = savedPins.get(stream.stream_id)
    return {
      ...stream,
      offers: stream.offers.map((offer) => {
        const removed = offer.state !== 'active'
        return {
          offer_id: offer.offer_id,
          offer_name: offer.offer_name,
          preview_url: offer.preview_url,
          share: removed ? 0 : offer.share,
          removed,
          pinned: !removed && !!pinned?.has(offer.offer_id),
        }
      }),
    }
  })
}

/** Перечитать потоки из Keitaro и сбросить несохранённые правки; false — если не вышло.
 *
 * Офферы, удалённые в админке Keitaro вручную, приходят со state "deleted" («0% +
 * BRING BACK»), но dirty НЕ создают: состояние карточки совпадает с Keitaro, удалять
 * там уже нечего. В Keitaro они вернутся как disabled при следующем реальном PUSH.
 */
async function fetchStreams(): Promise<boolean> {
  loading.value = true
  loadError.value = ''
  try {
    const data = await api.getCampaignStreams(campaignUuid)
    streams.value = toUiStreams(data)
    dirtyIds.clear()
    loaded.value = true
    return true
  } catch (error) {
    loadError.value = errorText(error, 'Не удалось загрузить потоки')
    // данные на экране ещё есть — достаточно тоста, иначе ошибку показываем на месте данных
    if (loaded.value) toast.error(loadError.value)
    return false
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
      // «призраков» бэк сам вернёт в Keitaro как disabled — их состав знает из БД
      try {
        await api.updateStreamOffers(campaignUuid, stream.stream_id, offers)
      } catch (error) {
        // уже отправленные потоки остаются UNSAVED: повторный PUSH отправит то же состояние
        toast.error(
          `Поток «${stream.name}» не сохранён: ${errorText(error, 'не удалось применить изменения')}`,
        )
        return
      }
    }
    if (await fetchStreams()) toast.info('Изменения применены')
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
      <router-link to="/campaigns" class="streams__crumb-link">Campaigns</router-link>
      <span class="streams__crumb-sep">/</span>
      <span>{{ campaign?.name ?? '…' }}</span>
      <span class="streams__crumb-sep">/</span>
      <span class="streams__crumb-current">Keitaro Streams</span>
    </nav>

    <div class="page-head">
      <h1 class="page-title">Keitaro Streams</h1>
      <div class="page-head__actions">
        <UiButton
          v-if="!anyDirty"
          variant="secondary"
          :loading="loading"
          :disabled="pushing"
          @click="fetchStreams"
        >
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
          <UiButton
            variant="secondary"
            :loading="loading"
            :disabled="pushing"
            @click="fetchStreams"
          >
            CANCEL
          </UiButton>
        </template>
        <UiButton v-if="campaign" variant="secondary" :href="campaign.admin_url" external>
          VIEW IN KT
          <IconExternalLink />
        </UiButton>
      </div>
    </div>

    <p v-if="loading && !loaded" class="muted">Загрузка…</p>
    <p v-else-if="loadError && !loaded" class="error-banner">{{ loadError }}</p>
    <p v-else-if="!streams.length" class="muted empty-state">В кампании нет потоков</p>
    <div v-else class="streams__list">
      <StreamCard
        v-for="stream in streams"
        :key="stream.stream_id"
        :stream="stream"
        :dirty="dirtyIds.has(stream.stream_id)"
        :push-blocked="pushBlocked"
        :busy="busy"
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

.streams__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
</style>
