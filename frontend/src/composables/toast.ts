/** Тосты: справа-снизу, инверсные; ошибки живут 6s, прочие — 4s. */

import { reactive } from 'vue'

export interface ToastItem {
  id: number
  kind: 'info' | 'error'
  text: string
}

let seq = 0
const timers = new Map<number, ReturnType<typeof setTimeout>>()

export const toasts = reactive<ToastItem[]>([])

function dismiss(id: number): void {
  const timer = timers.get(id)
  if (timer) {
    clearTimeout(timer)
    timers.delete(id)
  }
  const idx = toasts.findIndex((t) => t.id === id)
  if (idx !== -1) toasts.splice(idx, 1)
}

function push(kind: ToastItem['kind'], text: string): void {
  const id = ++seq
  toasts.push({ id, kind, text })
  timers.set(
    id,
    setTimeout(() => dismiss(id), kind === 'error' ? 6000 : 4000),
  )
}

export const toast = {
  info: (text: string) => push('info', text),
  error: (text: string) => push('error', text),
  dismiss,
}
