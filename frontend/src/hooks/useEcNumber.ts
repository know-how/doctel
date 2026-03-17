import { useEffect, useState } from "react"

const STORAGE_KEY = "docintel_ec_number"

export function useEcNumber() {
  const [ecNumber, setEcNumberState] = useState<string>("")

  useEffect(() => {
    if (typeof window === "undefined") return
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) {
      setEcNumberState(stored)
    }
  }, [])

  const setEcNumber = (value: string) => {
    const trimmed = value.trim()
    setEcNumberState(trimmed)
    if (typeof window !== "undefined") {
      if (trimmed) {
        window.localStorage.setItem(STORAGE_KEY, trimmed)
      } else {
        window.localStorage.removeItem(STORAGE_KEY)
      }
    }
  }

  return { ecNumber, setEcNumber }
}

