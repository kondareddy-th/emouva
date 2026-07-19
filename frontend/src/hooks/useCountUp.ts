import { useEffect, useRef, useState } from 'react'

export default function useCountUp(
  target: number,
  duration = 800,
  decimals = 2
): string {
  const [display, setDisplay] = useState('0')
  const prevTarget = useRef(0)
  const frameRef = useRef<number>()

  useEffect(() => {
    const start = prevTarget.current
    const diff = target - start
    const startTime = performance.now()

    const tick = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = start + diff * eased

      setDisplay(
        current.toLocaleString('en-US', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
      )

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        prevTarget.current = target
      }
    }

    frameRef.current = requestAnimationFrame(tick)
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
  }, [target, duration, decimals])

  return display
}
