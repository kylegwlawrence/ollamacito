import { createContext, useContext, useEffect, ReactNode } from 'react'

const THEME = 'dark'

interface ThemeContextType {
  theme: 'dark'
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-theme', THEME)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme: THEME }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
