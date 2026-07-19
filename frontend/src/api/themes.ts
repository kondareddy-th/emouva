import { apiFetch } from './client'

// ── Polytrade types (mirror the backend theme_dict / allocation_dict) ──
export interface ThemeFalsifier { label: string; breaks_if: string; kind: string }
export interface ThemeRedTeam { lens: string; attack: string; verdict: string }
export interface ThemeConstituent {
  symbol: string; target_weight: number; role: string
  conviction: number | null; rationale: string | null; status: string
}
export interface ThemeEvent { kind: string; summary: string; detail: any; created_at: string | null }
export interface ThemePerf {
  since_inception_pct: number | null; day_pct: number | null; per_name?: any[]; updated_at?: string
}
export interface Theme {
  id: string; slug: string; title: string; tags: string[]; narrative: string; hero_stat: string | null
  status: string; conviction: number; health: string
  falsifiers: ThemeFalsifier[]; red_team: ThemeRedTeam[]
  perf_snapshot: ThemePerf | null
  risk?: { managed_downside_pct: number; unmanaged_ref_pct: number; monthly_vol_pct: number; n_names: number; basis: string } | null
  report_status?: string | null
  report?: ThemeReport | null
  n_investors?: number; total_committed?: number; n_constituents?: number
  n_followers?: number; i_follow?: boolean; n_comments?: number
  constituents?: ThemeConstituent[]; events?: ThemeEvent[]
  my_allocation?: Allocation
}
export interface Comment {
  id: string; body: string; author: string; mine: boolean
  created_at: string | null; likes: number; i_liked: boolean
}
export interface ReportConstituent {
  symbol: string; role: string; weight: number; rationale: string | null
  price: number | null; margin_of_safety_pct: number | null; trend: string | null
  rev_growth: number | null; roe: number | null; op_margin: number | null; forward_pe: number | null; pe: number | null
}
export interface ThemeReport {
  generated_at: string; summary: string; key_takeaways: string[]
  sections: { heading: string; body: string }[]
  charts: {
    basket_history: { values: number[]; points: number } | null
    allocation: { symbol: string; weight: number; role: string }[]
    constituents: ReportConstituent[]
  }
}
export interface Holding {
  symbol: string; quantity: number; avg_cost: number; last_price: number | null
  market_value: number | null; unrealized_pnl: number | null
}
export interface Allocation {
  id: string; theme_id: string; account: string; status: string
  committed_usd: number; cash: number; invested_usd: number; market_value: number | null
  realized_pnl: number; unrealized_pnl: number | null; total_pnl: number | null; total_pnl_pct: number | null
  created_at: string | null; closed_at: string | null; close_reason: string | null
  theme?: { title: string; slug: string; status: string; health: string; conviction: number; hero_stat: string | null }
  holdings?: Holding[]
}

export const listThemes = () => apiFetch<{ themes: Theme[] }>('/api/themes').then(r => r.themes)
export const getTheme = (idOrSlug: string) => apiFetch<Theme>(`/api/themes/${idOrSlug}`)
export const allocateToTheme = (id: string, amount: number, account?: string) =>
  apiFetch<{ allocation: Allocation; investing: boolean }>(`/api/themes/${id}/allocate`, {
    method: 'POST', body: JSON.stringify({ amount, ...(account ? { account } : {}) }),
  })
export const myAllocations = () => apiFetch<{ allocations: Allocation[] }>('/api/themes/allocations/mine').then(r => r.allocations)
export const themeAccount = () => apiFetch<{ connected: boolean; live: boolean; account?: string; buying_power: number; available: number }>('/api/themes/account/summary')
export const unwindAllocation = (allocId: string) =>
  apiFetch<{ unwound: boolean }>(`/api/themes/allocations/${allocId}/unwind`, { method: 'POST' })

// social
export const followTheme = (id: string) =>
  apiFetch<{ following: boolean; n_followers: number }>(`/api/themes/${id}/follow`, { method: 'POST' })
export const listComments = (id: string) =>
  apiFetch<{ comments: Comment[] }>(`/api/themes/${id}/comments`).then(r => r.comments)
export const postComment = (id: string, body: string) =>
  apiFetch<Comment>(`/api/themes/${id}/comments`, { method: 'POST', body: JSON.stringify({ body }) })
export const likeComment = (commentId: string) =>
  apiFetch<{ liked: boolean; likes: number }>(`/api/themes/comments/${commentId}/like`, { method: 'POST' })
export const deleteComment = (commentId: string) =>
  apiFetch<{ deleted: boolean }>(`/api/themes/comments/${commentId}`, { method: 'DELETE' })
