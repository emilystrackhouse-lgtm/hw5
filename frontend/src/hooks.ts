import { useEffect, useRef, useState } from 'react'

/** Call `fn` now and every `ms` milliseconds (the latest fn is always used). */
export function usePoll(fn: () => void | Promise<void>, ms: number, enabled = true) {
  const saved = useRef(fn)
  saved.current = fn
  useEffect(() => {
    if (!enabled) return
    let stop = false
    const tick = async () => {
      if (stop) return
      try { await saved.current() } catch { /* errors are surfaced by the caller */ }
    }
    tick()
    const id = window.setInterval(tick, ms)
    return () => { stop = true; window.clearInterval(id) }
  }, [ms, enabled])
}

/** Smoothly animate a number toward `target` (used for the cash balance). */
export function useTween(target: number | null, duration = 900) {
  const [value, setValue] = useState(target ?? 0)
  const from = useRef<number | null>(target)
  useEffect(() => {
    if (target == null) return
    // First real value: show it immediately instead of counting up from zero.
    if (from.current == null) { from.current = target; setValue(target); return }
    const start = performance.now()
    const begin = from.current
    if (begin === target) return
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduce) { from.current = target; setValue(target); return }
    let raf = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      const v = begin + (target - begin) * eased
      setValue(v)
      from.current = v
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return value
}

/** A per-browser remembered string (the approver's name). Storage can be unavailable. */
export function useStoredString(key: string, initial = '') {
  const [value, setValue] = useState<string>(() => {
    try { return window.localStorage.getItem(key) ?? initial } catch { return initial }
  })
  useEffect(() => {
    try { window.localStorage.setItem(key, value) } catch { /* private mode: keep in memory */ }
  }, [key, value])
  return [value, setValue] as const
}

/** Re-render every second (for elapsed timers). */
export function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [active])
  return now
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
