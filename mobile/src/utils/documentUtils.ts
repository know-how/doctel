import { Linking, Alert } from "react-native"

const BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  "http://172.16.4.60:8000"

/**
 * Opens a document for viewing on the device.
 * Uses Linking.openURL which will either open in the browser
 * or trigger the system's file handler for the document type.
 */
export async function downloadAndOpenDocument(
  documentId?: string | null,
  filename?: string | null,
  previewUrl?: string | null,
): Promise<void> {
  if (!documentId) {
    Alert.alert("Error", "No document ID available")
    return
  }

  // Build the download URL using the API endpoint
  const url = `${BASE_URL}/api/documents/${encodeURIComponent(documentId)}/download`

  try {
    await Linking.openURL(url)
  } catch (err: any) {
    // Fallback: try preview_url or the download URL without auth
    if (previewUrl) {
      try {
        await Linking.openURL(previewUrl)
        return
      } catch {}
    }

    // Last resort: show an alert
    Alert.alert(
      "Document",
      filename || `Document ${documentId}`,
      [{ text: "OK" }],
    )
  }
}

/** Returns a single-letter icon and colour for a given filename */
export function fileIconInfo(filename?: string): { letter: string; color: string } {
  if (!filename) return { letter: "D", color: "#6B7280" }
  const ext = filename.split(".").pop()?.toLowerCase()
  if (ext === "pdf") return { letter: "P", color: "#EF4444" }
  if (["doc", "docx"].includes(ext ?? "")) return { letter: "W", color: "#3B82F6" }
  if (["xls", "xlsx"].includes(ext ?? "")) return { letter: "X", color: "#10B981" }
  if (["ppt", "pptx"].includes(ext ?? "")) return { letter: "S", color: "#F59E0B" }
  if (["txt", "md"].includes(ext ?? "")) return { letter: "T", color: "#6B7280" }
  if (["jpg", "jpeg", "png", "gif", "svg", "webp"].includes(ext ?? "")) return { letter: "I", color: "#8B5CF6" }
  return { letter: "D", color: "#6B7280" }
}

export function truncate(text: string, max = 180): string {
  if (!text) return ""
  return text.length > max ? text.slice(0, max) + "…" : text
}

export function chunkLabel(idx?: number): string {
  if (idx === undefined || idx === null) return ""
  return `p.${idx + 1}`
}
