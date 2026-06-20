import { Moon, Sun } from "lucide-react"
import { useTheme } from "../providers/ThemeProvider"

export function ThemeToggle() {
    const { setTheme, theme } = useTheme()

    const handleClick = () => {
        const newTheme = theme === "light" ? "dark" : "light"
        setTheme(newTheme)
    }

    return (
        <button
            type="button"
            onClick={handleClick}
            className="relative p-2 rounded-lg bg-gray-100 dark:bg-white/5 text-gray-900 dark:text-gray-100 dark:hover:bg-white/10 hover:bg-gray-200 transition-all active:scale-95 hover:scale-105 cursor-pointer"
            aria-label="Toggle theme"
        >
            <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute top-2 left-2 h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
        </button>
    )
}
