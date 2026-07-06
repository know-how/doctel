import React, { useEffect, useState, useRef } from "react"
import { uploadDocument, getWorkspaces, createProject, getTrainingModelsStatus } from "../api/client"
import { triggerTrainNow, triggerTrainBatch } from "../api/training"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

type ContentCategory = "document" | "image" | "audio" | "video"

const CATEGORY_CONFIG: Record<ContentCategory, { label: string; icon: string; types: string[]; extensions: string[]; description: string }> = {
  document: {
    label: "Document",
    icon: "📄",
    types: ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"],
    extensions: [".pdf", ".docx", ".txt"],
    description: "PDF, Word, TXT",
  },
  image: {
    label: "Image",
    icon: "🖼️",
    types: ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif", "image/bmp"],
    extensions: [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"],
    description: "PNG, JPG, WebP, GIF, BMP",
  },
  audio: {
    label: "Audio",
    icon: "🎙️",
    types: ["audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg", "audio/webm", "audio/flac", "audio/x-m4a"],
    extensions: [".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"],
    description: "WAV, MP3, M4A, OGG, WebM, FLAC",
  },
  video: {
    label: "Video",
    icon: "🎬",
    types: ["video/mp4", "video/avi", "video/quicktime", "video/x-msvideo"],
    extensions: [".mp4", ".avi", ".mov", ".mkv"],
    description: "MP4, AVI, MOV, MKV",
  },
}

interface Workspace {
  id: number | string
  name: string
}

interface FileEntry {
  file: File
  id: string
}

type UploadState = "idle" | "uploading" | "success" | "error"

export const DocumentAddPage: React.FC<{
  onOpenDocument?: (documentId: string) => void
}> = ({ onOpenDocument }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [files, setFiles] = useState<FileEntry[]>([])
  const [projectId, setProjectId] = useState("")
  const [newWorkspaceName, setNewWorkspaceName] = useState("")
  const [workspaceMode, setWorkspaceMode] = useState<"existing" | "new">("existing")
  const [documentType, setDocumentType] = useState("")
  const [documentDate, setDocumentDate] = useState("")
  const [isPublic, setIsPublic] = useState(false)
  const [uploadState, setUploadState] = useState<UploadState>("idle")
  const [progress, setProgress] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [uploadedIds, setUploadedIds] = useState<string[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [contentCategory, setContentCategory] = useState<ContentCategory>("document")
  const [trainModelsInfo, setTrainModelsInfo] = useState<{ models: string[]; models_count: number; admin_only_details: boolean } | null>(null)
  const [trainState, setTrainState] = useState<"idle" | "training" | "done" | "error">("idle")
  const [trainMessage, setTrainMessage] = useState("")
  useEffect(() => {
    getWorkspaces().then((res) => {
      const items = res.projects || res.workspaces || []
      setWorkspaces(items.map((w: any) => ({ id: w.id ?? w.project_id, name: w.name ?? w.project_name })))
    }).catch(() => {})
    getTrainingModelsStatus().then((s) => setTrainModelsInfo(s)).catch(() => {})
  }, [])

  useEffect(() => {
    if (uploadState === "success" && uploadedIds.length === 1 && onOpenDocument) {
      onOpenDocument(uploadedIds[0])
    }
  }, [uploadState, uploadedIds, onOpenDocument])

  const isValidFile = (f: File): boolean => {
     const ext = "." + (f.name.split(".").pop() || "").toLowerCase()
     const cfg = CATEGORY_CONFIG[contentCategory]
     return cfg.types.includes(f.type) || cfg.extensions.includes(ext)
   }

  const handleFilesSelected = (newFiles: FileList | File[]) => {
    setErrorMessage(null)
    const valid: FileEntry[] = []
    for (const f of Array.from(newFiles)) {
      if (isValidFile(f)) {
        valid.push({ file: f, id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}` })
      }
    }
    if (valid.length === 0) {
      setErrorMessage(`No valid files for "${CATEGORY_CONFIG[contentCategory].label}" category. Allowed: ${CATEGORY_CONFIG[contentCategory].description}`)
      return
    }
    setFiles((prev) => [...prev, ...valid])
    setUploadState("idle")
    setUploadedIds([])
  }

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files)
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    const effectiveProjectId = workspaceMode === "new" ? null : projectId
    const effectiveProjectName = workspaceMode === "new" ? newWorkspaceName.trim() || "Uncategorized" : projectId ? null : "Uncategorized"

    // If creating new workspace, create it first
    if (workspaceMode === "new" && newWorkspaceName.trim()) {
      try {
        const proj = await createProject(newWorkspaceName.trim())
        setProjectId(String((proj as any).id ?? (proj as any).project_id ?? ""))
        setWorkspaceMode("existing")
        // Refresh workspaces
        getWorkspaces().then((res) => {
          const items = res.projects || res.workspaces || []
          setWorkspaces(items.map((w: any) => ({ id: w.id ?? w.project_id, name: w.name ?? w.project_name })))
        }).catch(() => {})
      } catch (e: any) {
        // Continue with project_name anyway — backend will auto-create
      }
    }

    setUploadState("uploading")
    setProgress(0)
    setErrorMessage(null)
    const uploaded: string[] = []

    try {
      const total = files.length
      for (let i = 0; i < files.length; i++) {
        const { file } = files[i]
        const result = await uploadDocument(file, {
          project_id: effectiveProjectId || null,
          project_name: effectiveProjectName,
          document_type: documentType || null,
          document_date: documentDate || null,
          is_public: isPublic,
        })
        uploaded.push(result.id ?? String(result.id))
        setProgress(Math.round(((i + 1) / total) * 100))
        setUploadedIds([...uploaded])
      }

      setProgress(100)
      setUploadState("success")
      setUploadedIds(uploaded)
    } catch (e: any) {
      setUploadState("error")
      setErrorMessage(e.message ?? "Upload failed")
      setProgress(0)
    }
  }

  const handleTrainModel = async () => {
    setTrainState("training")
    setTrainMessage("Starting transfer learning on local Llama models...")
    try {
      // Use the training room endpoint to train on project documents
      let result: any
      try {
        result = await triggerTrainBatch()
      } catch {
        result = await triggerTrainNow()
      }
      setTrainState("done")
      setTrainMessage(
        result?.ok
          ? "✅ Model training started! The local model will now learn from uploaded ZETDC documents."
          : `Training queued: ${result?.reason || "Model will be updated with new knowledge."}`
      )
    } catch (e: any) {
      setTrainState("error")
      setTrainMessage(e.message || "Training could not be started. Check admin training room.")
    }
  }

  const reset = () => {
    setFiles([])
    setProjectId("")
    setNewWorkspaceName("")
    setWorkspaceMode("existing")
    setDocumentType("")
    setDocumentDate("")
    setIsPublic(false)
    setUploadState("idle")
    setProgress(0)
    setErrorMessage(null)
    setUploadedIds([])
    setTrainModelsInfo(null)
  }

  const isDark = theme === "dark"

  return (
    <div style={{ padding: t.spacing.xl, maxWidth: 860, margin: "0 auto" }}>
      <h1 style={{ fontSize: 28, fontWeight: 800, color: t.colors.text, margin: 0, letterSpacing: "-0.02em" }}>
        Upload Documents
      </h1>
      <p style={{ margin: "4px 0 0", fontSize: 14, color: t.colors.textSecondary }}>
        Add files for analysis, processing, and ZETDC knowledge training
      </p>

      {/* ── Category selector ── */}
      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        {(Object.keys(CATEGORY_CONFIG) as ContentCategory[]).map((cat) => {
          const cfg = CATEGORY_CONFIG[cat]
          const active = contentCategory === cat
          return (
            <button key={cat} type="button" onClick={() => { setContentCategory(cat); setFiles([]); setErrorMessage(null); setUploadState("idle") }}
              style={{
                display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: 10,
                border: `1px solid ${active ? t.colors.primary : t.colors.border}`,
                background: active ? t.colors.surfaceActive : "transparent",
                color: active ? t.colors.primary : t.colors.textMuted,
                fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.15s ease",
              }}>
              <span style={{ fontSize: 16 }}>{cfg.icon}</span>
              <span>{cfg.label}</span>
            </button>
          )
        })}
      </div>

      {/* ── Success ── */}
      {uploadState === "success" && (
        <div style={{ background: t.colors.cardBg, borderRadius: 14, border: `1px solid ${t.colors.border}`, padding: 40, marginTop: 24, textAlign: "center" }}>
          <div style={{ width: 60, height: 60, borderRadius: "50%", background: `${t.colors.success}18`, border: `2px solid ${t.colors.success}`, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
            <span style={{ color: t.colors.success, fontSize: 30 }}>✓</span>
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: t.colors.text, marginBottom: 6 }}>
            {uploadedIds.length} document{uploadedIds.length > 1 ? "s" : ""} uploaded
          </div>
          <div style={{ fontSize: 13, color: t.colors.textSecondary, marginBottom: 24 }}>
            {files.map((f) => f.file.name).join(", ")}
          </div>
          <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
            <button type="button" onClick={reset}
              style={{ background: "transparent", color: t.colors.textSecondary, border: `1px solid ${t.colors.border}`, borderRadius: 8, padding: "10px 20px", fontSize: 13, cursor: "pointer" }}>
              Upload More
            </button>
            {uploadedIds.length === 1 && (
              <button type="button" onClick={() => onOpenDocument?.(uploadedIds[0])}
                style={{ background: t.colors.primary, color: "#FFF", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                Open in Analyzer
              </button>
            )}
            {/* Batch analyze */}
            {uploadedIds.length >= 1 && (
              <button type="button" onClick={() => onOpenDocument?.(uploadedIds[0])}
                style={{ background: `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`, color: "#FFF", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                🧠 Batch Analyze
              </button>
            )}
            {/* Transfer learning */}
            {trainState === "idle" && (
              <button type="button" onClick={handleTrainModel}
                style={{ background: `linear-gradient(135deg, ${t.colors.accent}, #D97706)`, color: "#FFF", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                ⚡ Train Local Model
              </button>
            )}
          </div>

          {/* Training status */}
          {trainState !== "idle" && (
            <div style={{ marginTop: 20, padding: "14px 18px", background: trainState === "error" ? `${t.colors.error}10` : `${t.colors.primary}08`, borderRadius: 10, border: `1px solid ${trainState === "error" ? t.colors.error + "30" : t.colors.primary + "20"}` }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: trainState === "error" ? t.colors.error : t.colors.text, marginBottom: 4 }}>
                {trainState === "training" ? "⏳ Training in progress..." : trainState === "done" ? "✅ Training Complete" : "❌ Training Failed"}
              </div>
              <div style={{ fontSize: 12, color: t.colors.textSecondary }}>{trainMessage}</div>
            </div>
          )}
        </div>
      )}

      {/* ── Error ── */}
      {uploadState === "error" && (
        <div style={{ background: t.colors.cardBg, borderRadius: 14, border: `1px solid ${t.colors.border}`, padding: 40, marginTop: 24, textAlign: "center" }}>
          <div style={{ width: 60, height: 60, borderRadius: "50%", background: `${t.colors.error}18`, border: `2px solid ${t.colors.error}`, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
            <span style={{ color: t.colors.error, fontSize: 28 }}>✕</span>
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: t.colors.error, marginBottom: 6 }}>Upload Failed</div>
          <div style={{ fontSize: 13, color: t.colors.textSecondary, marginBottom: 20 }}>{errorMessage}</div>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button type="button" onClick={reset}
              style={{ background: "transparent", color: t.colors.textSecondary, border: `1px solid ${t.colors.border}`, borderRadius: 8, padding: "10px 20px", fontSize: 13, cursor: "pointer" }}>
              Cancel
            </button>
            <button type="button" onClick={handleUpload}
              style={{ background: t.colors.primary, color: "#FFF", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
              Retry
            </button>
          </div>
        </div>
      )}

      {/* ── Main form ── */}
      {uploadState !== "success" && uploadState !== "error" && (
        <>
          <input ref={fileInputRef} type="file" multiple accept={CATEGORY_CONFIG[contentCategory].types.join(",")}
            onChange={(e) => { if (e.target.files) handleFilesSelected(e.target.files); }}
            style={{ display: "none" }} />

          {/* Drop zone */}
          <div onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            style={{
              background: dragOver ? `${t.colors.primary}08` : t.colors.cardBg,
              borderRadius: 14, border: `2px dashed ${dragOver ? t.colors.primary : t.colors.border}`,
              padding: 48, marginTop: 24, textAlign: "center", cursor: "pointer",
              transition: "all 0.2s ease",
            }}>
            {files.length > 0 ? (
              <div>
                <div style={{ fontSize: 36, marginBottom: 10 }}>{CATEGORY_CONFIG[contentCategory].icon}</div>
                <div style={{ fontWeight: 700, color: t.colors.text, fontSize: 15, marginBottom: 12 }}>
                  {files.length} file{files.length > 1 ? "s" : ""} selected
                </div>
                {/* File list */}
                <div style={{ maxWidth: 500, margin: "0 auto", display: "flex", flexDirection: "column", gap: 6 }}>
                  {files.map((f) => (
                    <div key={f.id} style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      padding: "8px 14px", background: t.colors.surfaceHover, borderRadius: 8,
                      fontSize: 13, gap: 10,
                    }}>
                      <span style={{ flex: 1, textAlign: "left", color: t.colors.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {f.file.name}
                      </span>
                      <span style={{ color: t.colors.textMuted, fontSize: 11, flexShrink: 0 }}>
                        {(f.file.size / 1024).toFixed(1)} KB
                      </span>
                      <button type="button" onClick={(e) => { e.stopPropagation(); removeFile(f.id) }}
                        style={{ background: "none", border: "none", color: t.colors.error, cursor: "pointer", fontSize: 16, padding: 0, lineHeight: 1 }}>
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
                <button type="button" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }}
                  style={{ marginTop: 14, background: "none", border: "none", color: t.colors.primary, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                  + Add more files
                </button>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 44, marginBottom: 12 }}>{CATEGORY_CONFIG[contentCategory].icon}</div>
                <div style={{ fontWeight: 600, color: t.colors.text, fontSize: 15, marginBottom: 6 }}>
                  Drop {CATEGORY_CONFIG[contentCategory].label.toLowerCase()}s here or click to browse
                </div>
                <div style={{ fontSize: 12, color: t.colors.textSecondary }}>
                  Supported: {CATEGORY_CONFIG[contentCategory].description}
                </div>
              </div>
            )}
          </div>

          {/* Progress */}
          {uploadState === "uploading" && (
            <div style={{ marginTop: 16 }}>
              <div style={{ height: 8, borderRadius: 999, background: t.colors.surface, overflow: "hidden" }}>
                <div style={{ height: "100%", borderRadius: 999, background: `linear-gradient(90deg, ${t.colors.primary}, ${t.colors.secondary})`, transition: "width 0.3s ease", width: `${progress}%` }} />
              </div>
              <div style={{ fontSize: 12, color: t.colors.textSecondary, marginTop: 6, textAlign: "right" }}>
                Uploading {Math.round(progress)}% · {files.length} file{files.length > 1 ? "s" : ""}
              </div>
            </div>
          )}

          {/* Metadata fields */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 24 }}>
            {/* Repository / Workspace */}
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: t.colors.textSecondary, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Repository / Workspace
              </label>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                {[
                  { mode: "existing" as const, label: "Select existing" },
                  { mode: "new" as const, label: "Create new" },
                ].map((opt) => (
                  <button key={opt.mode} type="button" onClick={() => setWorkspaceMode(opt.mode)}
                    style={{
                      flex: 1, padding: "7px 12px", borderRadius: 8, border: `1px solid ${workspaceMode === opt.mode ? t.colors.primary : t.colors.border}`,
                      background: workspaceMode === opt.mode ? t.colors.surfaceActive : "transparent",
                      color: workspaceMode === opt.mode ? t.colors.primary : t.colors.textMuted,
                      fontSize: 12, fontWeight: 600, cursor: "pointer",
                    }}>
                    {opt.label}
                  </button>
                ))}
              </div>

              {workspaceMode === "existing" ? (
                <select value={projectId} onChange={(e) => setProjectId(e.target.value)}
                  style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: `1px solid ${t.colors.border}`, background: t.colors.inputBg, color: t.colors.text, fontSize: 13, cursor: "pointer", outline: "none", WebkitAppearance: "none", MozAppearance: "none", appearance: "none", backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%23${isDark ? 'ffffff' : '0a1628'}40' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: "right 10px center", backgroundRepeat: "no-repeat", backgroundSize: "16px", paddingRight: "32px" }}>
                  <option value="">Select a repository…</option>
                  {workspaces.map((w) => (
                    <option key={w.id} value={String(w.id)}>{w.name}</option>
                  ))}
                </select>
              ) : (
                <input type="text" placeholder="Enter repository / workspace name"
                  value={newWorkspaceName} onChange={(e) => setNewWorkspaceName(e.target.value)}
                  style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: `1px solid ${t.colors.border}`, background: t.colors.inputBg, color: t.colors.text, fontSize: 13, outline: "none", boxSizing: "border-box" }} />
              )}
            </div>

            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: t.colors.textSecondary, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Document Type
              </label>
              <input type="text" placeholder="e.g. Report, Memo, Contract"
                value={documentType} onChange={(e) => setDocumentType(e.target.value)}
                style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: `1px solid ${t.colors.border}`, background: t.colors.inputBg, color: t.colors.text, fontSize: 13, outline: "none", boxSizing: "border-box" }} />
            </div>

            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: t.colors.textSecondary, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Document Date
              </label>
              <input type="date" value={documentDate} onChange={(e) => setDocumentDate(e.target.value)}
                style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: `1px solid ${t.colors.border}`, background: t.colors.inputBg, color: t.colors.text, fontSize: 13, outline: "none", boxSizing: "border-box", colorScheme: isDark ? "dark" : "light" }} />
            </div>

            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: t.colors.textSecondary, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Visibility
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" onClick={() => setIsPublic(false)}
                  style={{
                    flex: 1, padding: "10px 14px", borderRadius: 8, border: `1px solid ${!isPublic ? t.colors.primary : t.colors.border}`,
                    background: !isPublic ? t.colors.surfaceActive : "transparent",
                    color: !isPublic ? t.colors.primary : t.colors.textMuted,
                    fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                  }}>
                  <span>🔒</span> Private
                </button>
                <button type="button" onClick={() => setIsPublic(true)}
                  style={{
                    flex: 1, padding: "10px 14px", borderRadius: 8, border: `1px solid ${isPublic ? t.colors.primary : t.colors.border}`,
                    background: isPublic ? t.colors.surfaceActive : "transparent",
                    color: isPublic ? t.colors.primary : t.colors.textMuted,
                    fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                  }}>
                  <span>🌐</span> Public
                </button>
              </div>
            </div>
          </div>

          {/* Transfer learning info */}
          <div style={{
            marginTop: 24, padding: "14px 18px",
            background: isDark ? "rgba(251,191,36,0.06)" : "rgba(243,111,33,0.05)",
            borderRadius: 10, border: `1px solid ${t.colors.accent}20`,
            display: "flex", alignItems: "flex-start", gap: 10,
          }}>
            <span style={{ fontSize: 18, flexShrink: 0 }}>⚡</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: t.colors.text, marginBottom: 3 }}>
                Transfer Learning Ready
              </div>
              <div style={{ fontSize: 11, color: t.colors.textSecondary, lineHeight: 1.5 }}>
                After uploading, local Llama models are automatically trained on ZETDC documents.
                This enables models to learn your organization's knowledge for accurate, domain-specific responses.
              </div>
              {trainModelsInfo && (
                <div style={{ marginTop: 8, fontSize: 10, color: t.colors.textMuted }}>
                  {trainModelsInfo.models_count} model{trainModelsInfo.models_count > 1 ? 's' : ''} configured for auto-training
                </div>
              )}
            </div>
          </div>

          {/* Upload button */}
          <div style={{ marginTop: 24 }}>
            <button type="button" onClick={handleUpload}
              disabled={files.length === 0 || uploadState === "uploading"}
              style={{
                width: "100%", padding: "14px", borderRadius: 10,
                border: "none", fontSize: 15, fontWeight: 700, cursor: files.length === 0 ? "not-allowed" : "pointer",
                background: files.length === 0 || uploadState === "uploading"
                  ? t.colors.border
                  : `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`,
                color: "#FFF", opacity: files.length === 0 ? 0.5 : 1,
                letterSpacing: "0.02em",
              }}>
              {uploadState === "uploading"
                ? `Uploading ${files.length} file${files.length > 1 ? "s" : ""}… ${progress}%`
                : `Upload ${files.length > 0 ? files.length : ""} Document${files.length > 1 ? "s" : ""}`}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
