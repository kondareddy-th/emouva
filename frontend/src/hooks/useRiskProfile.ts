import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch, apiStream } from '../api/client'
import { EMPTY_RISK_PROFILE, type RiskProfile } from '../data/mockData'

interface UseRiskProfileResult {
  data: RiskProfile
  loading: boolean
  source: 'computed' | 'disconnected'
  refetch: () => void
}

export function useRiskProfile(): UseRiskProfileResult {
  const [data, setData] = useState<RiskProfile>(EMPTY_RISK_PROFILE)
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState<'computed' | 'disconnected'>('disconnected')

  const fetch_ = useCallback(() => {
    setLoading(true)
    apiFetch<RiskProfile>('/api/portfolio/risk-profile')
      .then((res) => {
        setData(res)
        setSource(res.source === 'computed' ? 'computed' : 'disconnected')
      })
      .catch(() => {
        setData(EMPTY_RISK_PROFILE)
        setSource('disconnected')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetch_() }, [fetch_])
  return { data, loading, source, refetch: fetch_ }
}

interface UseRiskNarrativeResult {
  narrative: string
  loading: boolean
  error: string | null
  generate: () => void
}

export function useRiskNarrative(): UseRiskNarrativeResult {
  const [narrative, setNarrative] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  const generate = useCallback(() => {
    // Abort any in-progress stream
    controllerRef.current?.abort()

    setNarrative('')
    setLoading(true)
    setError(null)

    const ctrl = apiStream('/api/portfolio/risk-profile/narrative', {
      onDelta: (data) => {
        setNarrative((prev) => prev + data.text)
      },
      onDone: () => {
        setLoading(false)
      },
      onError: (data) => {
        setError(data.message || 'Narrative generation failed')
        setLoading(false)
      },
    })
    controllerRef.current = ctrl
  }, [])

  useEffect(() => {
    return () => { controllerRef.current?.abort() }
  }, [])

  return { narrative, loading, error, generate }
}
