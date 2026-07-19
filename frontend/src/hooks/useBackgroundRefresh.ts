import { useCallback, useRef } from 'react'
import useInterval from './useInterval'

const REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes

interface RefetchCallbacks {
  refetchSummary: () => void
  refetchPositions: () => void
  refetchWatchlist: () => void
}

/**
 * Silently refreshes Robinhood portfolio data every 5 minutes.
 * Only triggers refetch callbacks; does NOT touch briefs or news.
 */
export default function useBackgroundRefresh(
  enabled: boolean,
  callbacks: RefetchCallbacks
) {
  const callbacksRef = useRef(callbacks)
  callbacksRef.current = callbacks

  const refresh = useCallback(() => {
    callbacksRef.current.refetchSummary()
    callbacksRef.current.refetchPositions()
    callbacksRef.current.refetchWatchlist()
  }, [])

  useInterval(refresh, enabled ? REFRESH_INTERVAL : null)
}
