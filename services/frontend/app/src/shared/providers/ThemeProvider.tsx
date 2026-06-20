/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

type Theme = "dark" | "light" | "system"
type ResolvedTheme = "dark" | "light"

type ThemeProviderProps = {
    children: React.ReactNode
    defaultTheme?: Theme
    storageKey?: string
}

type ThemeProviderState = {
    theme: Theme
    resolvedTheme: ResolvedTheme
    setTheme: (theme: Theme) => void
}

const initialState: ThemeProviderState = {
    theme: "system",
    resolvedTheme: "light",
    setTheme: () => null,
}

const ThemeProviderContext = createContext<ThemeProviderState>(initialState)

function getSystemTheme(): ResolvedTheme {
    if (typeof globalThis.matchMedia !== "function") {
        return "light"
    }
    return globalThis.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function ThemeProvider({
    children,
    defaultTheme = "system",
    storageKey = "vite-ui-theme",
}: ThemeProviderProps) {
    const [theme, setThemeState] = useState<Theme>(
        () => (localStorage.getItem(storageKey) as Theme) || defaultTheme
    )
    const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
        theme === "system" ? getSystemTheme() : (theme as ResolvedTheme)
    )

    useEffect(() => {
        const root = globalThis.document.documentElement
        root.classList.remove("light", "dark")

        if (theme === "system") {
            const systemTheme = getSystemTheme()
            setResolvedTheme(systemTheme)
            root.classList.add(systemTheme)
            if (typeof globalThis.matchMedia !== "function") {
                return
            }
            const mq = globalThis.matchMedia("(prefers-color-scheme: dark)")
            const listener = () => {
                const next = getSystemTheme()
                setResolvedTheme(next)
                root.classList.remove("light", "dark")
                root.classList.add(next)
            }
            mq.addEventListener("change", listener)
            return () => mq.removeEventListener("change", listener)
        }

        const resolved = theme as ResolvedTheme
        setResolvedTheme(resolved)
        root.classList.add(resolved)
    }, [theme])

    const setTheme = useCallback((nextTheme: Theme) => {
        localStorage.setItem(storageKey, nextTheme)
        setThemeState(nextTheme)
    }, [storageKey])

    const value = useMemo(() => ({
        theme,
        resolvedTheme,
        setTheme,
    }), [theme, resolvedTheme, setTheme])

    return (
        <ThemeProviderContext.Provider value={value}>
            {children}
        </ThemeProviderContext.Provider>
    )
}

export const useTheme = () => {
    const context = useContext(ThemeProviderContext)

    if (context === undefined)
        throw new Error("useTheme must be used within a ThemeProvider")

    return context
}
