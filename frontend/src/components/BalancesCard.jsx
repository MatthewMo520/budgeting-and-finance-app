import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../AuthContext"

const fmt = (n) => "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export default function BalancesCard() {
  const { user, apiFetch } = useAuth()
  const [banks, setBanks] = useState(null)   // null = loading
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true)
    try {
      const res = await apiFetch(`/plaid/balances${refresh ? "?refresh=true" : ""}`)
      if (res.ok) setBanks(await res.json())
      else setBanks([])
    } catch {
      setBanks([])
    } finally {
      setRefreshing(false)
    }
  }, [apiFetch])

  useEffect(() => { if (user?.has_bank) load() }, [user?.has_bank, load])

  if (!user?.has_bank) return null

  const allAccounts = (banks || []).flatMap(b => b.accounts)
  const total = allAccounts.reduce((s, a) => s + (a.available ?? a.current ?? 0), 0)

  return (
    <div className="bal-card">
      <div className="bal-hdr">
        <div className="chart-title" style={{ marginBottom: 0 }}>Accounts</div>
        <div className="bal-hdr-right">
          {allAccounts.length > 0 && (
            <span className="bal-total">{fmt(total)} <span className="bal-total-label">total</span></span>
          )}
          <button className="bal-refresh" onClick={() => load(true)} disabled={refreshing} aria-label="Refresh balances">
            {refreshing ? "…" : "↻"}
          </button>
        </div>
      </div>

      {banks === null ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }} aria-hidden="true">
          <div className="skeleton" style={{ height: 38 }} />
          <div className="skeleton" style={{ height: 38 }} />
        </div>
      ) : banks.length === 0 ? (
        <div className="bal-loading">Balances are unavailable right now — try refreshing.</div>
      ) : (
        <div className="bal-rows">
          {banks.map((b, i) => (
            b.error ? (
              <div key={i} className="bal-row">
                <div className="bal-name">{b.institution}</div>
                <div className="bal-sub">Couldn't reach this bank — try refreshing</div>
              </div>
            ) : b.accounts.map((a, j) => (
              <div key={`${i}-${j}`} className="bal-row">
                <div>
                  <div className="bal-name">{a.name}{a.mask ? <span className="bal-mask"> ••{a.mask}</span> : null}</div>
                  <div className="bal-sub">{b.institution}{a.subtype ? ` · ${a.subtype}` : ""}</div>
                </div>
                <div className="bal-amt">
                  {fmt(a.available ?? a.current ?? 0)}
                  {a.available != null && a.current != null && a.available !== a.current && (
                    <div className="bal-sub" style={{ textAlign: "right" }}>{fmt(a.current)} current</div>
                  )}
                </div>
              </div>
            ))
          ))}
        </div>
      )}
    </div>
  )
}
