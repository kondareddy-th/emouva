import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Wallet, Check } from 'lucide-react'
import clsx from 'clsx'
import { apiFetch } from '../api/client'
import { getSelectedAccount, setSelectedAccount, syncPortfolio } from '../hooks/usePortfolioStore'

interface Account {
  account_number: string
  type: string
  nickname: string | null
  is_default: boolean
  is_agentic: boolean
  is_paper?: boolean
}

function label(a: Account): string {
  if (a.is_paper) return `${a.nickname || 'Paper'} · paper money`
  const base = a.nickname || (a.is_default ? 'Individual' : a.type)
  const tag = a.is_agentic ? ' · Agentic' : a.is_default ? ' · Default' : ''
  return `${base} (••${a.account_number.slice(-4)})${tag}`
}

// Compact label for the trigger button (the popover shows the full label).
function shortLabel(a: Account): string {
  if (a.is_paper) return a.nickname || 'Paper'
  const base = a.nickname || (a.is_default ? 'Individual' : a.type)
  return `${base} ••${a.account_number.slice(-4)}`
}

/** Switches which Robinhood account the dashboard reflects. Custom popover (not a native
 *  <select>) so the option list matches our dark UI. Hidden unless there's >1 account. */
export default function AccountSwitcher() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selected, setSelected] = useState<string | null>(getSelectedAccount())
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    apiFetch<{ accounts: Account[] }>('/api/robinhood/accounts')
      .then((r) => setAccounts(r.accounts || []))
      .catch(() => setAccounts([]))
  }, [])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  if (accounts.length <= 1) return null

  const current =
    accounts.find((a) => a.account_number === selected) ||
    accounts.find((a) => a.is_default) ||
    accounts[0]

  const onChange = (acctNum: string) => {
    const isDefault = accounts.find((a) => a.account_number === acctNum)?.is_default
    setSelectedAccount(isDefault ? null : acctNum) // null = default account
    setSelected(acctNum)
    setOpen(false)
    syncPortfolio().catch(() => {})
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-[8px] bg-surface-2 border border-[rgba(180,220,190,0.12)] hover:border-accent/40 transition-colors"
      >
        <Wallet className="w-3.5 h-3.5 text-accent flex-none" />
        <span className="text-[13px] font-mono tabular-nums text-text-secondary max-w-[160px] truncate">{shortLabel(current)}</span>
        <ChevronDown className={clsx('w-3.5 h-3.5 text-text-tertiary transition-transform flex-none', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-[268px] max-h-[320px] overflow-y-auto rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.14)] shadow-xl shadow-black/50 z-[60] py-1">
          {accounts.map((a) => {
            const on = a.account_number === current?.account_number
            return (
              <button
                key={a.account_number}
                onClick={() => onChange(a.account_number)}
                className={clsx(
                  'w-full flex items-center gap-2 px-3 py-2 text-left text-[12.5px] font-mono tabular-nums transition-colors',
                  on ? 'text-accent bg-accent/10' : 'text-text-secondary hover:bg-[rgba(180,220,190,0.05)]'
                )}
              >
                <Check className={clsx('w-3.5 h-3.5 flex-none', on ? 'text-accent opacity-100' : 'opacity-0')} strokeWidth={2} />
                <span className="truncate">{label(a)}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
