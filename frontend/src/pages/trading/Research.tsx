import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAgent } from '../../hooks/useAgentStore'
import { C, SERIF, MONO, SANS } from '../../data/agentMockData'
import { Dia } from '../../components/trading/primitives'

const microLabel = (color: string): React.CSSProperties => ({ font: `500 10px ${SANS}`, letterSpacing: '.13em', color, textTransform: 'uppercase' })
const cardBase: React.CSSProperties = { background: C.card, border: `1px solid ${C.border}`, borderRadius: 10 }

export default function Research() {
  const a = useAgent()
  const [src, setSrc] = useState('')
  const [trackSym, setTrackSym] = useState('')
  const mob = a.isMobile
  const s = a.latestScreen
  const researchPrinciples = a.allP.filter((p) => p.gold)

  const gridStyle: React.CSSProperties = mob
    ? { display: 'flex', flexDirection: 'column' }
    : { display: 'grid', gridTemplateColumns: '1fr 340px' }
  const mainStyle: React.CSSProperties = mob ? { padding: '18px 16px' } : { padding: 24, borderRight: `1px solid ${C.borderDim}` }
  const railStyle: React.CSSProperties = { ...(mob ? { padding: '18px 16px' } : { padding: '24px 20px' }), display: 'flex', flexDirection: 'column', gap: 16, background: C.raised }

  const runBtn = (
    <span onClick={() => { if (!a.screening) a.runScreen() }} style={{ display: 'inline-block', font: `500 12px ${SANS}`, color: C.bg, background: a.screening ? C.muted : C.gold, padding: '9px 18px', borderRadius: 6, cursor: a.screening ? 'default' : 'pointer' }}>{a.screening ? 'Running the screen…' : 'Run the morning screen'}</span>
  )

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto' }}>
      <div style={gridStyle}>
        {/* ── main: the real morning screen ── */}
        <div style={mainStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4, flexWrap: 'wrap' }}>
            <span style={{ font: `500 24px ${SERIF}`, color: C.textPrimary }}>Research</span>
            <span style={{ flex: 'none', font: `500 9px ${SANS}`, letterSpacing: '.09em', padding: '2px 7px', borderRadius: 4, color: C.bg, background: C.lightGold }}>SONNET 5</span>
          </div>
          <div style={{ font: `400 12px ${SANS}`, color: C.muted, marginBottom: 20 }}>The Partner screens your watchlist through the circle of competence, margin of safety, and inversion — and distills any paper you hand it into a principle.</div>

          {!s ? (
            <div style={{ ...cardBase, padding: '28px 20px', textAlign: 'center' }}>
              <div style={{ font: `400 13.5px/1.6 ${SERIF}`, color: C.secondary, marginBottom: 6 }}>No morning screen yet.</div>
              <div style={{ font: `400 12px ${SANS}`, color: C.muted, marginBottom: 18 }}>Run it to funnel your universe down to a single best idea — or nothing, if nothing clears.</div>
              {runBtn}
            </div>
          ) : (
            <>
              <div style={{ ...cardBase, padding: '16px 18px', marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ ...microLabel(C.faint) }}>Latest morning screen · {new Date(s.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</div>
                  <div style={{ font: `400 11px ${MONO}`, color: C.faint }}>{s.universe_count} in universe</div>
                </div>
                {/* funnel counts */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                  {(s.stages || []).map((st, i) => (
                    <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ font: `400 11.5px ${SANS}`, color: C.secondary }}><span style={{ font: `500 14px ${SERIF}`, color: C.body }}>{st.count}</span> {st.label}</span>
                      {i < (s.stages || []).length - 1 && <span style={{ color: C.disabled }}>→</span>}
                    </span>
                  ))}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Dia size={8} color={C.gold} style={{ transform: 'rotate(45deg)' }} />
                  <span style={{ font: `500 17px ${SERIF}`, color: C.textPrimary }}>{s.survivor ? `${s.survivor} — the survivor` : 'No survivor this run'}</span>
                </div>
              </div>

              <div style={{ ...cardBase, border: `1px solid ${C.goldBorderStrong}`, padding: '16px 18px', marginBottom: 12 }}>
                <div style={{ ...microLabel(C.gold), marginBottom: 8 }}>The verdict</div>
                <div style={{ font: `400 13px/1.6 ${SANS}`, color: C.body }}>{s.verdict}</div>
              </div>

              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <Link to={`/trading/screen/${s.id}`} style={{ font: `500 12px ${SANS}`, color: C.bg, background: C.gold, padding: '9px 18px', borderRadius: 6, textDecoration: 'none' }}>See the full funnel →</Link>
                {runBtn}
              </div>
            </>
          )}
        </div>

        {/* ── rail: distillation + research-sourced principles ── */}
        <div style={railStyle}>
          {/* dropzone — paste a link or text, distilled by Sonnet 5 */}
          <div style={{ border: `1.5px dashed ${C.goldBorderStrong}`, borderRadius: 10, padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <div style={{ width: 26, height: 26, border: `1px solid rgba(207,174,98,0.5)`, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Dia size={9} /></div>
              <div style={{ font: `500 12.5px ${SANS}`, color: C.textPrimary }}>Paste a paper link or text</div>
            </div>
            <textarea
              value={src} onChange={(e) => setSrc(e.target.value)} rows={3}
              placeholder="https://… or paste an abstract"
              style={{ width: '100%', resize: 'vertical', background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8, padding: '9px 11px', font: `400 12px ${SANS}`, color: C.textPrimary, outline: 'none', marginBottom: 10 }}
            />
            <span
              onClick={() => { if (!a.distilling) a.distill(src) }}
              style={{ display: 'inline-block', font: `500 12px ${SANS}`, color: C.bg, background: a.distilling ? C.muted : C.gold, padding: '8px 16px', borderRadius: 6, cursor: a.distilling ? 'default' : 'pointer' }}
            >{a.distilling ? 'Distilling…' : 'Distill it'}</span>
            <div style={{ font: `400 10.5px/1.5 ${SANS}`, color: C.faint, marginTop: 8 }}>I'll read it, distill it, invert it, and propose a principle before you adopt anything.</div>
          </div>

          {/* distilled result (real) */}
          {a.distilled && (
            <div style={{ ...cardBase, padding: 16, border: `1px solid ${C.goldBorder}` }}>
              <div style={{ ...microLabel(C.lightGold), marginBottom: 8 }}>Distilled · {a.distilled.section}</div>
              {a.distilled.title && <div style={{ font: `500 13.5px ${SERIF}`, color: C.textPrimary, marginBottom: 6 }}>{a.distilled.title}</div>}
              <div style={{ font: `400 12px/1.55 ${SANS}`, color: C.secondary, marginBottom: 8 }}>{a.distilled.gist}</div>
              {a.distilled.inversion && <div style={{ font: `400 11.5px/1.5 ${SANS}`, color: C.muted, marginBottom: 10 }}><span style={{ color: C.loss }}>Inverts:</span> {a.distilled.inversion}</div>}
              <div style={{ font: `italic 400 12.5px/1.5 ${SERIF}`, color: C.lightGold, marginBottom: 12 }}>"{a.distilled.principle}"</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <span onClick={a.adoptQmj} style={{ font: `500 12px ${SANS}`, color: C.bg, background: C.gold, padding: '8px 16px', borderRadius: 6, cursor: 'pointer' }}>Add to the Latticework</span>
                <span onClick={a.reviseQmj} style={{ font: `500 12px ${SANS}`, color: C.secondary, border: `1px solid ${C.goldBorder}`, padding: '8px 16px', borderRadius: 6, cursor: 'pointer' }}>Revise</span>
                <span onClick={a.discardQmj} style={{ font: `500 12px ${SANS}`, color: C.muted, padding: '8px 12px', cursor: 'pointer' }}>Discard</span>
              </div>
            </div>
          )}

          {/* track list — watch-only, ≤3 (real) */}
          <div style={{ ...cardBase, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={microLabel(C.faint)}>Watching · {a.tracks.length}/{a.trackMax}</div>
              {a.tracks.length > 0 && <span onClick={a.checkTrack} style={{ font: `400 10.5px ${SANS}`, color: C.gold, cursor: 'pointer' }}>re-value now</span>}
            </div>
            <div style={{ display: 'flex', gap: 6, marginBottom: a.tracks.length ? 12 : 0 }}>
              <input
                value={trackSym} onChange={(e) => setTrackSym(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && a.tracks.length < a.trackMax) { a.addTrack(trackSym); setTrackSym('') } }}
                placeholder="Add a ticker to watch" maxLength={8}
                style={{ flex: 1, background: C.bg, border: `1px solid ${C.border}`, borderRadius: 7, padding: '7px 10px', font: `500 12px ${MONO}`, color: C.textPrimary, textTransform: 'uppercase', outline: 'none' }}
              />
              <span
                onClick={() => { if (a.tracks.length < a.trackMax && trackSym.trim()) { a.addTrack(trackSym); setTrackSym('') } }}
                style={{ font: `500 12px ${SANS}`, color: C.bg, background: a.tracks.length >= a.trackMax ? C.muted : C.gold, padding: '7px 14px', borderRadius: 7, cursor: a.tracks.length >= a.trackMax ? 'default' : 'pointer', whiteSpace: 'nowrap' }}
              >Watch</span>
            </div>
            {a.tracks.map((t) => {
              const st = t.status === 'proposed' ? C.gain : t.status === 'interesting' ? C.gold : C.muted
              const margin = t.last_margin_pct
              return (
                <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: `1px solid ${C.borderRow}` }}>
                  <span style={{ font: `500 12.5px ${MONO}`, color: C.textPrimary, width: 52 }}>{t.symbol}</span>
                  <span style={{ font: `400 10.5px ${MONO}`, color: margin == null ? C.faint : margin >= 0 ? C.gain : C.loss, width: 56 }}>
                    {margin == null ? '—' : `${margin >= 0 ? '+' : '−'}${Math.abs(margin).toFixed(0)}%`}
                  </span>
                  <span style={{ flex: 1, font: `500 9px ${SANS}`, letterSpacing: '.08em', textTransform: 'uppercase', color: st }}>{t.status}</span>
                  <span onClick={() => a.removeTrack(t.symbol)} style={{ font: `400 14px ${SANS}`, color: C.faint, cursor: 'pointer', lineHeight: 1 }}>×</span>
                </div>
              )
            })}
            <div style={{ font: `400 10px/1.5 ${SANS}`, color: C.faint, marginTop: 10 }}>Watch-only. Checked daily on the math; when one reaches your margin of safety, the Partner deep-dives it and brings it to you for approval.</div>
          </div>

          {/* research-sourced principles (real) */}
          <div style={{ ...cardBase, padding: 16 }}>
            <div style={{ ...microLabel(C.faint), marginBottom: 12 }}>Adopted from research</div>
            {researchPrinciples.length === 0 ? (
              <div style={{ font: `400 11.5px/1.5 ${SANS}`, color: C.muted }}>Nothing distilled into the Latticework yet. Hand the Partner a paper above.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                {researchPrinciples.map((p) => (
                  <div key={p.id} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span style={{ font: `italic 400 12.5px/1.45 ${SERIF}`, color: C.body }}>"{p.text}"</span>
                    <span style={{ font: `400 10px ${MONO}`, color: C.faint }}>{p.sec}</span>
                  </div>
                ))}
                <Link to="/trading/principles" style={{ font: `400 11px ${SANS}`, color: C.gold, textDecoration: 'none', marginTop: 2 }}>View in Principles →</Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
