import { useEffect, useState } from 'react'
import { listServices } from '../services/api'
import type { ServiceInfo } from '../types/api'

interface UseServicesResult {
  services: ServiceInfo[]
  loading: boolean
  error: string | null
}

/** GET /api/services once on mount -- the catalog rarely changes at runtime. */
export function useServices(): UseServicesResult {
  const [services, setServices] = useState<ServiceInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listServices()
      .then((result) => {
        if (!cancelled) {
          setServices(result)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load services')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  return { services, loading, error }
}
