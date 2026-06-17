import { createContext, useContext, useState, useEffect, useRef, useCallback } from "react"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(() => localStorage.getItem("access_token"))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const apiBase = import.meta.env.VITE_API_URL || "/api"

  // Keep a ref so apiFetch always sees the latest token without re-creating the function
  const tokenRef = useRef(accessToken)
  tokenRef.current = accessToken

  useEffect(() => {
    if (!accessToken) { setLoading(false); return }
    fetch(`${apiBase}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(data => setUser(data))
      .catch(() => {
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
        setAccessToken(null)
      })
      .finally(() => setLoading(false))
  }, [accessToken])

  const refreshUser = useCallback(async () => {
    const token = tokenRef.current
    if (!token) return
    const res = await fetch(`${apiBase}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) setUser(await res.json())
  }, [])

  function saveTokens(access, refresh) {
    localStorage.setItem("access_token", access)
    if (refresh) localStorage.setItem("refresh_token", refresh)
    setAccessToken(access)
    tokenRef.current = access
  }

  function logout() {
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
    setAccessToken(null)
    setUser(null)
  }

  /**
   * Drop-in replacement for fetch() that:
   * 1. Injects Authorization header automatically
   * 2. On 401, tries to refresh the access token once
   * 3. Retries the original request with the new token
   * 4. Logs out if refresh also fails
   */
  const apiFetch = useCallback(async (path, options = {}) => {
    const authHeaders = { Authorization: `Bearer ${tokenRef.current}` }
    const mergedOptions = {
      ...options,
      headers: { ...options.headers, ...authHeaders },
    }

    let res = await fetch(`${apiBase}${path}`, mergedOptions)

    if (res.status === 401) {
      const refreshToken = localStorage.getItem("refresh_token")
      if (!refreshToken) { logout(); return res }

      const refreshRes = await fetch(`${apiBase}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (!refreshRes.ok) { logout(); return res }

      const { access_token } = await refreshRes.json()
      saveTokens(access_token, null)

      // Retry original request with new token
      res = await fetch(`${apiBase}${path}`, {
        ...options,
        headers: { ...options.headers, Authorization: `Bearer ${access_token}` },
      })
    }

    return res
  }, [])

  return (
    <AuthContext.Provider value={{ accessToken, user, loading, saveTokens, logout, apiFetch, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
