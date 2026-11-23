/** Пересчёт долей: сумма всегда 100, лишняя единица — первым элементам. */

export function redistribute(n: number): number[] {
  if (n <= 0) throw new Error('n must be positive')
  const base = Math.floor(100 / n)
  const extra = 100 % n
  return Array.from({ length: n }, (_, i) => (i < extra ? base + 1 : base))
}
