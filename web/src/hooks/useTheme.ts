import { useEffect, useState } from 'react'

export type ThemePreference = 'system' | 'dark' | 'light'
const KEY = 'a2a-theme'

function readPreference(): ThemePreference {
  try {
    const item = localStorage.getItem(KEY)
    return item === 'light' || item === 'dark' ? item : 'system'
  } catch {
    return 'system'
  }
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(readPreference)

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference
      document.documentElement.dataset.theme = theme
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#000000' : '#F5F5F5')
    }
    apply()
    media.addEventListener('change', apply)
    try { localStorage.setItem(KEY, preference) } catch { /* private browsing */ }
    return () => media.removeEventListener('change', apply)
  }, [preference])

  return { preference, setPreference }
}
