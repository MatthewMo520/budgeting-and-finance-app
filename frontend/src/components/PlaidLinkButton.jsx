import { useCallback, useEffect, useState } from "react"
import { usePlaidLink } from "react-plaid-link"
import { useAuth } from "../AuthContext"

export default function PlaidLinkButton({ onSuccess, className = "hdr-connect", label = "+ Connect bank", style }) {
  const { apiFetch } = useAuth()
  const [linkToken, setLinkToken] = useState(null)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    apiFetch("/plaid/create-link-token", { method: "POST" })
      .then(r => r.json())
      .then(d => setLinkToken(d.link_token))
  }, [apiFetch])

  const onPlaidSuccess = useCallback(async (publicToken) => {
    setSyncing(true)
    try {
      const res = await apiFetch("/plaid/exchange-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_token: publicToken }),
      })
      const data = await res.json()
      onSuccess(data.transactions_synced)
    } finally {
      setSyncing(false)
    }
  }, [apiFetch, onSuccess])

  const { open, ready } = usePlaidLink({ token: linkToken, onSuccess: onPlaidSuccess })

  return (
    <button
      className={className}
      style={style}
      onClick={() => open()}
      disabled={!ready || syncing}
    >
      {syncing ? "Syncing…" : label}
    </button>
  )
}
