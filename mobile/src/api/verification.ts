/**
 * Mobile API Verification Test Suite
 * This file contains tests to verify all mobile API connections work correctly with the backend.
 * Run these tests to ensure backend connectivity and data flow.
 */

import * as api from "./client"
import { ChatRequest } from "../types/api"

interface TestResult {
  name: string
  status: "pass" | "fail" | "skip"
  error?: string
  duration: number
}

interface TestResponse {
  passed: number
  failed: number
  skipped: number
  results: TestResult[]
  totalTime: number
}

class ApiVerificationTest {
  private results: TestResult[] = []
  private testStartTime = 0

  async runAllTests(): Promise<TestResponse> {
    const startTime = Date.now()

    // Authentication Tests
    await this.testGetCurrentUser()

    // Document Tests
    await this.testGetMyDocuments()
    await this.testDocumentAnalysis()

    // Chat Tests
    await this.testCreateChatSession()
    await this.testGetChatSessions()
    await this.testGetAvailableModels()

    // Project Tests
    await this.testGetMyProjects()
    await this.testGetProjects()

    // System Tests
    await this.testGetBootstrapStatus()
    await this.testGetIngestStatus()

    const totalTime = Date.now() - startTime
    const passed = this.results.filter((r) => r.status === "pass").length
    const failed = this.results.filter((r) => r.status === "fail").length
    const skipped = this.results.filter((r) => r.status === "skip").length

    return {
      passed,
      failed,
      skipped,
      results: this.results,
      totalTime,
    }
  }

  private async runTest(
    name: string,
    testFn: () => Promise<void>,
    optional = false,
  ): Promise<void> {
    const startTime = Date.now()
    try {
      await testFn()
      this.results.push({
        name,
        status: "pass",
        duration: Date.now() - startTime,
      })
      console.log(`✅ ${name}`)
    } catch (error: any) {
      const status = optional ? "skip" : "fail"
      this.results.push({
        name,
        status,
        error: error?.message || String(error),
        duration: Date.now() - startTime,
      })
      console.log(
        `${status === "fail" ? "❌" : "⏭️"} ${name}: ${error?.message || error}`,
      )
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // Authentication Tests
  // ─────────────────────────────────────────────────────────────────

  private async testGetCurrentUser(): Promise<void> {
    await this.runTest("GET /users/me - Fetch current user", async () => {
      const user = await api.getMe()
      if (!user || !user.email) throw new Error("Invalid user response")
    })
  }

  // ─────────────────────────────────────────────────────────────────
  // Document Tests
  // ─────────────────────────────────────────────────────────────────

  private async testGetMyDocuments(): Promise<void> {
    await this.runTest("GET /api/me/documents - Fetch user documents", async () => {
      const docs = await api.getMyDocuments()
      if (!Array.isArray(docs.documents)) throw new Error("Invalid documents response")
    })
  }

  private async testDocumentAnalysis(): Promise<void> {
    await this.runTest(
      "GET /documents/{id}/analysis - Fetch document analysis",
      async () => {
        const docs = await api.getMyDocuments()
        if (docs.documents.length === 0) throw new Error("No documents available")
        const analysis = await api.getDocumentAnalysis(docs.documents[0].id)
        if (!analysis) throw new Error("Invalid analysis response")
      },
      true,
    )
  }

  // ─────────────────────────────────────────────────────────────────
  // Chat Tests
  // ─────────────────────────────────────────────────────────────────

  private async testCreateChatSession(): Promise<void> {
    await this.runTest("POST /api/chat/sessions - Create chat session", async () => {
      const session = await api.createChatSession(undefined, "global")
      if (!session.session_id) throw new Error("No session ID returned")
    })
  }

  private async testGetChatSessions(): Promise<void> {
    await this.runTest("GET /api/chat/sessions - List chat sessions", async () => {
      const sessions = await api.getChatSessions()
      if (!Array.isArray(sessions.sessions)) throw new Error("Invalid sessions response")
    })
  }

  private async testGetAvailableModels(): Promise<void> {
    await this.runTest("GET /api/models/available - Get available models", async () => {
      const models = await api.getAvailableModels()
      if (!Array.isArray(models.models)) throw new Error("Invalid models response")
    })
  }

  // ─────────────────────────────────────────────────────────────────
  // Project Tests
  // ─────────────────────────────────────────────────────────────────

  private async testGetMyProjects(): Promise<void> {
    await this.runTest("GET /api/me/projects - Get user projects", async () => {
      const projects = await api.getMyProjects()
      if (!Array.isArray(projects.projects)) throw new Error("Invalid projects response")
    })
  }

  private async testGetProjects(): Promise<void> {
    await this.runTest("GET /projects - List all projects", async () => {
      const projects = await api.getProjects()
      if (!Array.isArray(projects.projects)) throw new Error("Invalid projects response")
    })
  }

  // ─────────────────────────────────────────────────────────────────
  // System Tests
  // ─────────────────────────────────────────────────────────────────

  private async testGetBootstrapStatus(): Promise<void> {
    await this.runTest(
      "GET /api/bootstrap/status - Check bootstrap status",
      async () => {
        const status = await api.getBootstrapStatus()
        if (!status) throw new Error("Invalid bootstrap response")
      },
      true,
    )
  }

  private async testGetIngestStatus(): Promise<void> {
    await this.runTest(
      "GET /api/ingest/status - Check ingest status",
      async () => {
        const docs = await api.getMyDocuments()
        if (docs.documents.length === 0) throw new Error("No documents available")
        const status = await api.getIngestStatus(docs.documents[0].id)
        if (!status) throw new Error("Invalid ingest status response")
      },
      true,
    )
  }
}

/**
 * Run the verification tests
 * Usage: await runApiVerification()
 */
export async function runApiVerification(): Promise<TestResponse> {
  const tester = new ApiVerificationTest()
  return await tester.runAllTests()
}

/**
 * Print test results to console
 */
export function printTestResults(response: TestResponse): void {
  console.log("\n" + "=".repeat(60))
  console.log("API Verification Test Results")
  console.log("=".repeat(60))

  console.log(`\n📊 Summary:`)
  console.log(`  ✅ Passed:  ${response.passed}`)
  console.log(`  ❌ Failed:  ${response.failed}`)
  console.log(`  ⏭️  Skipped: ${response.skipped}`)
  console.log(`  ⏱️  Total Time: ${response.totalTime}ms`)

  if (response.failed > 0) {
    console.log(`\n🔴 Failed Tests:`)
    response.results
      .filter((r) => r.status === "fail")
      .forEach((r) => {
        console.log(`  ❌ ${r.name}`)
        console.log(`     Error: ${r.error}`)
        console.log(`     Duration: ${r.duration}ms`)
      })
  }

  if (response.skipped > 0) {
    console.log(`\n🟡 Skipped Tests (Optional):`)
    response.results
      .filter((r) => r.status === "skip")
      .forEach((r) => {
        console.log(`  ⏭️  ${r.name}`)
        console.log(`     Reason: ${r.error}`)
      })
  }

  console.log("\n" + "=".repeat(60) + "\n")
}

/**
 * Export test runner for testing frameworks
 */
export const ApiTests = {
  runAllTests: async () => {
    const response = await runApiVerification()
    printTestResults(response)
    return response
  },
}
