import { createContext, useContext, useEffect, useState } from "react"

// "light" | "dark" | "system" — persisted in localStorage, applied as
// document.documentElement[data-theme] so CSS tokens switch everywhere.
const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "system")

  useEffect(() => {
    localStorage.setItem("theme", theme)
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () => {
      const resolved = theme === "system" ? (mq.matches ? "dark" : "light") : theme
      document.documentElement.dataset.theme = resolved
    }
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [theme])

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  return useContext(ThemeContext)
}
