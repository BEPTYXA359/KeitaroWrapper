<script setup lang="ts">
/** Форма «New campaign»: name / geo / offer -> POST /api/campaigns. */

import { computed, onMounted, reactive, ref } from 'vue'

import { api, ApiError, type CreatedCampaignResponse, type OfferSearchItem } from '../api'
import OfferAutocomplete from './OfferAutocomplete.vue'
import UiBadge from './UiBadge.vue'
import UiButton from './UiButton.vue'
import UiInput from './UiInput.vue'

const emit = defineEmits<{ created: [result: CreatedCampaignResponse] }>()

const prefix = ref('')
const name = ref('')
const geo = ref('')
const selectedOffer = ref<OfferSearchItem | null>(null)

const fieldErrors = reactive<{ name?: string; geo?: string; offer?: string }>({})
const formError = ref('')
const submitting = ref(false)

const finalName = computed(() =>
  name.value.trim() ? `${prefix.value}${name.value.trim()}` : undefined,
)

onMounted(async () => {
  try {
    prefix.value = (await api.config()).campaign_prefix
  } catch {
    // префикс — только подсказка; без него форма всё равно работает
  }
})

function selectOffer(offer: OfferSearchItem | null): void {
  selectedOffer.value = offer
  fieldErrors.offer = undefined
}

function validate(): boolean {
  fieldErrors.name = name.value.trim() ? undefined : 'Укажите название кампании'
  fieldErrors.geo = geo.value.trim() ? undefined : 'Укажите geo-коды (например MX,AU,RO)'
  fieldErrors.offer = selectedOffer.value ? undefined : 'Выберите оффер'
  return !fieldErrors.name && !fieldErrors.geo && !fieldErrors.offer
}

async function submit(): Promise<void> {
  formError.value = ''
  if (!validate()) return
  submitting.value = true
  try {
    const result = await api.createCampaign({
      name: name.value.trim(),
      geo: geo.value.trim(),
      offer_id: selectedOffer.value!.id,
    })
    emit('created', result)
  } catch (error) {
    formError.value = error instanceof ApiError ? error.detail : 'Не удалось создать кампанию'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="submit">
    <div class="form__field">
      <div class="form__label-row">
        <span class="form__label">Name</span>
        <UiBadge v-if="prefix" variant="neutral">{{ prefix }}</UiBadge>
      </div>
      <UiInput
        v-model="name"
        placeholder="campaign1"
        :error="fieldErrors.name"
        :hint="finalName"
      />
    </div>

    <div class="form__field">
      <span class="form__label">Geo</span>
      <UiInput
        v-model="geo"
        placeholder="MX,AU,RO,..."
        mono
        :error="fieldErrors.geo"
      />
    </div>

    <div class="form__field">
      <span class="form__label">Offer</span>
      <OfferAutocomplete :error="fieldErrors.offer" @select="selectOffer" />
    </div>

    <p v-if="formError" class="error-banner">{{ formError }}</p>

    <div>
      <UiButton variant="primary" type="submit" :loading="submitting">Create</UiButton>
    </div>
  </form>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 480px;
}

.form__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form__label-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form__label {
  font-size: 12px;
  font-weight: 500;
}
</style>
