import { useState, useEffect, useRef, useCallback, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import useAuth from '../hooks/useAuth'
import PnlCard, { type PnlStats } from '../components/PnlCard'
import ModeToggle from '../components/ModeToggle'
import {
  COMMUNITY_HOST, isRemoteCommunity, communityFetch, communityLogin,
  communityLogout, communitySignedIn, getCommunityUser, type CommunityUser,
} from '../api/community'

/* ══════════════════════════════════════════════════════════════════════
   Community — one public channel. Anyone can read; sign in to post a
   message or share a Spotify-Wrapped-style P&L card. Refresh-polling feed.
   ══════════════════════════════════════════════════════════════════════ */

interface Post {
  id: string
  kind: string
  author_name: string
  author_handle: string | null
  body: string | null
  stats: PnlStats | null
  created_at: string
  is_mine: boolean
}

const BG = '#0a0e0f'
const CARD = '#141c28'
const LINE = 'rgba(180,220,190,0.12)'
const GOLD = '#cfae62'
const TEXT = '#eef4f2'
const MUTED = 'rgba(238,244,242,0.55)'
const SERIF = "'EB Garamond', Georgia, serif"
const MONO = "'JetBrains Mono', ui-monospace, monospace"
const SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif"

function ago(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export default function Community() {
  const { user: localUser } = useAuth()
  // The room is CENTRAL. On the community host itself, you post as your normal
  // session. On a self-hosted install, you post with an emouva.com account
  // (separate "community token") while all trading data stays local.
  const [remoteUser, setRemoteUser] = useState<CommunityUser | null>(
    isRemoteCommunity && communitySignedIn() ? getCommunityUser() : null,
  )
  const poster = isRemoteCommunity ? remoteUser : localUser
  const [posts, setPosts] = useState<Post[]>([])
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  // share modal
  const [sharing, setSharing] = useState(false)
  const [shareStats, setShareStats] = useState<PnlStats | null>(null)
  const [shareCaption, setShareCaption] = useState('')
  const cardRef = useRef<HTMLDivElement>(null)

  const load = useCallback(() => {
    communityFetch<Post[]>('/api/community/feed').then(setPosts).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  const send = async () => {
    const body = msg.trim()
    if (!body) return
    setMsg('')
    try {
      await communityFetch('/api/community/post', { method: 'POST', body: JSON.stringify({ kind: 'message', body }) })
      load()
    } catch (e: any) {
      alert(String(e?.message || 'Could not post').replace(/^\d+:\s*/, ''))
    }
  }

  const openShare = async () => {
    setBusy(true)
    try {
      // The card reflects the AGENTIC account (where the AI trades), not the user's default.
      const [sum, pos] = await Promise.all([
        apiFetch<any>('/api/portfolio/summary?account=agentic').catch(() => null),
        apiFetch<any>('/api/portfolio/positions?account=agentic').catch(() => null),
      ])
      const positions: any[] = pos?.positions || []
      const num = (v: any) => { const n = Number(v); return v == null || isNaN(n) ? null : n }
      const pShares = (p: any) => num(p.shares) ?? num(p.quantity)
      const pAvg = (p: any) => num(p.avg_cost) ?? num(p.average_buy_price)
      const pPrice = (p: any) => num(p.current_price) ?? num(p.price) ?? num(p.last_price)
      const pVal = (p: any) => {
        const eq = num(p.equity ?? p.market_value ?? p.value)
        if (eq != null) return eq
        const s = pShares(p), pr = pPrice(p)
        return s != null && pr != null ? s * pr : null
      }
      const pCost = (p: any) => {
        const s = pShares(p), a = pAvg(p)
        return s != null && a != null ? s * a : null
      }
      // per-position TOTAL return (since purchase) — falls back to any provided pct
      const pRet = (p: any) => {
        const a = pAvg(p), pr = pPrice(p)
        if (a != null && a > 0 && pr != null) return ((pr - a) / a) * 100
        const c = pCost(p), v = pVal(p)
        if (c != null && c > 0 && v != null) return ((v - c) / c) * 100
        return num(p.total_return_pct ?? p.gain_pct ?? p.unrealized_pnl_pct)
      }

      const byVal = [...positions].sort((a, b) => (pVal(b) ?? 0) - (pVal(a) ?? 0))
      const withRet = positions.filter((p) => pRet(p) != null)
      const best = withRet.length ? withRet.reduce((a, b) => (pRet(b)! > pRet(a)! ? b : a)) : null

      // Total return: prefer the summary, else derive it from positions' cost basis
      // (the Robinhood summary sometimes returns total_gain_pct = 0).
      let portfolioValue = num(sum?.total_value)
      if (portfolioValue == null) portfolioValue = positions.reduce((s, p) => s + (pVal(p) ?? 0), 0) || null
      let totalReturnPct = num(sum?.total_gain_pct)
      let totalGain = num(sum?.total_gain)
      const totalCost = positions.reduce((s, p) => s + (pCost(p) ?? 0), 0)
      if ((totalReturnPct == null || totalReturnPct === 0) && totalCost > 0 && portfolioValue != null) {
        totalGain = portfolioValue - totalCost
        totalReturnPct = (totalGain / totalCost) * 100
      }

      const stats: PnlStats = {
        portfolioValue: portfolioValue ?? undefined,
        totalReturnPct: totalReturnPct ?? undefined,
        totalGain: totalGain ?? undefined,
        dayChangePct: num(sum?.daily_change_pct) ?? undefined,
        positionsCount: positions.length,
        topHolding: byVal[0]?.symbol ?? null,
        bestSymbol: best?.symbol ?? null,
        bestPct: best ? pRet(best) : null,
        generatedAt: new Date().toISOString(),
        source: sum?.source,
      }
      setShareStats(stats)
      setSharing(true)
    } finally {
      setBusy(false)
    }
  }

  const postCard = async () => {
    if (!shareStats) return
    setBusy(true)
    try {
      await communityFetch('/api/community/post', {
        method: 'POST',
        body: JSON.stringify({ kind: 'pnl_card', body: shareCaption.trim() || null, stats: shareStats }),
      })
      setSharing(false)
      setShareCaption('')
      load()
    } catch (e: any) {
      alert(String(e?.message || 'Could not post the card').replace(/^\d+:\s*/, ''))
    } finally {
      setBusy(false)
    }
  }

  const download = async () => {
    const el = cardRef.current
    if (!el) return
    try {
      const mod: any = await import('html2pdf.js')
      const html2pdf = mod.default || mod
      const dataUrl: string = await html2pdf()
        .set({ image: { type: 'png', quality: 1 }, html2canvas: { scale: 2, backgroundColor: null, useCORS: true } })
        .from(el)
        .outputImg('datauristring')
      const a = document.createElement('a')
      a.href = dataUrl
      a.download = 'emouva-pnl.png'
      a.click()
    } catch {
      alert('Could not render the image here — you can screenshot the card instead.')
    }
  }

  const remove = async (id: string) => {
    if (!confirm('Delete this post?')) return
    try {
      await communityFetch(`/api/community/post/${id}`, { method: 'DELETE' })
      load()
    } catch { /* ignore */ }
  }

  const btnGold: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 8, borderRadius: 8, border: 'none',
    background: GOLD, color: BG, fontWeight: 600, cursor: 'pointer', padding: '10px 18px', font: `600 13px ${SANS}`,
  }
  const btnOutline: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 8, borderRadius: 8,
    border: `1px solid ${LINE}`, background: 'transparent', color: TEXT, cursor: 'pointer',
    padding: '10px 16px', font: `500 13px ${SANS}`,
  }

  return (
    <div style={{ minHeight: '100vh', background: BG, color: TEXT, fontFamily: SANS }}>
      {/* top bar */}
      <div style={{ position: 'sticky', top: 0, zIndex: 30, background: 'rgba(10,14,15,0.85)', backdropFilter: 'blur(8px)', borderBottom: `1px solid ${LINE}` }}>
        <div style={{ maxWidth: 720, margin: '0 auto', padding: '0 20px', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none' }}>
            <div style={{ width: 10, height: 10, background: GOLD, transform: 'rotate(45deg)', boxShadow: `0 0 14px ${GOLD}` }} />
            <span style={{ font: `500 13px ${SANS}`, letterSpacing: '0.22em', color: GOLD }}>EMOUVA</span>
            <span style={{ font: `11px ${SANS}`, color: MUTED, marginLeft: 4 }}>· Community</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            {localUser && localUser.full_access !== false && <ModeToggle active="community" variant="gold" />}
            {poster ? (
              <span style={{ font: `12px ${MONO}`, color: MUTED }}>
                @{poster.username}
                {isRemoteCommunity && (
                  <span onClick={() => { communityLogout(); setRemoteUser(null) }} style={{ marginLeft: 8, cursor: 'pointer', textDecoration: 'underline' }}>sign out</span>
                )}
              </span>
            ) : !isRemoteCommunity ? (
              <Link to="/login" style={{ ...btnGold, padding: '7px 14px', textDecoration: 'none' }}>Sign in to post</Link>
            ) : null}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 720, margin: '0 auto', padding: '28px 20px 80px' }}>
        {/* intro */}
        <h1 style={{ font: `500 30px ${SERIF}`, margin: '0 0 6px', letterSpacing: '-0.01em' }}>
          A community of <span style={{ color: GOLD }}>AI traders</span>.
        </h1>
        <p style={{ color: MUTED, font: `15px ${SANS}`, margin: '0 0 24px', lineHeight: 1.55, maxWidth: 560 }}>
          Post your P&amp;L, swap tricks, and learn how others run their agents. One room, everyone welcome.
        </p>

        {/* composer */}
        {poster ? (
          <div style={{ background: CARD, border: `1px solid ${LINE}`, borderRadius: 12, padding: 14, marginBottom: 26 }}>
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                value={msg}
                onChange={(e) => setMsg(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send()}
                placeholder="Share a trick, an idea, or a question…"
                style={{ flex: 1, background: BG, border: `1px solid ${LINE}`, borderRadius: 8, padding: '10px 12px', color: TEXT, font: `14px ${SANS}`, outline: 'none' }}
              />
              <button onClick={send} disabled={!msg.trim()} style={{ ...btnGold, opacity: msg.trim() ? 1 : 0.5 }}>Send</button>
            </div>
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
              <button onClick={openShare} disabled={busy} style={btnOutline}>
                {busy ? 'Building…' : '◆ Share my P&L'}
              </button>
              <span style={{ font: `11px ${MONO}`, color: MUTED }}>a one-tap Wrapped card from your portfolio</span>
            </div>
          </div>
        ) : isRemoteCommunity ? (
          <CentralSignIn onDone={setRemoteUser} />
        ) : (
          <div style={{ background: CARD, border: `1px solid ${LINE}`, borderRadius: 12, padding: 18, marginBottom: 26, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
            <span style={{ color: MUTED, font: `14px ${SANS}` }}>Sign in to post your P&amp;L and join the conversation.</span>
            <Link to="/login" style={{ ...btnGold, textDecoration: 'none' }}>Post your P&L →</Link>
          </div>
        )}

        {/* feed */}
        {posts.length === 0 && (
          <p style={{ color: MUTED, font: `14px ${SANS}`, textAlign: 'center', padding: '40px 0' }}>
            No posts yet — be the first to share.
          </p>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {posts.map((p) => (
            <div key={p.id} style={{ background: CARD, border: `1px solid ${LINE}`, borderRadius: 12, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: p.kind === 'pnl_card' || p.body ? 12 : 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 26, height: 26, borderRadius: '50%', background: 'rgba(207,174,98,0.14)', display: 'flex', alignItems: 'center', justifyContent: 'center', font: `600 12px ${SERIF}`, color: GOLD }}>
                    {(p.author_name || '?').charAt(0).toUpperCase()}
                  </div>
                  <span style={{ font: `600 13px ${SANS}` }}>{p.author_name}</span>
                  <span style={{ font: `11px ${MONO}`, color: MUTED }}>· {ago(p.created_at)}</span>
                </div>
                {p.is_mine && (
                  <button onClick={() => remove(p.id)} title="Delete" style={{ background: 'transparent', border: 'none', color: MUTED, cursor: 'pointer', font: `14px ${SANS}` }}>×</button>
                )}
              </div>
              {p.body && <p style={{ margin: p.kind === 'pnl_card' ? '0 0 12px' : 0, font: `14px ${SANS}`, lineHeight: 1.55, color: 'rgba(238,244,242,0.9)' }}>{p.body}</p>}
              {p.kind === 'pnl_card' && p.stats && (
                <PnlCard stats={p.stats} author={p.author_name} handle={p.author_handle} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* share modal */}
      {sharing && shareStats != null && (
        <div
          onClick={() => setSharing(false)}
          style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
        >
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440, width: '100%', maxHeight: '92vh', overflowY: 'auto', background: '#0d1214', border: `1px solid ${LINE}`, borderRadius: 16, padding: 20 }}>
            <div style={{ font: `600 15px ${SANS}`, marginBottom: 4 }}>Share your P&L</div>
            <p style={{ font: `12px ${SANS}`, color: MUTED, margin: '0 0 16px' }}>
              {shareStats.source === 'disconnected'
                ? 'No agentic account found — connect Robinhood and let your agent trade to get real numbers.'
                : 'Built from your agentic account — where your AI trades. Add a note, then post it to the feed.'}
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
              <PnlCard ref={cardRef} stats={shareStats} author={poster?.display_name} handle={(poster as any)?.public_id || poster?.username} />
            </div>
            <input
              value={shareCaption}
              onChange={(e) => setShareCaption(e.target.value)}
              placeholder="Add a caption (optional)…"
              style={{ width: '100%', boxSizing: 'border-box', background: BG, border: `1px solid ${LINE}`, borderRadius: 8, padding: '10px 12px', color: TEXT, font: `14px ${SANS}`, outline: 'none', marginBottom: 14 }}
            />
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button onClick={postCard} disabled={busy} style={{ ...btnGold, opacity: busy ? 0.6 : 1 }}>{busy ? 'Posting…' : 'Post to feed'}</button>
              <button onClick={download} style={btnOutline}>Download PNG</button>
              <button onClick={() => setSharing(false)} style={{ ...btnOutline, marginLeft: 'auto' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/** Sign in to the central community (emouva.com account) from a self-hosted install. */
function CentralSignIn({ onDone }: { onDone: (u: CommunityUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const host = COMMUNITY_HOST.replace(/^https?:\/\//, '')
  const go = async () => {
    if (!username.trim() || !password) return
    setBusy(true); setErr('')
    try { onDone(await communityLogin(username.trim(), password)) }
    catch (e: any) { setErr(String(e?.message || 'Login failed').replace(/^\d+:\s*/, '')) }
    finally { setBusy(false) }
  }
  const inp: CSSProperties = {
    flex: '1 1 160px', background: BG, border: `1px solid ${LINE}`, borderRadius: 8,
    padding: '10px 12px', color: TEXT, font: `14px ${SANS}`, outline: 'none',
  }
  return (
    <div style={{ background: CARD, border: `1px solid ${LINE}`, borderRadius: 12, padding: 18, marginBottom: 26 }}>
      <div style={{ font: `600 14px ${SANS}`, marginBottom: 4 }}>Join the conversation</div>
      <p style={{ color: MUTED, font: `13px ${SANS}`, margin: '0 0 12px', lineHeight: 1.5 }}>
        The community lives on <span style={{ color: GOLD }}>{host}</span> — one shared room for every Emouva trader.
        Sign in with your {host} account to post; your trading stays on this machine.
      </p>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" autoCapitalize="none" style={inp} />
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="password"
          onKeyDown={(e) => e.key === 'Enter' && go()} style={inp} />
        <button onClick={go} disabled={busy || !username.trim() || !password}
          style={{ border: 'none', borderRadius: 8, background: GOLD, color: BG, fontWeight: 600, cursor: 'pointer', padding: '10px 18px', font: `600 13px ${SANS}`, opacity: busy ? 0.6 : 1 }}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </div>
      {err && <div style={{ color: '#f2937f', font: `12px ${SANS}`, marginTop: 8 }}>{err}</div>}
      <div style={{ color: MUTED, font: `12px ${SANS}`, marginTop: 10 }}>
        No account? <a href={`${COMMUNITY_HOST}/signup`} target="_blank" rel="noreferrer" style={{ color: GOLD }}>Create one on {host} ↗</a>
      </div>
    </div>
  )
}
