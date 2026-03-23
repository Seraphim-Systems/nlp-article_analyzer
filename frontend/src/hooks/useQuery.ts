import { useState, useEffect, useCallback } from 'react'

export function useQuery<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
  options: { interval?: number } = {},
) {
  const [data, setData]     = useState<T | null>(null)
  const [loading, setLoad]  = useState(true)
  const [error, setError]   = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const result = await fn()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoad(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    setLoad(true)
    load()
  }, [load])

  useEffect(() => {
    if (!options.interval) return
    const id = setInterval(load, options.interval)
    return () => clearInterval(id)
  }, [load, options.interval])

  return { data, loading, error, reload: load }
}
