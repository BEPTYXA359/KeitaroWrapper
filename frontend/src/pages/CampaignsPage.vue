<script setup lang="ts">
/** Список кампаний, известных приложению, со ссылками на редактор и Keitaro.
 *  Кампанию, созданную мимо приложения, можно открыть по её id в Keitaro.
 */

import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, ApiError, type CampaignListItem } from '../api'
import IconExternalLink from '../components/IconExternalLink.vue'
import UiButton from '../components/UiButton.vue'
import UiInput from '../components/UiInput.vue'

const router = useRouter()

const items = ref<CampaignListItem[]>([])
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')

const keitaroId = ref('')
const linking = ref(false)
const linkError = ref('')

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    items.value = await api.listCampaigns()
    loaded.value = true
  } catch (error) {
    loadError.value = error instanceof ApiError ? error.detail : 'Не удалось загрузить кампании'
  } finally {
    loading.value = false
  }
}

/** Связать кампанию Keitaro с приложением и открыть её потоки в редакторе. */
async function openExisting(): Promise<void> {
  linkError.value = ''
  const raw = keitaroId.value.trim()
  const id = Number(raw)
  if (!/^\d+$/.test(raw) || !Number.isSafeInteger(id) || id <= 0) {
    linkError.value = 'Введите id кампании в Keitaro — целое положительное число'
    return
  }
  linking.value = true
  try {
    const campaign = await api.linkCampaign(id)
    await router.push({ name: 'streams', params: { uuid: campaign.uuid } })
  } catch (error) {
    linkError.value = error instanceof ApiError ? error.detail : 'Не удалось открыть кампанию'
  } finally {
    linking.value = false
  }
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(date)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section>
    <div class="page-head">
      <h1 class="page-title">Campaigns</h1>
      <div class="page-head__actions">
        <UiButton
          v-if="loaded && items.length"
          variant="secondary"
          :loading="loading"
          @click="load"
        >
          REFRESH
        </UiButton>
        <UiButton variant="primary" href="/">NEW CAMPAIGN</UiButton>
      </div>
    </div>

    <form class="campaigns__open" @submit.prevent="openExisting">
      <UiInput
        v-model="keitaroId"
        class="campaigns__open-field"
        label="Keitaro ID"
        placeholder="Например 1234"
        mono
      />
      <UiButton variant="secondary" type="submit" :loading="linking">OPEN</UiButton>
      <span class="muted campaigns__open-hint">
        кампания, созданная в Keitaro, — откроется в редакторе
      </span>
    </form>
    <p v-if="linkError" class="error-banner campaigns__open-error">{{ linkError }}</p>

    <p v-if="loading && !loaded" class="muted">Загрузка…</p>

    <div v-else-if="loadError && !loaded" class="error-banner campaigns__error">
      <p>{{ loadError }}</p>
      <UiButton variant="secondary" :loading="loading" @click="load">RETRY</UiButton>
    </div>

    <p v-else-if="!items.length" class="muted empty-state">
      Нет кампаний — создайте новую или откройте существующую по id
    </p>

    <table v-else class="campaigns__table">
      <thead>
        <tr>
          <th class="campaigns__th-left">Campaign</th>
          <th class="campaigns__th-left">UUID</th>
          <th>Keitaro ID</th>
          <th>Added</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.uuid">
          <td>
            <router-link
              :to="`/campaigns/${item.uuid}/streams`"
              class="campaigns__link"
            >
              {{ item.name }}
            </router-link>
          </td>
          <td class="mono muted campaigns__small">{{ item.uuid }}</td>
          <td class="mono campaigns__small">{{ item.keitaro_campaign_id ?? '—' }}</td>
          <td class="mono muted campaigns__small">{{ formatDate(item.created_at) }}</td>
          <td class="campaigns__actions">
            <UiButton
              variant="secondary"
              size="sm"
              :href="`/campaigns/${item.uuid}/streams`"
            >
              OPEN STREAMS
            </UiButton>
            <UiButton
              v-if="item.admin_url"
              variant="secondary"
              size="sm"
              :href="item.admin_url"
              external
            >
              VIEW IN KT
              <IconExternalLink />
            </UiButton>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
/* форма «открыть по id»: кнопка выровнена по полю, а не по подписи над ним */
.campaigns__open {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.campaigns__open-field {
  width: 200px;
}

.campaigns__open-hint {
  padding-bottom: 10px;
  font-size: 12px;
}

.campaigns__open-error {
  max-width: 720px;
  margin-bottom: var(--space-3);
}

.campaigns__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  max-width: 720px;
}

.campaigns__table {
  width: 100%;
  border-collapse: collapse;
}

.campaigns__table th {
  padding: var(--space-1) 0;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-text-muted);
  text-align: right;
}

/* специфичность как у .campaigns__table th — иначе проиграет text-align: right */
.campaigns__table th.campaigns__th-left {
  text-align: left;
}

.campaigns__table td {
  height: 44px;
  padding: 0;
  border-top: 1px solid var(--c-border);
  text-align: right;
}

.campaigns__table td:first-child,
.campaigns__table td:nth-child(2) {
  text-align: left;
}

.campaigns__table tbody tr:hover {
  background: var(--c-surface);
}

.campaigns__link {
  color: var(--c-text);
}

.campaigns__link:hover {
  text-decoration: underline;
}

.campaigns__small {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.campaigns__actions {
  white-space: nowrap;
}

.campaigns__actions > * + * {
  margin-left: var(--space-2);
}
</style>
