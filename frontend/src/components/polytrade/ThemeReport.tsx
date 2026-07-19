import { ResponsiveContainer, AreaChart, Area, YAxis, Tooltip, PieChart, Pie, Cell } from 'recharts'
import ReactMarkdown from 'react-markdown'
import { C, SANS, SERIF, MONO } from './parts'
import type { ThemeReport as Report, ReportConstituent } from '../../api/themes'

const ROLE_COLOR: Record<string, string> = { anchor: '#E9D6A2', satellite: '#7FE3A9', speculative: '#DFB65A' }
const pctFrac = (v: number | null) => (v == null ? '—' : `${(v * 100).toFixed(0)}%`)
const pctNum = (v: number | null) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`)
const num1 = (v: number | null) => (v == null ? '—' : v.toFixed(1))
const gl = (v: number | null | undefined) => (v == null ? C.muted : v >= 0 ? C.gain : C.loss)

// ── section label ─────────────────────────────────────────────────────────
const SLabel = ({ children }: { children: React.ReactNode }) => (
  <div style={{ font: `500 11px ${MONO}`, letterSpacing: '.12em', textTransform: 'uppercase', color: C.gold, marginBottom: 10 }}>{children}</div>
)

// react-markdown → themed elements
const MD = ({ children }: { children: string }) => (
  <ReactMarkdown
    components={{
      p: (p) => <p style={{ font: `400 13.5px ${SANS}`, color: C.body, lineHeight: 1.62, margin: '0 0 12px' }}>{p.children}</p>,
      strong: (p) => <strong style={{ color: C.textPrimary, fontWeight: 600 }}>{p.children}</strong>,
      em: (p) => <em style={{ color: C.lightGold }}>{p.children}</em>,
      ul: (p) => <ul style={{ margin: '0 0 12px', paddingLeft: 18 }}>{p.children}</ul>,
      ol: (p) => <ol style={{ margin: '0 0 12px', paddingLeft: 18 }}>{p.children}</ol>,
      li: (p) => <li style={{ font: `400 13.5px ${SANS}`, color: C.body, lineHeight: 1.55, marginBottom: 4 }}>{p.children}</li>,
      h3: (p) => <div style={{ font: `600 14px ${SANS}`, color: C.textPrimary, margin: '4px 0 8px' }}>{p.children}</div>,
      h4: (p) => <div style={{ font: `600 13px ${SANS}`, color: C.lightGold, margin: '4px 0 6px' }}>{p.children}</div>,
      a: (p) => <a href={p.href} target="_blank" rel="noreferrer" style={{ color: C.lightGold, textDecoration: 'underline' }}>{p.children}</a>,
    }}
  >{children}</ReactMarkdown>
)

function PerfChart({ values }: { values: number[] }) {
  const data = values.map((v, i) => ({ i, v }))
  const chg = values.length ? values[values.length - 1] - 100 : 0
  const col = chg >= 0 ? C.gain : C.loss
  const lo = Math.min(...values), hi = Math.max(...values)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <SLabel>Basket performance · ~{Math.round(values.length / 21)}mo</SLabel>
        <span style={{ font: `600 13px ${MONO}`, color: col }}>{chg >= 0 ? '+' : ''}{chg.toFixed(1)}%</span>
      </div>
      <div style={{ height: 150 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 2, left: 2, bottom: 0 }}>
            <defs>
              <linearGradient id="ptperf" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={col} stopOpacity={0.32} />
                <stop offset="100%" stopColor={col} stopOpacity={0} />
              </linearGradient>
            </defs>
            <YAxis domain={[lo * 0.99, hi * 1.01]} hide />
            <Tooltip
              contentStyle={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, font: `400 11px ${MONO}` }}
              labelFormatter={() => ''} formatter={(v: any) => [`${(v as number).toFixed(1)}`, 'index']} />
            <Area type="monotone" dataKey="v" stroke={col} strokeWidth={2} fill="url(#ptperf)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{ font: `400 10px ${MONO}`, color: C.faint, marginTop: 2 }}>Indexed to 100 at window start · weighted by target %</div>
    </div>
  )
}

function AllocDonut({ allocation }: { allocation: { symbol: string; weight: number; role: string }[] }) {
  const data = allocation.map(a => ({ name: a.symbol, value: +(a.weight * 100).toFixed(1), role: a.role }))
  return (
    <div>
      <SLabel>Allocation</SLabel>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ width: 128, height: 150, flex: 'none' }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={38} outerRadius={62} paddingAngle={2} stroke="none">
                {data.map((d, i) => <Cell key={i} fill={ROLE_COLOR[d.role] || C.gold} />)}
              </Pie>
              <Tooltip contentStyle={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, font: `400 11px ${MONO}` }}
                formatter={(v: any, n: any) => [`${v}%`, n]} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {data.map(d => (
            <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 7, font: `400 11.5px ${MONO}` }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: ROLE_COLOR[d.role] || C.gold, flex: 'none' }} />
              <span style={{ color: C.body, width: 48 }}>{d.name}</span>
              <span style={{ color: C.faint }}>{d.value}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Scorecard({ rows }: { rows: ReportConstituent[] }) {
  const H = ({ children, w }: { children: React.ReactNode; w?: number }) =>
    <th style={{ font: `500 9.5px ${MONO}`, letterSpacing: '.06em', textTransform: 'uppercase', color: C.faint, textAlign: 'right', padding: '0 0 6px', width: w }}>{children}</th>
  const Td = ({ children, color = C.body, left = false }: { children: React.ReactNode; color?: string; left?: boolean }) =>
    <td style={{ font: `500 12px ${MONO}`, color, textAlign: left ? 'left' : 'right', padding: '7px 0', fontVariantNumeric: 'tabular-nums' }}>{children}</td>
  return (
    <div>
      <SLabel>Constituent scorecard</SLabel>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr style={{ borderBottom: `1px solid ${C.borderRow}` }}>
          <H w={90}><span style={{ float: 'left' }}>Name</span></H><H>Wt</H><H>Marg. safety</H><H>Rev gr.</H><H>ROE</H><H>Op mgn</H><H>Fwd P/E</H><H>Trend</H>
        </tr></thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.symbol} style={{ borderBottom: `1px solid ${C.borderRow}` }}>
              <Td left><span style={{ color: C.textPrimary }}>{r.symbol}</span> <span style={{ color: ROLE_COLOR[r.role] || C.muted, fontSize: 9 }}>{r.role[0].toUpperCase()}</span></Td>
              <Td>{(r.weight * 100).toFixed(1)}%</Td>
              <Td color={gl(r.margin_of_safety_pct)}>{pctNum(r.margin_of_safety_pct)}</Td>
              <Td color={gl(r.rev_growth)}>{pctFrac(r.rev_growth)}</Td>
              <Td>{pctFrac(r.roe)}</Td>
              <Td>{pctFrac(r.op_margin)}</Td>
              <Td>{num1(r.forward_pe)}</Td>
              <Td color={r.trend === 'rising' ? C.gain : r.trend === 'falling' ? C.loss : C.muted}>{r.trend || '—'}</Td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ font: `400 10px ${MONO}`, color: C.faint, marginTop: 6 }}>Margin of safety vs our conservative fair value · fundamentals from our data</div>
    </div>
  )
}

export default function ThemeReport({ report }: { report: Report }) {
  const hist = report.charts?.basket_history
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {report.summary && (
        <p style={{ font: `400 15px ${SERIF}`, color: C.body, lineHeight: 1.62, margin: 0 }}>{report.summary}</p>
      )}

      {report.key_takeaways?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '14px 16px', borderRadius: 12, background: 'rgba(207,174,98,0.05)', border: `1px solid ${C.goldBorder}` }}>
          <SLabel>Key takeaways</SLabel>
          {report.key_takeaways.map((t, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
              <span style={{ width: 5, height: 5, transform: 'rotate(45deg)', background: C.gold, marginTop: 5, flex: 'none' }} />
              <span style={{ font: `400 13.5px ${SANS}`, color: C.body, lineHeight: 1.5 }}>{t}</span>
            </div>
          ))}
        </div>
      )}

      {/* charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 20 }}>
        {hist?.values?.length ? <PerfChart values={hist.values} /> : <div />}
        {report.charts?.allocation?.length ? <AllocDonut allocation={report.charts.allocation} /> : <div />}
      </div>

      {report.charts?.constituents?.length ? <Scorecard rows={report.charts.constituents} /> : null}

      {/* sections */}
      {report.sections?.map((s, i) => (
        <div key={i}>
          <div style={{ font: `500 17px ${SERIF}`, color: C.textPrimary, marginBottom: 8, paddingBottom: 6, borderBottom: `1px solid ${C.borderRow}` }}>{s.heading}</div>
          <MD>{s.body}</MD>
        </div>
      ))}

      <div style={{ font: `400 10px ${MONO}`, color: C.faint }}>
        AI-generated research · {report.generated_at ? new Date(report.generated_at).toLocaleDateString() : ''} · informational only, not personalized advice
      </div>
    </div>
  )
}
