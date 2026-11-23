/** Пересчёт долей: сумма равна total, лишняя единица — первым элементам. */

export function redistribute(n: number, total = 100): number[] {
  if (n <= 0) throw new Error('n must be positive')
  const base = Math.floor(total / n)
  const extra = total % n
  return Array.from({ length: n }, (_, i) => (i < extra ? base + 1 : base))
}
