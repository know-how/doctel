import { useEffect, useState } from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"

const STORAGE_KEY = "docintel_ec_number"

export function useEcNumber() {
  const [ecNumber, setEcNumberState] = useState<string>("")

  useEffect(() => {
    const load = async () => {
      const stored = await AsyncStorage.getItem(STORAGE_KEY)
      if (stored) {
        setEcNumberState(stored)
      }
    }
    load()
  }, [])

  const setEcNumber = async (value: string) => {
    const trimmed = value.trim()
    setEcNumberState(trimmed)
    if (trimmed) {
      await AsyncStorage.setItem(STORAGE_KEY, trimmed)
    } else {
      await AsyncStorage.removeItem(STORAGE_KEY)
    }
  }

  return { ecNumber, setEcNumber }
}
