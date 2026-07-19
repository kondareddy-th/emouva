import { useState, useEffect, useRef, useCallback, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { C, SERIF, MONO, SANS } from '../data/agentMockData'
import { Dia } from '../components/trading/primitives'
import { useMarketStatus } from '../hooks/useMarketStatus'

/* ══════════════════════════════════════════════════════════════════════
   Emouva — Marketing Landing Page (Agentic Trading)
   High-fidelity port of design_handoff_landing_page/Emouva Landing.dc.html.
   All copy is Munger-voice and part of the design — preserved verbatim.
   Inline-style driven for pixel accuracy. No icon library; the only motif
   is the gold rotated-square "diamond" (<Dia/>).
   ══════════════════════════════════════════════════════════════════════ */

// ── Ledger script types ────────────────────────────────────────────────
type Kind = 'check' | 'screen' | 'pass' | 'exec'
interface ScriptEntry {
  time: string
  kind: Kind
  mono?: string
  order?: string
  orderNote?: string
  body: string
  quote?: string
  link?: string
}

const HEADS: [string, string][] = [
  ['Trade from your machine.', 'Share it in the community.'],
  ['The Partner trades.', 'You hold the mandate.'],
  ['Most days it does nothing.', 'That is the point.'],
  ['Hire a partner,', 'not another app.'],
]

const PRE_SCRIPT: ScriptEntry[] = [
  { time: '09:31', kind: 'check', body: 'Pre-market review. Futures are noisy; the theses are quiet. No action.' },
  {
    time: '09:42',
    kind: 'screen',
    mono: '214 screened → 12 in circle → 4 margin ≥30% → 1 passed inversion',
    body: 'Costco survived every attempt to kill it. Order drafted — it exceeds your limit, so it waits for you below.',
    link: 'See who fell out, and why →',
  },
  { time: '09:58', kind: 'pass', body: 'Ford at margin +41% — killed by inversion. One union negotiation away from a broken thesis.' },
  {
    time: '10:12',
    kind: 'pass',
    body: 'NVDA up 4.1% on momentum. No thesis has changed — chasing strength is not in the mandate.',
    quote: '“Envy of a rising ticker is a terrible reason to own it.”',
  },
  {
    time: '10:31',
    kind: 'exec',
    order: 'SELL 60 OXY @ $71.22',
    orderNote: 'realized +$1,842',
    body: 'Position crossed the 9% ceiling. Trimmed back to size — the thesis stands; the sizing rule stands taller.',
  },
  { time: '10:47', kind: 'check', body: 'Checked all 214 names. Touched nothing.' },
]

const POST_SCRIPT: ScriptEntry[] = [
  {
    time: '11:30',
    kind: 'check',
    body: 'Prices moved. Theses didn’t. No action.',
    quote: '“Mostly, the job is sitting.”',
  },
  { time: '12:04', kind: 'pass', body: 'AAPL trades 10% above my fair value. Watching, not selling — never interrupt compounding unnecessarily.' },
  { time: '12:34', kind: 'check', body: 'Cash above the floor, drift inside the bands. Nothing to do, so nothing was done.' },
]

const BADGE: Record<Kind, { label: string; bg: string; color: string }> = {
  check: { label: 'PORTFOLIO CHECK', bg: 'rgba(255,255,255,0.05)', color: C.secondary },
  screen: { label: 'MORNING SCREEN', bg: 'rgba(207,174,98,0.14)', color: C.gold },
  pass: { label: 'PASSED', bg: 'rgba(255,255,255,0.05)', color: C.secondary },
  exec: { label: 'EXECUTED', bg: 'rgba(127,227,169,0.16)', color: C.gain },
}

const MAX_WIDTH = 1240
const SECTION_PAD = 'clamp(64px,8vw,104px) 24px'

// prefers-reduced-motion (evaluated once; drives cursor/entrance choices)
const prefersReduced =
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false

// ── Small shared pieces ─────────────────────────────────────────────────
function Overline({ text }: { text: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
      <Dia size={6} />
      <span style={{ font: `11px ${MONO}`, letterSpacing: '0.16em', color: C.gold }}>{text}</span>
    </div>
  )
}

const h2Style: CSSProperties = {
  margin: '0 0 14px',
  font: `500 clamp(30px,3.4vw,42px) ${SERIF}`,
  lineHeight: 1.12,
  color: C.textPrimary,
  textWrap: 'balance',
}

// ── Typing headline hook ────────────────────────────────────────────────
// Mirrors the prototype htick(): first pair fully typed on load, hold 3.8s,
// delete @12ms/char, 380ms gap, type next @34-76ms jittered, repeat forever.
function useTypingHeadline() {
  const firstLen = HEADS[0][0].length + HEADS[0][1].length
  const [hIdx, setHIdx] = useState(0)
  const [hChars, setHChars] = useState(firstLen)
  const [hPhase, setHPhase] = useState<'typing' | 'pausing' | 'deleting'>('pausing')
  const timer = useRef<ReturnType<typeof setTimeout>>()

  // keep latest state in refs so the tick loop reads current values
  const s = useRef({ hIdx, hChars, hPhase })
  s.current = { hIdx, hChars, hPhase }

  useEffect(() => {
    const tick = () => {
      const { hIdx: idx, hChars: chars, hPhase: phase } = s.current
      const pair = HEADS[idx]
      const total = pair[0].length + pair[1].length
      let delay: number
      if (phase === 'pausing') {
        setHPhase('deleting')
        delay = 40
      } else if (phase === 'deleting') {
        if (chars > 0) {
          setHChars(chars - 1)
          delay = 12
        } else {
          setHIdx((idx + 1) % HEADS.length)
          setHPhase('typing')
          delay = 380
        }
      } else {
        if (chars < total) {
          setHChars(chars + 1)
          delay = 34 + Math.random() * 42
        } else {
          setHPhase('pausing')
          delay = 3800
        }
      }
      timer.current = setTimeout(tick, delay)
    }
    // first pair is fully typed; hold 3.8s before the cycle begins
    timer.current = setTimeout(tick, 3800)
    return () => clearTimeout(timer.current)
  }, [])

  // resolve the two visible lines + trailing cursor
  const pair = HEADS[hIdx]
  const A = pair[0]
  const B = pair[1]
  let hA: string
  let hB: string
  if (hChars <= A.length) {
    hA = A.slice(0, hChars)
    hB = ''
  } else {
    hA = A
    hB = B.slice(0, hChars - A.length)
  }
  if (hPhase !== 'pausing' && !prefersReduced) {
    if (hB.length > 0 || hChars > A.length) hB += '|'
    else hA += '|'
  }
  return { hA, hB }
}

export default function Landing() {
  const mkt = useMarketStatus()
  // ── config flags (tweakable A/B props from the prototype) ──────────────
  const CTA_TEXT: Record<'account' | 'paper', string> = { account: 'Post your P&L', paper: 'Start paper trading' }
  const ctaVariant: 'account' | 'paper' = 'account'
  const showContrast = true
  const ctaText = CTA_TEXT[ctaVariant]

  // ── headline ───────────────────────────────────────────────────────────
  const { hA, hB } = useTypingHeadline()

  // ── ledger feed state ────────────────────────────────────────────────────
  const [arrivedPre, setArrivedPre] = useState(0)
  const [approvalShown, setApprovalShown] = useState(false)
  const [approval, setApproval] = useState<'pending' | 'approved' | 'declined'>('pending')
  const [arrivedPost, setArrivedPost] = useState(0)

  // ── controls ─────────────────────────────────────────────────────────────
  const [threshold, setThreshold] = useState(25000)
  const [paused, setPaused] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const timers = useRef<ReturnType<typeof setTimeout>[]>([])
  const toastTimer = useRef<ReturnType<typeof setTimeout>>()
  const trackEl = useRef<HTMLDivElement | null>(null)

  // ── mount: schedule pre-approval feed + the awaiting-approval card ────────
  useEffect(() => {
    const gaps = [500, 1200, 1400, 1500, 1900, 2100]
    let t = 0
    gaps.forEach((g, i) => {
      t += g
      timers.current.push(setTimeout(() => setArrivedPre(i + 1), t))
    })
    timers.current.push(setTimeout(() => setApprovalShown(true), t + 2200))
    return () => {
      timers.current.forEach(clearTimeout)
      clearTimeout(toastTimer.current)
    }
  }, [])

  const showToast = useCallback((msg: string) => {
    clearTimeout(toastTimer.current)
    setToast(msg)
    toastTimer.current = setTimeout(() => setToast(null), 3800)
  }, [])

  const decide = useCallback(
    (kind: 'approved' | 'declined') => {
      setApproval((prev) => {
        if (prev !== 'pending') return prev
        showToast(
          kind === 'approved'
            ? 'Order placed — bought 40 COST at $912.63 avg.'
            : 'Declined. The Partner logged your veto — no questions asked.'
        )
        ;[1700, 5600, 10400].forEach((d, i) => {
          timers.current.push(setTimeout(() => setArrivedPost(i + 1), d))
        })
        return kind
      })
    },
    [showToast]
  )

  const togglePause = useCallback(() => {
    setPaused((prev) => {
      const next = !prev
      showToast(next ? 'The Partner is paused. It will keep writing to the Ledger.' : 'Resumed. Next check in 26 minutes.')
      return next
    })
  }, [showToast])

  // ── slider drag ───────────────────────────────────────────────────────────
  const updateFromX = useCallback((clientX: number) => {
    const el = trackEl.current
    if (!el) return
    const r = el.getBoundingClientRect()
    let p = (clientX - r.left) / r.width
    p = Math.max(0, Math.min(1, p))
    let v = 1000 + p * 99000
    v = Math.round(v / 500) * 500
    setThreshold(v)
  }, [])

  const sliderDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault()
      try {
        if (e.currentTarget.setPointerCapture) e.currentTarget.setPointerCapture(e.pointerId)
      } catch {
        /* pointer capture not supported */
      }
      setDragging(true)
      updateFromX(e.clientX)
    },
    [updateFromX]
  )
  const sliderMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (dragging) updateFromX(e.clientX)
    },
    [dragging, updateFromX]
  )
  const sliderUp = useCallback(() => setDragging(false), [])

  // ── derived ledger view ──────────────────────────────────────────────────
  const keepPre = approvalShown ? Math.max(2, 5 - arrivedPost) : 6
  const preArr = PRE_SCRIPT.slice(Math.max(0, arrivedPre - keepPre), arrivedPre)
  const postArr = POST_SCRIPT.slice(0, arrivedPost)
  const pending = approvalShown && approval === 'pending'

  let checks = 0
  let acts = 0
  PRE_SCRIPT.slice(0, arrivedPre).forEach((e) => {
    if (e.kind === 'check' || e.kind === 'screen') checks += 1
    if (e.kind === 'exec') acts += 1
  })
  postArr.forEach((e) => {
    if (e.kind === 'check') checks += 1
  })
  if (approval === 'approved') acts += 1

  const footerLeft = paused
    ? 'Paused — watching, not trading'
    : pending
    ? 'Waiting on your approval · order #1847 · expires 15:55 ET'
    : `Next check ${['11:30', '12:04', '12:34', '13:04'][arrivedPost] || '13:04'} ET · every 30 min`
  const footerRight = `Checked ${checks}× today · acted ${acts === 1 ? 'once' : `${acts}×`}`

  // ── threshold derived ────────────────────────────────────────────────────
  const fmt = '$' + threshold.toLocaleString('en-US')
  const fillPct = ((threshold - 1000) / 99000) * 100
  const thresholdNote =
    threshold >= 36500
      ? `At ${fmt}, this morning’s $36,496 Costco buy would have executed on its own — you’d have read about it in the Ledger, not approved it.`
      : `At ${fmt}, this morning’s $36,496 Costco buy waits for you. Anything smaller, the Partner handles alone — and still shows its work.`

  // ── shared button styles ─────────────────────────────────────────────────
  const goldBtn: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 9,
    borderRadius: 6,
    background: C.gold,
    color: C.bg,
    fontWeight: 600,
    textDecoration: 'none',
    transition: 'background 0.15s',
    cursor: 'pointer',
    border: 'none',
  }
  const outlineBtn: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 9,
    borderRadius: 6,
    border: `1px solid ${'rgba(180,220,190,0.28)'}`,
    color: C.body,
    fontWeight: 500,
    textDecoration: 'none',
    transition: 'border-color 0.15s',
    cursor: 'pointer',
    background: 'transparent',
  }

  // ── ledger entry renderer ────────────────────────────────────────────────
  const renderEntry = (e: ScriptEntry, key: string, withLink: boolean) => {
    const b = BADGE[e.kind]
    return (
      <div
        key={key}
        className={prefersReduced ? undefined : 'em-fade'}
        style={{ display: 'flex', gap: 14, padding: '15px 0', borderBottom: `1px solid ${C.borderRow}` }}
      >
        <span
          style={{
            flex: '0 0 44px',
            font: `11px ${MONO}`,
            color: C.faint,
            paddingTop: 2,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {e.time}
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <span
            style={{
              display: 'inline-block',
              font: `600 9.5px ${SANS}`,
              letterSpacing: '0.11em',
              padding: '3px 8px',
              borderRadius: 4,
              marginBottom: 8,
              background: b.bg,
              color: b.color,
            }}
          >
            {b.label}
          </span>
          {e.order && (
            <p style={{ margin: '0 0 6px', font: `500 13.5px ${SANS}`, color: C.textPrimary }}>
              {e.order}{' '}
              <span style={{ font: `12px ${MONO}`, color: C.gain, fontVariantNumeric: 'tabular-nums' }}>
                {e.orderNote}
              </span>
            </p>
          )}
          {e.mono && (
            <p
              style={{
                margin: '0 0 7px',
                font: `11.5px ${MONO}`,
                color: C.secondary,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {e.mono}
            </p>
          )}
          <p style={{ margin: 0, font: `12.5px ${SANS}`, lineHeight: 1.55, color: C.muted }}>{e.body}</p>
          {e.quote && (
            <p style={{ margin: '6px 0 0', font: `italic 13.5px ${SERIF}`, color: C.gold }}>{e.quote}</p>
          )}
          {withLink && e.link && (
            <Link
              to="/trading"
              style={{
                display: 'inline-block',
                marginTop: 6,
                font: `11.5px ${SANS}`,
                color: C.secondary,
                textDecoration: 'underline',
                textUnderlineOffset: 3,
                textDecorationColor: 'rgba(180,220,190,0.3)',
              }}
            >
              {e.link}
            </Link>
          )}
        </div>
      </div>
    )
  }

  // ── mandate hard-limit chip ──────────────────────────────────────────────
  const chip = (amber = false): CSSProperties => ({
    font: `11px ${MONO}`,
    color: amber ? C.warning : C.secondary,
    padding: '6px 11px',
    border: `1px solid ${amber ? C.amberBorder : C.border}`,
    borderRadius: 6,
    background: C.bg,
  })

  return (
    <div
      style={{
        minHeight: '100vh',
        background: C.bg,
        color: C.body,
        font: `14px ${SANS}`,
        lineHeight: 1.55,
      }}
    >
      {/* ══════════ TOP BAR ══════════ */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: C.topBar,
          borderBottom: `1px solid ${C.borderDim}`,
          backdropFilter: 'blur(8px)',
        }}
      >
        <div
          style={{
            maxWidth: MAX_WIDTH,
            margin: '0 auto',
            padding: '0 24px',
            height: 54,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
            <Dia size={10} />
            <span style={{ font: `500 13px ${SANS}`, letterSpacing: '0.22em', color: C.lightGold }}>EMOUVA</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                padding: '4px 10px',
                border: `1px solid ${C.border}`,
                borderRadius: 5,
              }}
            >
              <div
                className={prefersReduced || !mkt?.open ? undefined : 'em-pulse-dot'}
                style={{ width: 6, height: 6, borderRadius: '50%', background: mkt?.open ? C.gain : C.muted }}
              />
              <span style={{ font: `10.5px ${MONO}`, color: C.secondary, letterSpacing: '0.04em' }}>
                {mkt ? `${mkt.label} · ${mkt.et}`.toUpperCase() : '—'}
              </span>
            </div>
            <a
              href="https://github.com/kondareddy-th/emouva"
              target="_blank"
              rel="noreferrer"
              style={{ font: `13px ${SANS}`, color: C.gold, textDecoration: 'none' }}
            >
              Open source ↗
            </a>
            <Link to="/community" style={{ font: `13px ${SANS}`, color: C.secondary, textDecoration: 'none' }}>
              Community
            </Link>
            <Link to="/trading" style={{ font: `13px ${SANS}`, color: C.secondary, textDecoration: 'none' }}>
              The demo
            </Link>
            <Link to="/login" style={{ font: `13px ${SANS}`, color: C.secondary, textDecoration: 'none' }}>
              Sign in
            </Link>
            <Link to="/community" style={{ ...goldBtn, padding: '8px 16px', font: `600 13px ${SANS}` }}>
              {ctaText}
            </Link>
          </div>
        </div>
      </div>

      {/* ══════════ OPEN-SOURCE ANNOUNCEMENT ══════════ */}
      <a
        href="https://github.com/kondareddy-th/emouva"
        target="_blank"
        rel="noreferrer"
        style={{
          display: 'block',
          background: C.goldTint,
          borderBottom: `1px solid ${C.goldBorder}`,
          textDecoration: 'none',
          padding: '9px 24px',
          textAlign: 'center',
        }}
      >
        <span style={{ font: `600 9.5px ${MONO}`, letterSpacing: '0.14em', color: C.bg, background: C.gold, borderRadius: 4, padding: '2px 7px', marginRight: 10, verticalAlign: 'middle' }}>NEW</span>
        <span style={{ font: `12.5px ${SANS}`, color: C.body, verticalAlign: 'middle' }}>
          Emouva is now <span style={{ color: C.lightGold, fontWeight: 600 }}>fully open source</span> — the entire platform, yours to run on your own machine.{' '}
          <span style={{ color: C.gold, textDecoration: 'underline', textUnderlineOffset: 3 }}>Get the code ↗</span>
        </span>
      </a>

      {/* ══════════ HERO ══════════ */}
      <div style={{ borderBottom: `1px solid ${C.borderDim}` }}>
        <div
          style={{
            maxWidth: MAX_WIDTH,
            margin: '0 auto',
            padding: 'clamp(56px,7vw,96px) 24px clamp(56px,7vw,88px)',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 56,
            alignItems: 'flex-start',
          }}
        >
          {/* Left: message */}
          <div style={{ flex: '1 1 460px', minWidth: 0, maxWidth: 620 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 26 }}>
              <Dia size={6} />
              <span style={{ font: `11px ${MONO}`, letterSpacing: '0.16em', color: C.gold }}>
                AGENTIC TRADING · OPEN SOURCE · UNDER A HUMAN MANDATE
              </span>
            </div>
            <h1
              style={{
                margin: '0 0 22px',
                font: `500 clamp(42px,4.8vw,58px) ${SERIF}`,
                lineHeight: 1.06,
                minHeight: '2.24em',
                letterSpacing: '-0.01em',
                color: C.textPrimary,
                textWrap: 'balance',
              }}
            >
              {hA}
              <br />
              <span style={{ color: C.gold }}>{hB}</span>
            </h1>
            <p style={{ margin: '0 0 30px', font: `16.5px ${SANS}`, lineHeight: 1.65, color: C.secondary, maxWidth: 520, textWrap: 'pretty' }}>
              Emouva runs your portfolio the way the best investors actually work: screen everything, buy rarely, explain
              every move. The Partner checks the market every 30 minutes — and asks your permission for anything over your
              limit.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', marginBottom: 16 }}>
              <Link to="/community" style={{ ...goldBtn, padding: '13px 24px', font: `600 14px ${SANS}` }}>
                {ctaText} <span style={{ fontFamily: MONO }}>→</span>
              </Link>
              <Link to="/trading" style={{ ...outlineBtn, padding: '13px 22px', font: `500 14px ${SANS}` }}>
                Watch it work — the live demo
              </Link>
            </div>
            <p style={{ margin: 0, font: `11px ${MONO}`, color: C.faint, letterSpacing: '0.03em' }}>
              Free and open source. Starts on paper money, not real risk —{' '}
              <a href="https://github.com/kondareddy-th/emouva" target="_blank" rel="noreferrer" style={{ color: C.secondary }}>
                read every line on GitHub ↗
              </a>
              .
            </p>

            <div style={{ marginTop: 44, paddingTop: 28, borderTop: `1px solid ${C.borderDim}`, maxWidth: 520 }}>
              <p style={{ margin: 0, font: `italic 17px ${SERIF}`, lineHeight: 1.6, color: C.gold }}>
                “The big money is not in the buying and the selling, but in the waiting.”
              </p>
              <p style={{ margin: '6px 0 0', font: `10.5px ${MONO}`, letterSpacing: '0.1em', color: C.faint }}>
                — CHARLIE MUNGER, THE PARTNER'S TEMPERAMENT
              </p>
            </div>
          </div>

          {/* Right: live ledger */}
          <div style={{ flex: '1 1 440px', minWidth: 0, maxWidth: 600 }}>
            <div
              style={{
                background: C.card,
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                overflow: 'hidden',
                boxShadow: '0 24px 60px rgba(0,0,0,0.35)',
              }}
            >
              {/* header strip */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '13px 18px',
                  background: C.raised,
                  borderBottom: `1px solid ${C.borderDim}`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>THE LEDGER</span>
                  <span
                    style={{
                      font: `500 9.5px ${MONO}`,
                      letterSpacing: '0.11em',
                      padding: '2px 7px',
                      borderRadius: 4,
                      background: 'rgba(127,227,169,0.14)',
                      color: C.gain,
                    }}
                  >
                    LIVE
                  </span>
                </div>
                <span style={{ font: `10.5px ${MONO}`, color: C.muted, fontVariantNumeric: 'tabular-nums' }}>
                  NET LIQ $487,320 · DAY <span style={{ color: C.gain }}>+0.66%</span>
                </span>
              </div>

              {/* feed area */}
              <div style={{ padding: '4px 18px 14px', minHeight: 430 }}>
                {/* pre-approval feed */}
                {preArr.map((e) => renderEntry(e, `pre-${e.time}`, true))}

                {/* 11:02 Awaiting approval — interactive */}
                {approvalShown && (
                  <div style={{ padding: '15px 0', borderBottom: `1px solid ${C.borderRow}` }}>
                    <div style={{ display: 'flex', gap: 14 }}>
                      <span
                        style={{
                          flex: '0 0 44px',
                          font: `11px ${MONO}`,
                          color: C.faint,
                          paddingTop: 2,
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        11:02
                      </span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        {pending && (
                          <div
                            style={{
                              background: C.goldTint,
                              border: `1px solid ${'rgba(207,174,98,0.32)'}`,
                              borderRadius: 8,
                              padding: 14,
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 9 }}>
                              <span
                                className={prefersReduced ? undefined : 'em-pulse'}
                                style={{
                                  display: 'inline-block',
                                  font: `600 9.5px ${SANS}`,
                                  letterSpacing: '0.11em',
                                  padding: '3px 8px',
                                  borderRadius: 4,
                                  background: C.gold,
                                  color: C.bg,
                                }}
                              >
                                AWAITING YOUR APPROVAL
                              </span>
                              <span style={{ font: `10.5px ${MONO}`, color: C.faint }}>order #1847</span>
                            </div>
                            <p style={{ margin: '0 0 7px', font: `500 13.5px ${SANS}`, color: C.textPrimary }}>
                              Buy 40 COST · Costco Wholesale @ $912.40{' '}
                              <span style={{ font: `12px ${MONO}`, color: C.secondary, fontVariantNumeric: 'tabular-nums' }}>
                                ≈ $36,496
                              </span>
                            </p>
                            <p style={{ margin: '0 0 12px', font: `12px ${SANS}`, lineHeight: 1.55, color: C.muted }}>
                              Exceeds your $25,000 limit, so I'm asking. Inside the circle, fair value $1,380, margin 34%,
                              survived inversion. Sized at 8.5% — under your 9% ceiling.
                            </p>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              <button
                                onClick={() => decide('approved')}
                                style={{ ...goldBtn, padding: '9px 18px', font: `600 12.5px ${SANS}` }}
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => decide('declined')}
                                style={{ ...outlineBtn, padding: '9px 18px', font: `500 12.5px ${SANS}` }}
                              >
                                Decline
                              </button>
                              <span style={{ font: `10px ${MONO}`, color: C.faint }}>try it — this one is live</span>
                            </div>
                          </div>
                        )}

                        {approval === 'approved' && (
                          <div style={{ border: `1px solid ${C.greenBorder}`, borderRadius: 8, padding: 14 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 8 }}>
                              <span
                                style={{
                                  display: 'inline-block',
                                  font: `600 9.5px ${SANS}`,
                                  letterSpacing: '0.11em',
                                  padding: '3px 8px',
                                  borderRadius: 4,
                                  background: 'rgba(127,227,169,0.16)',
                                  color: C.gain,
                                }}
                              >
                                EXECUTED
                              </span>
                              <span style={{ font: `10.5px ${MONO}`, color: C.faint }}>order #1847 · 11:06 ET</span>
                            </div>
                            <p style={{ margin: '0 0 6px', font: `500 13.5px ${SANS}`, color: C.textPrimary }}>
                              Bought 40 COST @ $912.63 avg{' '}
                              <span style={{ font: `12px ${MONO}`, color: C.gain, fontVariantNumeric: 'tabular-nums' }}>
                                filled in two lots
                              </span>
                            </p>
                            <p style={{ margin: 0, font: `12px ${SANS}`, lineHeight: 1.55, color: C.muted }}>
                              Approved by you. Cash reserve now 10.7% — above your 10% floor. The thesis, sizing math, and
                              exit triggers are written down. Nothing about this trade is a mystery.
                            </p>
                          </div>
                        )}

                        {approval === 'declined' && (
                          <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: 14 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 8 }}>
                              <span
                                style={{
                                  display: 'inline-block',
                                  font: `600 9.5px ${SANS}`,
                                  letterSpacing: '0.11em',
                                  padding: '3px 8px',
                                  borderRadius: 4,
                                  background: 'rgba(255,255,255,0.05)',
                                  color: C.muted,
                                }}
                              >
                                DECLINED
                              </span>
                              <span style={{ font: `10.5px ${MONO}`, color: C.faint }}>order #1847 · 11:06 ET</span>
                            </div>
                            <p style={{ margin: 0, font: `12px ${SANS}`, lineHeight: 1.55, color: C.muted }}>
                              Understood. I won't resubmit COST for 30 days unless the thesis materially improves. Vetoes
                              are part of the mandate — you never owe me a reason.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* post-decision feed */}
                {postArr.map((e) => renderEntry(e, `post-${e.time}`, false))}
              </div>

              {/* footer strip */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '11px 18px',
                  background: C.raised,
                  borderTop: `1px solid ${C.borderDim}`,
                }}
              >
                <span style={{ font: `10.5px ${MONO}`, color: C.faint, fontVariantNumeric: 'tabular-nums' }}>
                  {footerLeft}
                </span>
                <span style={{ font: `11px ${SANS}`, color: C.faint }}>{footerRight}</span>
              </div>
            </div>
            <p style={{ margin: '12px 4px 0', font: `10.5px ${MONO}`, color: C.faint, textAlign: 'right' }}>
              A real morning from the demo portfolio —{' '}
              <Link to="/trading" style={{ color: C.secondary }}>
                open the full product →
              </Link>
            </p>
          </div>
        </div>
      </div>

      {/* ══════════ PROOF STRIP ══════════ */}
      <div style={{ background: C.raised, borderBottom: `1px solid ${C.borderDim}` }}>
        <div style={{ maxWidth: MAX_WIDTH, margin: '0 auto', padding: '36px 24px 30px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 28 }}>
            <div>
              <p style={{ margin: 0, font: `500 34px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
                214
              </p>
              <p style={{ margin: '2px 0 4px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                STOCKS SCREENED THIS MORNING
              </p>
              <p style={{ margin: 0, font: `12.5px ${SANS}`, color: C.muted }}>Twelve survived the circle. One was bought.</p>
            </div>
            <div>
              <p style={{ margin: 0, font: `500 34px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
                11
              </p>
              <p style={{ margin: '2px 0 4px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                TRADES YEAR TO DATE
              </p>
              <p style={{ margin: 0, font: `italic 14px ${SERIF}`, color: C.gold }}>Few, by design.</p>
            </div>
            <div>
              <p style={{ margin: 0, font: `500 34px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
                71%
              </p>
              <p style={{ margin: '2px 0 4px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                WIN RATE · 14-MONTH MEDIAN HOLD
              </p>
              <p style={{ margin: 0, font: `12.5px ${SANS}`, color: C.muted }}>Held like an owner, not a renter.</p>
            </div>
            <div>
              <p style={{ margin: 0, font: `500 34px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
                0
              </p>
              <p style={{ margin: '2px 0 4px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                UNEXPLAINED ACTIONS
              </p>
              <p style={{ margin: 0, font: `12.5px ${SANS}`, color: C.muted }}>Every move — and every pass — cites a principle.</p>
            </div>
          </div>
          <p style={{ margin: '22px 0 0', font: `10px ${MONO}`, color: C.disabled, textAlign: 'right' }}>
            LIVE DEMO PORTFOLIO · YTD 2026
          </p>
        </div>
      </div>

      {/* ══════════ HOW IT DECIDES ══════════ */}
      <div style={{ borderBottom: `1px solid ${C.borderDim}` }}>
        <div style={{ maxWidth: MAX_WIDTH, margin: '0 auto', padding: SECTION_PAD }}>
          <Overline text="HOW IT DECIDES" />
          <h2 style={{ ...h2Style, maxWidth: 640 }}>An elimination, every morning at 09:42.</h2>
          <p style={{ margin: '0 0 44px', font: `15.5px ${SANS}`, lineHeight: 1.65, color: C.secondary, maxWidth: 600, textWrap: 'pretty' }}>
            The Partner doesn't hunt for reasons to buy. It hunts for reasons not to — and acts only on what survives. Four
            gates, in order:
          </p>

          {/* funnel — flex so the survivor stretches full-width on wrap */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              background: C.borderDim,
              border: `1px solid ${C.borderDim}`,
              borderRadius: 10,
              overflow: 'hidden',
            }}
          >
            <div style={{ flex: '1 1 220px', minWidth: 0, background: C.bg, padding: '24px 22px' }}>
              <p style={{ margin: 0, font: `500 44px ${SERIF}`, color: C.muted, fontVariantNumeric: 'tabular-nums' }}>214</p>
              <p style={{ margin: '2px 0 12px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                THE UNIVERSE
              </p>
              <p style={{ margin: 0, font: `12.5px ${SANS}`, lineHeight: 1.6, color: C.muted }}>
                Everything liquid enough to own. Most of it will never matter.
              </p>
            </div>
            <div style={{ flex: '1 1 220px', minWidth: 0, background: C.bg, padding: '24px 22px' }}>
              <p style={{ margin: 0, font: `500 44px ${SERIF}`, color: C.secondary, fontVariantNumeric: 'tabular-nums' }}>12</p>
              <p style={{ margin: '2px 0 12px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                INSIDE THE CIRCLE
              </p>
              <p style={{ margin: '0 0 10px', font: `12.5px ${SANS}`, lineHeight: 1.6, color: C.muted }}>
                Businesses the Partner can actually explain.
              </p>
              <p style={{ margin: 0, font: `11px ${MONO}`, lineHeight: 1.7, color: C.faint }}>
                NVDA out — semis capex cycle
                <br />
                LLY out — pipeline risk
                <br />
                TSLA out — narrative-priced
              </p>
            </div>
            <div style={{ flex: '1 1 220px', minWidth: 0, background: C.bg, padding: '24px 22px' }}>
              <p style={{ margin: 0, font: `500 44px ${SERIF}`, color: C.body, fontVariantNumeric: 'tabular-nums' }}>4</p>
              <p style={{ margin: '2px 0 12px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                MARGIN OF SAFETY ≥ 30%
              </p>
              <p style={{ margin: '0 0 10px', font: `12.5px ${SANS}`, lineHeight: 1.6, color: C.muted }}>
                Priced well below what they're worth.
              </p>
              <p style={{ margin: 0, font: `11px ${MONO}`, lineHeight: 1.7, color: C.faint }}>
                COST +34 · F +41 · KHC +38 · T +33
                <br />
                <span style={{ color: C.loss }}>F, KHC, T — killed by inversion</span>
              </p>
            </div>
            <div
              style={{
                flex: '1 1 220px',
                minWidth: 0,
                background: C.raised,
                padding: '24px 22px',
                boxShadow: 'inset 0 0 0 1px rgba(207,174,98,0.30)',
              }}
            >
              <p style={{ margin: 0, font: `500 44px ${SERIF}`, color: C.gold, fontVariantNumeric: 'tabular-nums' }}>1</p>
              <p style={{ margin: '2px 0 12px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.gold }}>
                THE SURVIVOR — COST
              </p>
              <p style={{ margin: '0 0 10px', font: `12.5px ${SANS}`, lineHeight: 1.6, color: C.secondary }}>
                Fair value $1,380. Margin 34%. Sized at 8.5% of the book — then sent to you, because it's over your limit.
              </p>
              <Link
                to="/trading"
                style={{
                  font: `12px ${SANS}`,
                  color: C.gold,
                  textDecoration: 'underline',
                  textUnderlineOffset: 3,
                  textDecorationColor: 'rgba(207,174,98,0.4)',
                }}
              >
                Walk through the real screen →
              </Link>
            </div>
          </div>

          <p style={{ margin: '32px 0 0', font: `italic 17px ${SERIF}`, color: C.gold, textAlign: 'center' }}>
            “An idea isn't yours until you can state the other side better than they can.”
          </p>
        </div>
      </div>

      {/* ══════════ THE MANDATE ══════════ */}
      <div style={{ borderBottom: `1px solid ${C.borderDim}` }}>
        <div style={{ maxWidth: MAX_WIDTH, margin: '0 auto', padding: SECTION_PAD, display: 'flex', flexWrap: 'wrap', gap: 56 }}>
          <div style={{ flex: '1 1 420px', minWidth: 0, maxWidth: 560 }}>
            <Overline text="THE MANDATE" />
            <h2 style={h2Style}>It can act alone. Only as far as you allow.</h2>
            <p style={{ margin: '0 0 26px', font: `15.5px ${SANS}`, lineHeight: 1.65, color: C.secondary, textWrap: 'pretty' }}>
              You write the rules in plain English. Below your dollar limit, the Partner executes and shows its work. Above
              it, nothing moves until you approve — on your phone or in the app.
            </p>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 26 }}>
              <span style={chip()}>Max position 9.0%</span>
              <span style={chip()}>Cash floor 10%</span>
              <span style={chip()}>Max 3 orders / week</span>
              <span style={chip()}>Sector cap 30%</span>
              <span style={chip(true)}>Options &amp; leverage — OUTSIDE MANDATE</span>
            </div>
            <p style={{ margin: 0, font: `13px ${SANS}`, lineHeight: 1.65, color: C.muted, textWrap: 'pretty' }}>
              Limits are constitutional. The Partner cannot cross them —{' '}
              <em style={{ font: `14.5px ${SERIF}`, color: C.secondary }}>even with your approval on a single order.</em>{' '}
              Changing one requires a backtest, like a principle.
            </p>
          </div>

          <div style={{ flex: '1 1 420px', minWidth: 0, maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* Threshold slider card */}
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 22 }}>
              <p style={{ margin: '0 0 4px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                AUTONOMY · TRY THE DIAL
              </p>
              <p style={{ margin: '0 0 18px', font: `15px ${SANS}`, color: C.body }}>
                Ask my approval above{' '}
                <span style={{ font: `22px ${SERIF}`, color: C.lightGold, fontVariantNumeric: 'tabular-nums' }}>{fmt}</span>
              </p>
              <div
                ref={trackEl}
                onPointerDown={sliderDown}
                onPointerMove={sliderMove}
                onPointerUp={sliderUp}
                style={{ position: 'relative', height: 28, cursor: 'pointer', touchAction: 'none' }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: 12.5,
                    left: 0,
                    right: 0,
                    height: 3,
                    borderRadius: 2,
                    background: 'rgba(255,255,255,0.08)',
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    top: 12.5,
                    left: 0,
                    height: 3,
                    borderRadius: 2,
                    background: C.gold,
                    width: `${fillPct}%`,
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    top: 6,
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    background: C.lightGold,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.5)',
                    left: `calc(${fillPct}% - 8px)`,
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                <span style={{ font: `10px ${MONO}`, color: C.faint }}>$1k · ask always</span>
                <span style={{ font: `10px ${MONO}`, color: C.faint }}>$100k · fully autonomous</span>
              </div>
              <div
                style={{
                  marginTop: 14,
                  padding: '11px 13px',
                  borderRadius: 8,
                  background: C.goldTintRow,
                  border: `1px solid ${C.goldBorder}`,
                }}
              >
                <p style={{ margin: 0, font: `12.5px ${SANS}`, lineHeight: 1.55, color: C.secondary }}>{thresholdNote}</p>
              </div>
            </div>

            {/* Pause card */}
            <div style={{ background: C.card, border: `1px solid ${C.redBorder}`, borderRadius: 10, padding: 22 }}>
              <p style={{ margin: '0 0 4px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                THE OFF SWITCH
              </p>
              <p style={{ margin: '0 0 14px', font: `13px ${SANS}`, lineHeight: 1.6, color: C.muted, textWrap: 'pretty' }}>
                One click. The Partner keeps watching and writing to the Ledger, but stops trading. No confirmation maze, no
                retention flow.
              </p>
              {!paused ? (
                <button
                  onClick={togglePause}
                  style={{
                    padding: '10px 18px',
                    borderRadius: 6,
                    border: `1px solid ${'rgba(242,147,127,0.45)'}`,
                    background: 'transparent',
                    color: C.loss,
                    font: `500 12.5px ${SANS}`,
                    cursor: 'pointer',
                    transition: 'border-color 0.15s',
                  }}
                >
                  Pause the Partner
                </button>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '9px 13px',
                      borderRadius: 6,
                      background: C.amberTint,
                      border: `1px solid ${'rgba(223,182,90,0.35)'}`,
                    }}
                  >
                    <div
                      className={prefersReduced ? undefined : 'em-pulse-dot'}
                      style={{ width: 7, height: 7, borderRadius: '50%', background: C.warning }}
                    />
                    <span style={{ font: `11px ${MONO}`, letterSpacing: '0.08em', color: C.warning }}>
                      PAUSED — watching, not trading
                    </span>
                  </div>
                  <button
                    onClick={togglePause}
                    style={{ ...goldBtn, padding: '9px 16px', font: `600 12.5px ${SANS}` }}
                  >
                    Resume the Partner
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ══════════ THE LATTICEWORK ══════════ */}
      <div style={{ borderBottom: `1px solid ${C.borderDim}` }}>
        <div style={{ maxWidth: MAX_WIDTH, margin: '0 auto', padding: SECTION_PAD }}>
          <Overline text="THE LATTICEWORK" />
          <h2 style={{ ...h2Style, maxWidth: 680 }}>Twelve principles govern every decision.</h2>
          <p style={{ margin: '0 0 40px', font: `15.5px ${SANS}`, lineHeight: 1.65, color: C.secondary, maxWidth: 620, textWrap: 'pretty' }}>
            The Partner must cite one for anything it does — or declines to do. Edit them in your own words. Nothing applies
            until it survives a backtest against your actual history.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(270px,1fr))', gap: 16 }}>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 20 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <Dia size={7} style={{ marginTop: 7 }} />
                <p style={{ margin: 0, font: `italic 16px ${SERIF}`, lineHeight: 1.5, color: C.textPrimary }}>
                  Never interrupt compounding unnecessarily.
                </p>
              </div>
              <p style={{ margin: '14px 0 0', font: `10.5px ${MONO}`, lineHeight: 1.7, color: C.faint }}>
                CORE · MUNGER · invoked 34× this quarter · killed 9 ideas
              </p>
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 20 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <Dia size={7} style={{ marginTop: 7 }} />
                <p style={{ margin: 0, font: `italic 16px ${SERIF}`, lineHeight: 1.5, color: C.textPrimary }}>
                  If the business is outside the circle of competence, the price doesn't matter.
                </p>
              </div>
              <p style={{ margin: '14px 0 0', font: `10.5px ${MONO}`, lineHeight: 1.7, color: C.faint }}>
                CORE · SELECTION · the gate that removed 202 of 214 this morning
              </p>
            </div>
            <div
              style={{ background: C.card, border: `1px solid ${'rgba(207,174,98,0.32)'}`, borderRadius: 10, padding: 20 }}
            >
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <Dia size={7} style={{ marginTop: 7 }} />
                <p style={{ margin: 0, font: `italic 16px ${SERIF}`, lineHeight: 1.5, color: C.textPrimary }}>
                  Prefer quality: gross profitability, low leverage, stable margins. Junk rallies are rented, not owned.
                </p>
              </div>
              <p style={{ margin: '14px 0 0', font: `10.5px ${MONO}`, lineHeight: 1.7, color: C.gold }}>
                FROM RESEARCH · Quality Minus Junk (2014) · backtest +1.6pp CAGR, −6pp drawdown
              </p>
            </div>
          </div>

          <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'stretch' }}>
            <div
              style={{
                flex: '1 1 380px',
                background: C.emphasis,
                border: `1px solid ${C.goldBorder}`,
                borderRadius: 10,
                padding: 20,
              }}
            >
              <p style={{ margin: '0 0 10px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                WRITE YOUR OWN
              </p>
              <div
                style={{
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: '13px 14px',
                  marginBottom: 12,
                }}
              >
                <p style={{ margin: 0, font: `italic 15px ${SERIF}`, color: C.muted }}>
                  “Never buy anything the week before its earnings call.”
                </p>
              </div>
              <p style={{ margin: 0, font: `12.5px ${SANS}`, lineHeight: 1.6, color: C.muted }}>
                Plain English in, discipline out. The Partner restates how it will apply your rule, backtests it against
                your history, and shows what it would have blocked —{' '}
                <span style={{ font: `11px ${MONO}`, color: C.secondary }}>2 of 11 trades · +$310 avoided</span> — before it
                ever applies.
              </p>
            </div>
            <div style={{ flex: '1 1 380px', background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 20 }}>
              <p style={{ margin: '0 0 10px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                FEED IT RESEARCH
              </p>
              <p style={{ margin: '0 0 12px', font: `13px ${SANS}`, lineHeight: 1.65, color: C.secondary, textWrap: 'pretty' }}>
                Drop in a paper. The Partner reads it, distills the gist, tries to kill it three ways, and backtests what
                survives. “Quality Minus Junk” became principle 13. Momentum rotation was rejected —{' '}
                <em style={{ fontFamily: SERIF, color: C.gold }}>40 trades a year violates “sit on your ass.”</em>
              </p>
              <Link
                to="/trading"
                style={{
                  font: `12px ${SANS}`,
                  color: C.secondary,
                  textDecoration: 'underline',
                  textUnderlineOffset: 3,
                  textDecorationColor: 'rgba(180,220,190,0.3)',
                }}
              >
                See a paper get distilled →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* ══════════ NOT A CASINO ══════════ */}
      {showContrast && (
        <div style={{ borderBottom: `1px solid ${C.borderDim}`, background: C.raised }}>
          <div style={{ maxWidth: MAX_WIDTH, margin: '0 auto', padding: SECTION_PAD }}>
            <h2 style={{ ...h2Style, margin: '0 auto 40px', textAlign: 'center', maxWidth: 700 }}>
              Trading apps are paid when you trade.
              <br />
              <span style={{ color: C.gold }}>Emouva is free, and open source.</span>
            </h2>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, maxWidth: 960, margin: '0 auto' }}>
              <div style={{ flex: '1 1 380px', background: C.bg, border: `1px solid ${C.borderDim}`, borderRadius: 10, padding: 24 }}>
                <p style={{ margin: '0 0 16px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.faint }}>
                  THE AVERAGE TRADING APP
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.muted }}>Confetti on your first options trade.</p>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.muted }}>
                    Streaks, badges, and a push alert at 6:12 a.m.
                  </p>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.muted }}>A feed engineered to make you act.</p>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.muted }}>“Free” trades — your churn is the product.</p>
                </div>
              </div>
              <div
                style={{ flex: '1 1 380px', background: C.card, border: `1px solid ${'rgba(207,174,98,0.32)'}`, borderRadius: 10, padding: 24 }}
              >
                <p style={{ margin: '0 0 16px', font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.gold }}>EMOUVA</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.body }}>A ledger, not a feed.</p>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.body }}>
                    Passes recorded with the same care as trades.
                  </p>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.body }}>Four checks a day. One action a fortnight.</p>
                  <p style={{ margin: 0, font: `13.5px ${SANS}`, color: C.body }}>
                    Free and open source — no fee, and nothing to gain from your churn.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════ HOW YOU START ══════════ */}
      <div style={{ borderBottom: `1px solid ${C.borderDim}` }}>
        <div style={{ maxWidth: MAX_WIDTH, margin: '0 auto', padding: SECTION_PAD }}>
          <h2 style={{ ...h2Style, marginBottom: 44 }}>Three steps. The third one is waiting.</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(250px,1fr))', gap: 36 }}>
            <div>
              <p style={{ margin: '0 0 10px', font: `30px ${SERIF}`, color: C.lightGold, fontVariantNumeric: 'tabular-nums' }}>01</p>
              <p style={{ margin: '0 0 8px', font: `600 16px ${SANS}`, color: C.textPrimary }}>Write the mandate</p>
              <p style={{ margin: 0, font: `13.5px ${SANS}`, lineHeight: 1.65, color: C.muted, textWrap: 'pretty' }}>
                Your limits, your cadence, your approval threshold — in plain English, in about five minutes.
              </p>
            </div>
            <div>
              <p style={{ margin: '0 0 10px', font: `30px ${SERIF}`, color: C.lightGold, fontVariantNumeric: 'tabular-nums' }}>02</p>
              <p style={{ margin: '0 0 8px', font: `600 16px ${SANS}`, color: C.textPrimary }}>Watch it on paper</p>
              <p style={{ margin: 0, font: `13.5px ${SANS}`, lineHeight: 1.65, color: C.muted, textWrap: 'pretty' }}>
                Two weeks of real decisions with simulated money. Every screen, every pass, every order — written down and
                explained.
              </p>
            </div>
            <div>
              <p style={{ margin: '0 0 10px', font: `30px ${SERIF}`, color: C.lightGold, fontVariantNumeric: 'tabular-nums' }}>03</p>
              <p style={{ margin: '0 0 8px', font: `600 16px ${SANS}`, color: C.textPrimary }}>Fund it when convinced</p>
              <p style={{ margin: 0, font: `13.5px ${SANS}`, lineHeight: 1.65, color: C.muted, textWrap: 'pretty' }}>
                Connect your brokerage. Approvals come to your phone. The pause switch is always one click away.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ══════════ FINAL CTA ══════════ */}
      <div id="open">
        <div style={{ maxWidth: MAX_WIDTH, margin: '0 auto', padding: 'clamp(80px,10vw,130px) 24px', textAlign: 'center' }}>
          <p
            style={{
              margin: '0 0 18px',
              font: `italic 500 clamp(34px,4.2vw,54px) ${SERIF}`,
              lineHeight: 1.15,
              color: C.textPrimary,
              textWrap: 'balance',
            }}
          >
            “Mostly, the job is sitting.”
          </p>
          <p style={{ margin: '0 auto 34px', font: `15.5px ${SANS}`, lineHeight: 1.65, color: C.secondary, maxWidth: 520, textWrap: 'pretty' }}>
            The rest is knowing when not to. Watch the Partner work a real morning in the demo — then put it on your own
            portfolio, free and open source, on paper money first.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center', marginBottom: 14 }}>
            <Link to="/community" style={{ ...goldBtn, padding: '14px 28px', font: `600 14.5px ${SANS}` }}>
              {ctaText} <span style={{ fontFamily: MONO }}>→</span>
            </Link>
            <Link to="/trading" style={{ ...outlineBtn, padding: '14px 26px', font: `500 14.5px ${SANS}` }}>
              Tour the live demo
            </Link>
          </div>
          <p style={{ margin: 0, font: `11px ${MONO}`, color: C.faint }}>
            Free and open source · starts on paper money · self-host it or{' '}
            <a href="https://github.com/kondareddy-th/emouva" target="_blank" rel="noreferrer" style={{ color: C.secondary }}>
              star it on GitHub ↗
            </a>
          </p>
        </div>
      </div>

      {/* ══════════ FOOTER ══════════ */}
      <div style={{ borderTop: `1px solid ${C.borderDim}`, background: C.raised }}>
        <div
          style={{
            maxWidth: MAX_WIDTH,
            margin: '0 auto',
            padding: '28px 24px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 18,
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Dia size={8} />
            <span style={{ font: `500 12px ${SANS}`, letterSpacing: '0.22em', color: C.lightGold }}>EMOUVA</span>
          </div>
          <a
            href="https://github.com/kondareddy-th/emouva"
            target="_blank"
            rel="noreferrer"
            style={{ font: `10px ${MONO}`, letterSpacing: '0.13em', color: C.secondary, textDecoration: 'none' }}
          >
            OPEN SOURCE · GITHUB ↗
          </a>
          <p style={{ margin: 0, font: `10px ${MONO}`, lineHeight: 1.7, color: C.disabled, maxWidth: 640 }}>
            © 2026 EMOUVA · Free &amp; open source (MIT). Emouva is a technology platform, not a registered investment
            adviser. Paper trading is simulated. Live markets involve risk, including loss of principal. Demo-portfolio
            figures are illustrative.
          </p>
        </div>
      </div>

      {/* ══════════ TOAST ══════════ */}
      {toast !== null && (
        <div
          className={prefersReduced ? undefined : 'em-toast'}
          style={{
            position: 'fixed',
            bottom: 28,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '11px 18px',
            borderRadius: 8,
            background: C.toast,
            border: `1px solid ${C.goldBorderStrong}`,
            boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
          }}
        >
          <Dia size={7} />
          <span style={{ font: `12.5px ${SANS}`, color: C.body, whiteSpace: 'nowrap' }}>{toast}</span>
        </div>
      )}
    </div>
  )
}
