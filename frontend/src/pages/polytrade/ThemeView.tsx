import { useEffect, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getTheme, allocateToTheme, unwindAllocation, followTheme, listComments, postComment, likeComment, deleteComment, themeAccount, type Theme, type Comment } from '../../api/themes'
import { C, SANS, SERIF, MONO, Gauge, HealthPill, StatusChip, Tag, Card, money, money2, pct, pctColor, roleColor, EVENT_UI } from '../../components/polytrade/parts'
import ThemeReport from '../../components/polytrade/ThemeReport'

export default function ThemeView() {
  const { slug = '' } = useParams()
  const nav = useNavigate()
  const [t, setT] = useState<Theme | null>(null)
  const [err, setErr] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [following, setFollowing] = useState(false)
  const [followers, setFollowers] = useState(0)
  const [shared, setShared] = useState(false)
  const [showReport, setShowReport] = useState(true)

  const load = useCallback(() => getTheme(slug).then(tt => {
    setT(tt); setFollowing(!!tt.i_follow); setFollowers(tt.n_followers || 0)
  }).catch(e => setErr(String(e.message || 'Not found'))), [slug])
  useEffect(() => { load() }, [load])

  const toggleFollow = async () => {
    if (!t) return
    try { const r = await followTheme(t.id); setFollowing(r.following); setFollowers(r.n_followers) } catch { /* ignore */ }
  }
  const share = async () => {
    const url = `${window.location.origin}/polytrade/${slug}`
    try { await navigator.clipboard.writeText(url) } catch { /* ignore */ }
    setShared(true); setTimeout(() => setShared(false), 1800)
  }

  if (err) return <div style={{ font: `400 14px ${SANS}`, color: C.loss }}>{err} · <Link to="/polytrade" style={{ color: C.gold }}>back</Link></div>
  if (!t) return <div style={{ font: `400 13px ${SANS}`, color: C.muted }}>Loading…</div>

  const since = t.perf_snapshot?.since_inception_pct
  const day = t.perf_snapshot?.day_pct
  const mine = t.my_allocation
  const convText = t.conviction >= 70 ? 'High conviction' : t.conviction >= 55 ? 'Strong conviction' : t.conviction >= 40 ? 'Constructive' : 'Early / cautious'
  const convCol = t.conviction >= 55 ? C.gain : t.conviction >= 40 ? C.warning : C.loss

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 340px', gap: 22, alignItems: 'start' }}>
      {/* ── LEFT: thesis + basket + activity ── */}
      <div>
        <Link to="/polytrade" style={{ font: `400 12px ${SANS}`, color: C.muted, textDecoration: 'none' }}>← All themes</Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', margin: '12px 0 8px' }}>
          {(t.tags || []).map(x => <Tag key={x}>{x}</Tag>)}
          <StatusChip s={t.status} /><HealthPill h={t.health} />
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button onClick={toggleFollow} style={{ font: `500 12px ${SANS}`, color: following ? '#0C110E' : C.lightGold, background: following ? C.gold : 'transparent', border: `1px solid ${C.goldBorder}`, borderRadius: 999, padding: '5px 12px', cursor: 'pointer' }}>
              {following ? '✓ Following' : '+ Follow'}{followers ? ` · ${followers}` : ''}
            </button>
            <button onClick={share} style={{ font: `500 12px ${SANS}`, color: C.secondary, background: 'transparent', border: `1px solid ${C.borderDim}`, borderRadius: 999, padding: '5px 12px', cursor: 'pointer' }}>
              {shared ? 'Copied!' : 'Share'}
            </button>
          </div>
        </div>
        <h1 style={{ font: `500 30px ${SERIF}`, letterSpacing: '-.01em', margin: '0 0 8px', color: C.textPrimary }}>{t.title}</h1>
        {t.hero_stat && <div style={{ font: `italic 400 16px ${SERIF}`, color: C.lightGold, marginBottom: 16 }}>“{t.hero_stat}”</div>}

        <div style={{ display: 'flex', gap: 28, marginBottom: 20 }}>
          <div style={{ minWidth: 240 }}>
            <Label>Our conviction</Label>
            <Gauge v={t.conviction} />
            <div style={{ font: `500 11px ${MONO}`, color: convCol, marginTop: 5 }}>{convText} · {t.conviction}/100</div>
          </div>
          <Metric label="Since basket" value={pct(since)} color={pctColor(since)} />
          <Metric label="Today" value={pct(day)} color={pctColor(day)} />
          <Metric label="Investors" value={`${t.n_investors || 0}`} color={C.body} sub={money(t.total_committed)} />
        </div>

        <SectionTitle>Why we own this</SectionTitle>
        <p style={{ font: `400 14.5px ${SANS}`, color: C.body, lineHeight: 1.62, marginBottom: 14 }}>{t.narrative}</p>

        {/* full analyst research report — open by default, collapsible */}
        {t.report && (t.report.sections?.length || t.report.summary) ? (
          <div style={{ marginBottom: 22 }}>
            <button onClick={() => setShowReport(s => !s)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, background: 'transparent', border: `1px solid ${C.goldBorder}`, borderRadius: 8, padding: '9px 13px', cursor: 'pointer', font: `600 12.5px ${SANS}`, color: C.lightGold, marginBottom: showReport ? 18 : 0 }}>
              <span>📄</span>Research report
              <span style={{ color: C.faint, fontWeight: 400 }}>· {t.report.sections?.length || 0} sections + charts</span>
              <span style={{ marginLeft: 'auto', color: C.muted, font: `500 11px ${MONO}` }}>{showReport ? '▲ Hide' : '▼ Show'}</span>
            </button>
            {showReport && (
              <Card style={{ padding: 22 }}>
                <ThemeReport report={t.report} />
              </Card>
            )}
          </div>
        ) : t.report_status === 'generating' ? (
          <div style={{ font: `400 13px ${SANS}`, color: C.muted, marginBottom: 22 }}>✎ Our analyst is writing the full research report…</div>
        ) : null}

        {/* basket */}
        <SectionTitle>The basket · {(t.constituents || []).length} names</SectionTitle>
        <Card style={{ padding: 0, marginBottom: 22 }}>
          {(t.constituents || []).map((c, i) => (
            <div key={c.symbol} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 16px', borderBottom: i < (t.constituents!.length - 1) ? `1px solid ${C.borderRow}` : 'none' }}>
              <span style={{ font: `500 13px ${MONO}`, color: C.textPrimary, width: 52 }}>{c.symbol}</span>
              <span style={{ font: `500 9.5px ${MONO}`, letterSpacing: '.08em', textTransform: 'uppercase', color: roleColor(c.role), width: 66 }}>{c.role}</span>
              <div style={{ width: 120, height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${c.target_weight * 100}%`, background: C.gold, borderRadius: 999 }} />
              </div>
              <span style={{ font: `500 12px ${MONO}`, color: C.body, width: 46, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{(c.target_weight * 100).toFixed(1)}%</span>
              <span style={{ font: `400 12px ${SANS}`, color: C.muted, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.rationale}</span>
            </div>
          ))}
          {!(t.constituents || []).length && <div style={{ padding: 16, font: `400 13px ${SANS}`, color: C.muted }}>Basket is being assembled.</div>}
        </Card>

        {/* how we manage the risk — framed around our active exit discipline */}
        {(t.falsifiers || []).length > 0 && (
          <>
            <SectionTitle>How we protect you · what we watch</SectionTitle>
            <Card style={{ marginBottom: 22 }}>
              {t.risk && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '10px 12px', marginBottom: 12, borderRadius: 10, background: 'rgba(127,227,169,0.06)', border: `1px solid ${C.greenBorder}` }}>
                  <div>
                    <div style={{ font: `500 10px ${MONO}`, letterSpacing: '.1em', textTransform: 'uppercase', color: C.faint, marginBottom: 2 }}>Est. downside if we exit</div>
                    <div style={{ font: `600 22px ${MONO}`, color: C.gain, fontVariantNumeric: 'tabular-nums' }}>~{t.risk.managed_downside_pct}%</div>
                  </div>
                  <div style={{ font: `400 12px ${SANS}`, color: C.secondary, lineHeight: 1.5, flex: 1 }}>
                    Because we act on weakness <b style={{ color: C.lightGold }}>early</b>, a broken thesis typically costs
                    around this — well short of the <span style={{ color: C.muted }}>~{t.risk.unmanaged_ref_pct}%</span> a
                    left-alone basket could give back. An estimate from the basket's own volatility, not a guarantee.
                  </div>
                </div>
              )}
              <p style={{ font: `400 13px ${SANS}`, color: C.secondary, lineHeight: 1.55, margin: '0 0 12px' }}>
                We track these signals <span style={{ color: C.lightGold }}>every day</span> and act on weakness
                <span style={{ color: C.lightGold }}> early</span> — trimming or exiting well before a thesis fully
                breaks, so your downside stays contained rather than riding a name all the way down.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {t.falsifiers.map((f, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                    <div style={{ width: 5, height: 5, transform: 'rotate(45deg)', background: C.warning, marginTop: 5, flex: 'none' }} />
                    <div>
                      <span style={{ font: `500 13px ${SANS}`, color: C.body }}>{f.label}</span>
                      <span style={{ font: `400 12px ${SANS}`, color: C.faint }}> — {f.breaks_if}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}

        <SectionTitle>Discussion{t.n_comments ? ` · ${t.n_comments}` : ''}</SectionTitle>
        <Comments themeId={t.id} onChange={load} />
      </div>

      {/* ── RIGHT: my stake + add capital + activity feed ── */}
      <div style={{ position: 'sticky', top: 74, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {mine ? (
          <Card style={{ borderColor: C.goldBorderStrong, background: C.emphasis }}>
            <Label>Your position</Label>
            <div style={{ font: `500 26px ${MONO}`, color: C.textPrimary, margin: '4px 0', fontVariantNumeric: 'tabular-nums' }}>{money2(mine.market_value)}</div>
            <div style={{ font: `500 13px ${MONO}`, color: pctColor(mine.total_pnl) }}>
              {mine.total_pnl != null && mine.total_pnl >= 0 ? '▲' : '▼'} {money2(Math.abs(mine.total_pnl || 0))} ({pct(mine.total_pnl_pct)})
            </div>
            <div style={{ font: `400 11px ${MONO}`, color: C.faint, marginTop: 6 }}>Committed {money2(mine.committed_usd)} · {mine.status}</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
              <button onClick={() => setShowAdd(true)} disabled={t.status !== 'live' && t.status !== 'weakening'} style={btnPrimary}>Add more</button>
              <ExitButton allocId={mine.id} onDone={load} />
            </div>
          </Card>
        ) : (
          <Card style={{ borderColor: C.goldBorder }}>
            <Label>Add capital to this theme</Label>
            <p style={{ font: `400 12.5px ${SANS}`, color: C.muted, lineHeight: 1.5, margin: '6px 0 14px' }}>
              We buy the basket at target weights on your connected Robinhood account and manage it for you. Real-money funding is rolling out — you'll fund it here once it's live.
            </p>
            <button onClick={() => setShowAdd(true)} disabled={t.status === 'breaking'} style={{ ...btnPrimary, width: '100%', padding: '11px 0', fontSize: 14 }}>
              {t.status === 'breaking' ? 'Closing — not open' : 'Fund this theme'}
            </button>
          </Card>
        )}

        <Card style={{ padding: 0 }}>
          <div style={{ padding: '13px 16px', borderBottom: `1px solid ${C.borderRow}` }}>
            <Label>Live activity · what the AI is doing</Label>
          </div>
          <div style={{ maxHeight: 420, overflowY: 'auto' }}>
            {(t.events || []).map((e, i) => {
              const u = EVENT_UI[e.kind] || { c: C.muted, label: e.kind }
              return (
                <div key={i} style={{ display: 'flex', gap: 10, padding: '11px 16px', borderBottom: i < (t.events!.length - 1) ? `1px solid ${C.borderRow}` : 'none' }}>
                  <div style={{ width: 5, height: 5, borderRadius: '50%', background: u.c, marginTop: 6, flex: 'none' }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ font: `500 9.5px ${MONO}`, letterSpacing: '.08em', textTransform: 'uppercase', color: u.c }}>{u.label}</div>
                    <div style={{ font: `400 12.5px ${SANS}`, color: C.secondary, lineHeight: 1.45 }}>{e.summary}</div>
                    <div style={{ font: `400 10px ${MONO}`, color: C.faint, marginTop: 2 }}>{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</div>
                  </div>
                </div>
              )
            })}
            {!(t.events || []).length && <div style={{ padding: 16, font: `400 12px ${SANS}`, color: C.muted }}>No activity yet.</div>}
          </div>
        </Card>
      </div>

      {showAdd && <AddCapital theme={t} onClose={() => setShowAdd(false)} onDone={() => { setShowAdd(false); load() }} />}
    </div>
  )
}

function ExitButton({ allocId, onDone }: { allocId: string; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const go = async () => {
    if (!confirm('Exit this theme? We sell the basket and return the cash to your account.')) return
    setBusy(true)
    try { await unwindAllocation(allocId); onDone() } catch (e: any) { alert(String(e.message || 'Failed')); setBusy(false) }
  }
  return <button onClick={go} disabled={busy} style={btnGhost}>{busy ? 'Exiting…' : 'Exit'}</button>
}

function AddCapital({ theme, onClose, onDone }: { theme: Theme; onClose: () => void; onDone: () => void }) {
  const [acct, setAcct] = useState<{ connected: boolean; live: boolean; available: number } | null>(null)
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  useEffect(() => { themeAccount().then(setAcct).catch(() => setAcct({ connected: false, live: false, available: 0 })) }, [])
  const avail = acct?.available ?? null
  const amt = parseFloat(amount)
  const canFund = !!acct?.connected && !!acct?.live
  const valid = canFund && amt > 0 && (avail == null || amt <= avail)
  const submit = async () => {
    if (!valid) return
    setBusy(true); setErr('')
    try { await allocateToTheme(theme.id, amt); onDone() }
    catch (e: any) { setErr(String(e.message || 'Failed').replace(/^\d+:\s*/, '')); setBusy(false) }
  }
  const quick = [100, 500, 1000, 5000]
  return createPortal(
    <div onClick={onClose} style={overlay}>
      <div onClick={e => e.stopPropagation()} style={modal}>
        <div style={{ font: `500 18px ${SERIF}`, color: C.textPrimary, marginBottom: 3 }}>Fund “{theme.title}”</div>
        <div style={{ font: `400 12.5px ${SANS}`, color: C.muted, marginBottom: 4 }}>
          {acct?.connected
            ? <>Available buying power: <span style={{ color: C.body, fontFamily: MONO }}>{avail == null ? '…' : money2(avail)}</span></>
            : 'Connect your Robinhood account to invest.'}
        </div>
        <div style={{ font: `400 11px ${SANS}`, color: acct?.live ? C.faint : C.warning, marginBottom: 12, lineHeight: 1.45 }}>
          {acct?.live
            ? 'Real money — invested on your connected Robinhood account and managed for you. Total loss is possible.'
            : 'Preview — real-money theme investing is not live yet. Browse the basket and thesis; funding opens here once it is enabled.'}
        </div>
        <div style={{ position: 'relative', marginBottom: 12 }}>
          <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', font: `500 18px ${MONO}`, color: C.muted }}>$</span>
          <input value={amount} onChange={e => setAmount(e.target.value.replace(/[^0-9.]/g, ''))} inputMode="decimal" autoFocus placeholder="0"
            style={{ width: '100%', boxSizing: 'border-box', background: C.raised, border: `1px solid ${C.border}`, borderRadius: 10, padding: '12px 14px 12px 30px', font: `500 20px ${MONO}`, color: C.textPrimary, outline: 'none' }} />
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {quick.map(q => (
            <button key={q} onClick={() => setAmount(String(q))} style={{ flex: 1, background: C.raised, border: `1px solid ${C.border}`, borderRadius: 8, padding: '7px 0', font: `500 12px ${MONO}`, color: C.secondary, cursor: 'pointer' }}>${q >= 1000 ? `${q / 1000}k` : q}</button>
          ))}
        </div>
        {err && <div style={{ font: `400 12px ${SANS}`, color: C.loss, marginBottom: 12 }}>{err}</div>}
        <button onClick={submit} disabled={!valid || busy} style={{ ...btnPrimary, width: '100%', padding: '12px 0', fontSize: 14, opacity: (!valid || busy) ? 0.45 : 1 }}>
          {busy ? 'Placing orders…' : `Invest ${amt > 0 ? money2(amt) : ''}`}
        </button>
        <button onClick={onClose} style={{ width: '100%', background: 'none', border: 'none', font: `400 12px ${SANS}`, color: C.muted, marginTop: 10, cursor: 'pointer' }}>Cancel</button>
      </div>
    </div>,
    document.body,
  )
}

function Comments({ themeId, onChange }: { themeId: string; onChange: () => void }) {
  const [items, setItems] = useState<Comment[] | null>(null)
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const reload = useCallback(() => listComments(themeId).then(setItems).catch(() => setItems([])), [themeId])
  useEffect(() => { reload() }, [reload])

  const send = async () => {
    const text = body.trim()
    if (!text) return
    setBusy(true)
    try { await postComment(themeId, text); setBody(''); await reload(); onChange() }
    catch (e: any) { alert(String(e.message || 'Failed')) } finally { setBusy(false) }
  }
  const like = async (c: Comment) => {
    try { const r = await likeComment(c.id); setItems(prev => (prev || []).map(x => x.id === c.id ? { ...x, i_liked: r.liked, likes: r.likes } : x)) } catch { /* ignore */ }
  }
  const remove = async (c: Comment) => {
    if (!confirm('Delete your comment?')) return
    try { await deleteComment(c.id); await reload(); onChange() } catch { /* ignore */ }
  }

  return (
    <Card style={{ marginBottom: 22 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        <input value={body} onChange={e => setBody(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} maxLength={1000}
          placeholder="Add to the discussion…" style={{ flex: 1, background: C.raised, border: `1px solid ${C.border}`, borderRadius: 8, padding: '9px 12px', font: `400 13px ${SANS}`, color: C.textPrimary, outline: 'none' }} />
        <button onClick={send} disabled={busy || !body.trim()} style={{ background: C.gold, color: '#0C110E', border: 'none', borderRadius: 8, padding: '0 16px', font: `600 12.5px ${SANS}`, cursor: 'pointer', opacity: (busy || !body.trim()) ? 0.4 : 1 }}>Post</button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {(items || []).map(c => (
          <div key={c.id} style={{ display: 'flex', gap: 10 }}>
            <div style={{ width: 26, height: 26, borderRadius: '50%', background: C.raised, border: `1px solid ${C.borderDim}`, display: 'flex', alignItems: 'center', justifyContent: 'center', font: `600 11px ${SERIF}`, color: C.lightGold, flex: 'none' }}>{(c.author || '?').slice(0, 1).toUpperCase()}</div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ font: `600 12.5px ${SANS}`, color: C.body }}>{c.author}</span>
                <span style={{ font: `400 10px ${MONO}`, color: C.faint }}>{c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}</span>
                {c.mine && <span onClick={() => remove(c)} style={{ font: `400 10px ${SANS}`, color: C.faint, cursor: 'pointer', marginLeft: 'auto' }}>delete</span>}
              </div>
              <div style={{ font: `400 13px ${SANS}`, color: C.secondary, lineHeight: 1.45, margin: '2px 0 4px' }}>{c.body}</div>
              <button onClick={() => like(c)} style={{ background: 'none', border: 'none', cursor: 'pointer', font: `500 11px ${SANS}`, color: c.i_liked ? C.gold : C.faint, padding: 0 }}>
                ♥ {c.likes || 0}
              </button>
            </div>
          </div>
        ))}
        {items && !items.length && <div style={{ font: `400 12.5px ${SANS}`, color: C.muted }}>No comments yet — start the conversation.</div>}
      </div>
    </Card>
  )
}

const Label = ({ children }: { children: React.ReactNode }) =>
  <div style={{ font: `500 10px ${MONO}`, letterSpacing: '.1em', textTransform: 'uppercase', color: C.faint, marginBottom: 6 }}>{children}</div>
const SectionTitle = ({ children }: { children: React.ReactNode }) =>
  <div style={{ font: `500 11px ${MONO}`, letterSpacing: '.1em', textTransform: 'uppercase', color: C.muted, marginBottom: 10 }}>{children}</div>
function Metric({ label, value, color, sub }: { label: string; value: string; color: string; sub?: string }) {
  return (
    <div>
      <div style={{ font: `400 9.5px ${MONO}`, letterSpacing: '.08em', textTransform: 'uppercase', color: C.faint, marginBottom: 3 }}>{label}</div>
      <div style={{ font: `500 17px ${MONO}`, color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {sub && <div style={{ font: `400 10px ${MONO}`, color: C.faint, marginTop: 1 }}>{sub}</div>}
    </div>
  )
}
const btnPrimary: React.CSSProperties = { background: C.gold, color: '#0C110E', border: 'none', borderRadius: 8, padding: '8px 14px', font: `600 12.5px ${SANS}`, cursor: 'pointer' }
const btnGhost: React.CSSProperties = { background: 'transparent', color: C.loss, border: `1px solid ${C.redBorder}`, borderRadius: 8, padding: '8px 14px', font: `500 12.5px ${SANS}`, cursor: 'pointer' }
const overlay: React.CSSProperties = { position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(6,9,7,0.72)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }
const modal: React.CSSProperties = { width: '100%', maxWidth: 380, background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 22 }
