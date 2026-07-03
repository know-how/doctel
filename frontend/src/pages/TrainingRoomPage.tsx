import React, { useCallback, useEffect, useRef, useState } from "react"
import { colors } from "../theme/colors"
import {
  getTrainingStatus,
  getTrainingHistory,
  getInboxFiles,
  getRouterStatus,
  triggerTrainNow,
  triggerTrainIdle,
  triggerTrainBatch,
  uploadInboxFile,
  TrainingJobStatus,
  AdapterRecord,
  InboxFile,
  RouterStatusResponse,
} from "../api/training"
import { distillFromCloud } from "../api/client"

// ── helpers ───────────────────────────────────────────────────────────────────

const pct = (n: number) => `${Math.round(n * 100)}%`
const fmt = (iso?: string) =>
  iso ? new Date(iso).toLocaleString() : "—"

function StatusPill({ value }: { value: string }) {
  const map: Record<string, string> = {
    running: "#1976d2",
    done: "#2e7d32",
    error: colors.danger,
    skipped: colors.textMuted,
    pending: colors.accentOrange,
    idle: colors.textMuted,
  }
  const col = map[value] ?? colors.textMuted
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 700,
        background: col + "22",
        color: col,
        border: `1px solid ${col}44`,
        textTransform: "capitalize",
      }}
    >
      {value}
    </span>
  )
}

function TierDot({ active }: { active: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: active ? "#2e7d32" : "#9e9e9e",
        marginRight: 6,
        flexShrink: 0,
      }}
    />
  )
}

// ── main component ─────────────────────────────────────────────────────────────

export const TrainingRoomPage: React.FC = () => {
  const [job, setJob] = useState<TrainingJobStatus | null>(null)
  const [jobStatus, setJobStatus] = useState("idle")
  const [adapters, setAdapters] = useState<AdapterRecord[]>([])
  const [inboxFiles, setInboxFiles] = useState<InboxFile[]>([])
  const [router, setRouter] = useState<RouterStatusResponse | null>(null)
  const [batchFolder, setBatchFolder] = useState("")
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState("")
  const [actionMsg, setActionMsg] = useState("")
  const [actionError, setActionError] = useState("")
  const [distilling, setDistilling] = useState(false)
  const [distillResult, setDistillResult] = useState<string>("")
  const dropRef = useRef<HTMLDivElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── data loading ─────────────────────────────────────────────────────────────

  const loadAll = useCallback(async () => {
    try {
      const [st, hist, inbox, rs] = await Promise.allSettled([
        getTrainingStatus(),
        getTrainingHistory(),
        getInboxFiles(),
        getRouterStatus(),
      ])
      if (st.status === "fulfilled") {
        setJob(st.value.job)
        setJobStatus(st.value.status)
      }
      if (hist.status === "fulfilled") {
        setAdapters(hist.value.adapters)
      }
      if (inbox.status === "fulfilled") {
        setInboxFiles(inbox.value.files)
      }
      if (rs.status === "fulfilled") {
        setRouter(rs.value)
      }
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    loadAll()
    // poll while a job is running
    pollRef.current = setInterval(async () => {
      try {
        const st = await getTrainingStatus()
        setJob(st.job)
        setJobStatus(st.status)
        if (st.status !== "running") {
          loadAll()
          if (pollRef.current) clearInterval(pollRef.current)
        }
      } catch {
        // ignore
      }
    }, 2000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [loadAll])

  // ── training actions ──────────────────────────────────────────────────────────

  const runAction = async (
    fn: () => Promise<{ ok: boolean; reason?: string; job?: TrainingJobStatus }>
  ) => {
    setActionError("")
    setActionMsg("")
    try {
      const res = await fn()
      if (res.ok) {
        setActionMsg("Job started — training in background.")
        setJob(res.job ?? null)
        setJobStatus("running")
      } else {
        setActionError(res.reason ?? "Could not start job.")
      }
    } catch (e: any) {
      setActionError(e.message ?? "Error")
    }
    loadAll()
  }

  // ── file upload ───────────────────────────────────────────────────────────────

  const handleFiles = async (files: FileList | File[]) => {
    const arr = Array.from(files)
    if (!arr.length) return
    setUploading(true)
    setUploadMsg("")
    let ok = 0
    let fail = 0
    for (const f of arr) {
      try {
        await uploadInboxFile(f)
        ok++
      } catch {
        fail++
      }
    }
    setUploadMsg(`Uploaded ${ok} file${ok !== 1 ? "s" : ""}${fail ? `, ${fail} failed` : ""}.`)
    setUploading(false)
    await loadAll()
  }

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    await handleFiles(e.dataTransfer.files)
  }

  const onFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) await handleFiles(e.target.files)
  }

  // ── styles ────────────────────────────────────────────────────────────────────

  const card = {
    background: "#fff",
    borderRadius: 12,
    border: `1px solid ${colors.border}`,
    padding: 20,
    marginBottom: 20,
    boxShadow: "0 2px 8px rgba(11,78,162,0.07)",
  } satisfies React.CSSProperties

  const sectionTitle = {
    fontSize: 13,
    fontWeight: 700,
    color: colors.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: 1,
    marginBottom: 12,
  } satisfies React.CSSProperties

  const btn = (variant: "primary" | "secondary" | "danger") => ({
    padding: "8px 18px",
    borderRadius: 8,
    border: "none",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    transition: "opacity 0.15s",
    background:
      variant === "primary"
        ? `linear-gradient(90deg, ${colors.primary} 0%, ${colors.accentOrange} 100%)`
        : variant === "danger"
        ? colors.danger
        : colors.border,
    color: variant === "secondary" ? colors.textPrimary : "#fff",
  }) satisfies React.CSSProperties

  const isRunning = jobStatus === "running"

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 20px" }}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, color: colors.textPrimary, margin: 0 }}>
          🧠 Training Room
        </h1>
        <p style={{ color: colors.textMuted, marginTop: 6, fontSize: 14 }}>
          Fine-tune Doctel's local model with your ZETDC documents using LoRA/QLoRA.
          Drop files in the inbox, then trigger a learning cycle.
        </p>
      </div>

      {/* ── Intelligence Router Status ───────────────────────────────────────── */}
      {router && (
        <div style={card}>
          <div style={sectionTitle}>Intelligence Router — Active Tiers</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px" }}>
            {[
              { label: "Tier 1 – Local LoRA Adapter", active: router.local_lora },
              { label: "Tier 2 – Ollama (local)", active: router.ollama },
              { label: "Tier 3 – Cloud Teacher", active: router.cloud_teacher },
              { label: "Tier 4 – Web Search Fallback", active: router.web_search },
            ].map((t) => (
              <div key={t.label} style={{ display: "flex", alignItems: "center", fontSize: 13 }}>
                <TierDot active={t.active} />
                <span style={{ color: t.active ? colors.textPrimary : colors.textMuted }}>
                  {t.label}
                </span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 10, fontSize: 12, color: colors.textMuted }}>
            Active Ollama model: <strong>{router.active_ollama_model}</strong>
            &nbsp;·&nbsp;Free RAM: <strong>{router.free_ram_mb} MB</strong>
          </div>
        </div>
      )}

      {/* ── Current Job Status ───────────────────────────────────────────────── */}
      <div style={card}>
        <div style={sectionTitle}>Current Job</div>
        {job ? (
          <>
            <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 10 }}>
              <StatusPill value={job.status} />
              <span style={{ fontSize: 13, color: colors.textMuted }}>
                Trigger: <strong>{job.trigger}</strong>
              </span>
              {job.started_at && (
                <span style={{ fontSize: 13, color: colors.textMuted }}>
                  Started: <strong>{fmt(job.started_at)}</strong>
                </span>
              )}
            </div>
            {/* Progress bar */}
            <div
              style={{
                background: colors.background,
                borderRadius: 8,
                height: 10,
                overflow: "hidden",
                marginBottom: 8,
              }}
            >
              <div
                style={{
                  height: "100%",
                  borderRadius: 8,
                  width: pct(job.progress),
                  background: `linear-gradient(90deg, ${colors.primary}, ${colors.accentOrange})`,
                  transition: "width 0.5s ease",
                }}
              />
            </div>
            <div style={{ fontSize: 12, color: colors.textMuted }}>{job.message}</div>
            {job.status === "done" && (
              <div style={{ marginTop: 8, fontSize: 13, color: "#2e7d32", fontWeight: 600 }}>
                ✅ {job.result?.samples ?? 0} samples trained · {job.result?.steps ?? 0} steps completed
              </div>
            )}
            {job.status === "error" && (
              <div style={{ marginTop: 8, fontSize: 13, color: colors.danger }}>
                ⚠️ {job.message}
              </div>
            )}
          </>
        ) : (
          <div style={{ color: colors.textMuted, fontSize: 14 }}>No active job. Trigger one below.</div>
        )}
      </div>

      {/* ── Training Controls ────────────────────────────────────────────────── */}
      <div style={card}>
        <div style={sectionTitle}>Learning Cycles</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
          <button
            style={btn("primary")}
            disabled={isRunning}
            onClick={() => runAction(triggerTrainNow)}
            title="train.now() — start immediately"
          >
            ⚡ Train Now
          </button>
          <button
            style={btn("secondary")}
            disabled={isRunning}
            onClick={() => runAction(triggerTrainIdle)}
            title="train.idle() — start only when RAM is available"
          >
            🌙 Train Idle
          </button>
          <button
            style={btn("secondary")}
            disabled={isRunning}
            onClick={() => runAction(() => triggerTrainBatch(batchFolder || undefined))}
            title="train.batch(folder)"
          >
            📦 Batch Train
          </button>
          <button
            style={btn("primary")}
            disabled={distilling || isRunning}
            onClick={async () => {
              setDistilling(true)
              setDistillResult("")
              try {
                const res = await distillFromCloud({ auto_train: true })
                setDistillResult(
                  `Distilled ${res.total_samples} samples (${res.gemini_samples} Gemini, ${res.deepseek_samples} DeepSeek) across ${res.topics_covered} topics${res.training_triggered ? " — training triggered" : ""}`
                )
                loadAll()
              } catch (e: any) {
                setDistillResult(`Distillation failed: ${e.message ?? e}`)
              } finally {
                setDistilling(false)
              }
            }}
            title="Query Gemini/DeepSeek with ZETDC topics and capture training data"
          >
            {distilling ? "⏳ Distilling..." : "🧠 Distill ZETDC Knowledge"}
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="text"
            value={batchFolder}
            onChange={(e) => setBatchFolder(e.target.value)}
            placeholder="Batch folder path (optional – defaults to inbox)"
            style={{
              flex: 1,
              padding: "7px 12px",
              borderRadius: 8,
              border: `1px solid ${colors.border}`,
              fontSize: 13,
              color: colors.textPrimary,
            }}
          />
        </div>
        {actionMsg && (
          <div style={{ marginTop: 10, color: "#2e7d32", fontSize: 13 }}>✅ {actionMsg}</div>
        )}
        {actionError && (
          <div style={{ marginTop: 10, color: colors.danger, fontSize: 13 }}>⚠️ {actionError}</div>
        )}
        {distillResult && (
          <div style={{ marginTop: 10, fontSize: 13, color: distillResult.includes("failed") ? colors.danger : "#2e7d32" }}>
            {distillResult.includes("failed") ? "⚠️" : "✅"} {distillResult}
          </div>
        )}
        <div style={{ marginTop: 12, fontSize: 12, color: colors.textMuted }}>
          <code style={{ fontSize: 11 }}>train.now()</code> · <code style={{ fontSize: 11 }}>train.idle()</code> ·{" "}
          <code style={{ fontSize: 11 }}>train.batch(folder)</code>
        </div>
      </div>

      {/* ── Inbox Drop Zone ──────────────────────────────────────────────────── */}
      <div style={card}>
        <div style={sectionTitle}>Training Inbox</div>
        <div
          ref={dropRef}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          style={{
            border: `2px dashed ${dragging ? colors.primary : colors.border}`,
            borderRadius: 10,
            padding: "28px 20px",
            textAlign: "center",
            background: dragging ? "#E7F0FF" : colors.background,
            transition: "all 0.2s",
            marginBottom: 16,
            cursor: "pointer",
          }}
          onClick={() => document.getElementById("tr-file-input")?.click()}
        >
          <div style={{ fontSize: 32, marginBottom: 8 }}>📂</div>
          <div style={{ fontSize: 14, color: colors.textMuted }}>
            {uploading
              ? "Uploading…"
              : "Drop PDFs, DOCX, TXT, logs here · or click to browse"}
          </div>
          <div style={{ fontSize: 11, color: colors.textMuted, marginTop: 4 }}>
            .pdf · .docx · .txt · .log · .csv · .md
          </div>
          <input
            id="tr-file-input"
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.log,.csv,.md"
            style={{ display: "none" }}
            onChange={onFileInput}
          />
        </div>
        {uploadMsg && (
          <div style={{ marginBottom: 10, color: "#2e7d32", fontSize: 13 }}>✅ {uploadMsg}</div>
        )}
        {inboxFiles.length === 0 ? (
          <div style={{ color: colors.textMuted, fontSize: 13 }}>Inbox is empty.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                <th style={{ textAlign: "left", padding: "6px 8px", color: colors.textMuted, fontWeight: 600 }}>File</th>
                <th style={{ textAlign: "right", padding: "6px 8px", color: colors.textMuted, fontWeight: 600 }}>Size</th>
                <th style={{ textAlign: "center", padding: "6px 8px", color: colors.textMuted, fontWeight: 600 }}>Supported</th>
              </tr>
            </thead>
            <tbody>
              {inboxFiles.map((f) => (
                <tr key={f.name} style={{ borderBottom: `1px solid ${colors.border}22` }}>
                  <td style={{ padding: "6px 8px" }}>{f.name}</td>
                  <td style={{ textAlign: "right", padding: "6px 8px", color: colors.textMuted }}>{f.size_kb} KB</td>
                  <td style={{ textAlign: "center", padding: "6px 8px" }}>
                    {f.supported ? "✅" : "⚠️"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Adapter History ───────────────────────────────────────────────────── */}
      <div style={card}>
        <div style={sectionTitle}>Model State — LoRA Adapters</div>
        {adapters.length === 0 ? (
          <div style={{ color: colors.textMuted, fontSize: 13 }}>
            No adapters trained yet. Run a learning cycle to create the first one.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                {["Adapter ID", "Created", "Samples", "Notes"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "6px 8px",
                      color: colors.textMuted,
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {adapters.map((a) => (
                <tr key={a.id} style={{ borderBottom: `1px solid ${colors.border}22` }}>
                  <td style={{ padding: "6px 8px", fontFamily: "monospace", fontSize: 12 }}>{a.id}</td>
                  <td style={{ padding: "6px 8px", color: colors.textMuted }}>{fmt(a.created_at)}</td>
                  <td style={{ padding: "6px 8px", fontWeight: 600 }}>{a.samples.toLocaleString()}</td>
                  <td style={{ padding: "6px 8px", color: colors.textMuted }}>{a.notes || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Info footer ──────────────────────────────────────────────────────── */}
      <div
        style={{
          fontSize: 12,
          color: colors.textMuted,
          borderTop: `1px solid ${colors.border}`,
          paddingTop: 16,
          lineHeight: 1.7,
        }}
      >
        <strong>Training Room</strong> stores data in{" "}
        <code>C:\LocalAI\training_room\</code>.
        Subfolders: <code>inbox/</code> · <code>batches/</code> · <code>teacher_samples/</code> ·{" "}
        <code>web_samples/</code> · <code>model_state/</code>.
        LoRA training requires <code>peft + transformers + datasets</code> — see{" "}
        <code>requirements.txt</code> for install instructions.
      </div>
    </div>
  )
}
