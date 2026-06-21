import { createContext, useContext, useState, useEffect, useRef, useCallback } from "react"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // Access token is kept in memory only (never localStorage) so XSS can't
  // exfiltrate it. The refresh token lives in an httpOnly cookie the JS can't read.
  const [accessToken, setAccessToken] = useState(null)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const apiBase = import.meta.env.VITE_API_URL || "/api"

  const tokenRef = useRef(null)
  tokenRef.current = accessToken

  function setToken(access) {
    tokenRef.current = access
    setAccessToken(access)
  }

  const fetchMe = useCallback(async (token) => {
    const res = await fetch(`${apiBase}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) throw new Error("me failed")
    return res.json()
  }, [apiBase])

  // On load, try to mint a new access token from the refresh cookie, then bootstrap the user.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${apiBase}/auth/refresh`, { method: "POST", credentials: "include" })
        if (!res.ok) throw new Error("no session")
        const { access_token } = await res.json()
        const me = await fetchMe(access_token)
        if (!cancelled) { setToken(access_token); setUser(me) }
      } catch {
        if (!cancelled) { setToken(null); setUser(null) }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [apiBase, fetchMe])

  const refreshUser = useCallback(async () => {
    const token = tokenRef.current
    if (!token) return
    try { setUser(await fetchMe(token)) } catch { /* ignore */ }
  }, [fetchMe])

  // Called by login pages after a successful auth (refresh cookie is already set by the server).
  // Adopts the in-memory access token and loads the user profile.
  async function saveTokens(access) {
    setToken(access)
    try { setUser(await fetchMe(access)) } catch { /* ignore */ }
  }

  async function logout() {
    try { await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" }) } catch { /* ignore */ }
    setToken(null)
    setUser(null)
  }

  /**
   * fetch() wrapper that injects the Authorization header, and on a 401 tries to
   * mint a fresh access token from the refresh cookie once, then retries.
   */
  const apiFetch = useCallback(async (path, options = {}) => {
    const withAuth = (token) => ({
      ...options,
      credentials: "include",
      headers: { ...options.headers, Authorization: `Bearer ${token}` },
    })

    let res = await fetch(`${apiBase}${path}`, withAuth(tokenRef.current))

    if (res.status === 401) {
      const refreshRes = await fetch(`${apiBase}/auth/refresh`, { method: "POST", credentials: "include" })
      if (!refreshRes.ok) {
        setToken(null); setUser(null)
        return res
      }
      const { access_token } = await refreshRes.json()
      setToken(access_token)
      res = await fetch(`${apiBase}${path}`, withAuth(access_token))
    }

    return res
  }, [apiBase])

  return (
    <AuthContext.Provider value={{ accessToken, user, loading, saveTokens, logout, apiFetch, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
