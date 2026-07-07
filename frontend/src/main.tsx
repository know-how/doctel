import React from "react"
import ReactDOM from "react-dom/client"
import { App } from "./App"
import { globalStyles } from "./theme/globalStyles"

// Inject global styles
const styleElement = document.createElement("style")
styleElement.innerHTML = globalStyles
document.head.appendChild(styleElement)

// ── Error boundary to prevent blank page on runtime errors ─────────────
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary] Caught:", error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          minHeight: "100vh", background: "#070B14", color: "#E0E0E0", fontFamily: "sans-serif", padding: 32, textAlign: "center"
        }}>
          <h1 style={{ color: "#FF6B6B", marginBottom: 16 }}>Something went wrong</h1>
          <pre style={{ maxWidth: 600, overflow: "auto", background: "#0F1117", padding: 16, borderRadius: 8, fontSize: 13 }}>
            {this.state.error?.message}
          </pre>
          <button onClick={() => window.location.reload()} style={{
            marginTop: 24, padding: "10px 24px", border: "none", borderRadius: 6,
            background: "#4A6CF7", color: "#FFF", fontSize: 14, cursor: "pointer"
          }}>
            Reload Page
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)

