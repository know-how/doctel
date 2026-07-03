# Mobile Feature Parity - Implementation Checklist

**Overall Status: 28% Feature Parity**  
**Target: 90%+ for MVP Release**

---

## 🎯 CRITICAL FIXES (Blocking Current Use)

### API Endpoint Alignment
- [ ] Fix `POST /documents/{id}/chat` → `POST /api/ask/{documentId}` 
- [ ] Fix `GET /sessions` → `GET /api/chat/sessions`
- [ ] Fix `POST /sessions` → `POST /api/chat/sessions`
- [ ] Implement `GET /api/chat/sessions/{id}/messages` for history loading
- [ ] Add `POST /api/chat/sessions/{id}/model` for model switching
- [ ] Validate response types match frontend expectations

### Message History
- [ ] Load previous messages from session (`getChatMessages()`)
- [ ] Display message history in ChatScreen
- [ ] Implement pagination for messages (load older messages on scroll up)
- [ ] Display sender/timestamp/status for each message
- [ ] Format assistant responses with citations

### Session Management
- [ ] Create ChatSessionsScreen component
- [ ] List all sessions with metadata (title, date, model, project)
- [ ] Add session switching functionality
- [ ] Persist current session selection
- [ ] Filter sessions by project
- [ ] Show session creation time vs last updated

---

## 🔧 HIGH PRIORITY FEATURES

### Rich Content Rendering
- [ ] Add `react-native-markdown-display` for Markdown support
- [ ] Support code block syntax highlighting
- [ ] Implement Mermaid diagram rendering (consider `mermaid-cli` or canvas render)
- [ ] Display embedded charts/images
- [ ] Show citations/sources formatting
- [ ] Handle links in responses

### Model Selection UI
- [ ] Add model selector dropdown to ChatScreen
- [ ] Display available vs installed models
- [ ] Show current model in header
- [ ] Implement model switching mid-conversation
- [ ] Add offline mode indicator
- [ ] Persist model preference to AsyncStorage

### Document Library Screen
- [ ] Create DocumentLibraryScreen component
- [ ] List all uploaded documents
- [ ] Add search/filter by filename
- [ ] Add project filter dropdown
- [ ] Implement bulk select (checkbox)
- [ ] Add bulk actions:
  - [ ] Bulk move to project
  - [ ] Bulk retry ingest
  - [ ] Bulk download
  - [ ] Bulk delete (if enabled)
- [ ] Show document status (ingesting, ready, failed)
- [ ] Show upload date/project name

### Real-Time Updates
- [ ] Implement ingestion progress streaming/polling
- [ ] Show real-time ingest status with percentage
- [ ] Display ETA for ingestion
- [ ] Update status when ingestion completes
- [ ] Handle ingestion failures gracefully

### Better Error Handling
- [ ] Show retry button for failed ingestions
- [ ] Display clear error messages
- [ ] Implement exponential backoff for retries
- [ ] Handle network timeouts gracefully
- [ ] Show connection status indicator

---

## 📊 UI/UX ENHANCEMENTS

### Navigation & Layout
- [ ] Add tab-based navigation (Chat, Documents, Upload, Sessions)
- [ ] Or add drawer navigation with all screens
- [ ] Add screen headers with titles
- [ ] Implement proper screen transitions

### Chat Screen Improvements
- [ ] Add suggested prompts display below input
- [ ] Show document summary at top (executive summary)
- [ ] Display document analysis (topics, entities, sentiment)
- [ ] Add typing indicator while waiting for response
- [ ] Show message status (sending, waiting, success, error)
- [ ] Auto-scroll to bottom on new messages
- [ ] Add message retry button on errors

### Upload Screen Improvements
- [ ] Show recent documents list
- [ ] Display upload history
- [ ] Add progress bar during upload
- [ ] Show success message with document ID
- [ ] Link to open document in chat after upload

### Analytics & Statistics
- [ ] Show project statistics (document count, session count, models)
- [ ] Display personal statistics (total documents, conversations)
- [ ] Show recent activity
- [ ] Display used models

---

## 🎨 COMPONENTS TO CREATE/UPDATE

### New Components
- [ ] `ChatSessionsScreen.tsx` - List and switch sessions
- [ ] `DocumentLibraryScreen.tsx` - Document management
- [ ] `ProjectsScreen.tsx` - Project management (optional)
- [ ] `ModelSelectorDropdown.tsx` - Model selection UI
- [ ] `SessionHistoryModal.tsx` - Session history viewer
- [ ] `IngestionProgressIndicator.tsx` - Real-time progress display
- [ ] `ChatAnalysisCard.tsx` - Document analysis display

### Updated Components
- [ ] `ChatScreen.tsx` - Add history loading, model switching, rich content
- [ ] `DocumentUploadScreen.tsx` - Add library integration
- [ ] `api/client.ts` - Endpoint alignment, new functions

---

## 📡 API FUNCTIONS TO ADD/FIX

### New Functions Required
```typescript
// Chat Sessions
- getChatMessages(sessionId, limit) // Get full history
- createChatSession(documentId?, scope?) // Create session
- listChatSessions(projectId?, limit?) // List all sessions
- setChatSessionModel(sessionId, model) // Switch model in session
- deleteChatSession(sessionId) // Delete session (if supported)

// Chat Messages
- chatGlobally(question, model?) // Global cross-document search
- suggestPrompts(documentId) // Get suggested prompts

// Models
- getAvailableModels() // Already exists, verify response format
- getModelLabels() // Get friendly names
- startModelPull(model) // Download model
- getModelPullStatus(model) // Check download progress

// Documents  
- downloadDocumentFile(documentId) // Download document
- retryIngest(documentId) // Retry failed ingest
- overrideDocumentProject(documentId, projectId) // Move doc

// Projects
- getMyDocuments() // List documents
- getMyProjects() // List projects  
- getProjectAnalysis(projectId) // Get project summary

// History
- getSummaryHistory() // Summary history
- getUiSettings() // Get UI configuration
- getBootstrapStatus() // Bootstrap progress
```

### Functions to Fix
```typescript
// Current (Wrong)
- chatWithDocument(documentId, payload) → POST /documents/{id}/chat

// Should Be
- chatWithDocument(documentId, payload) → POST /api/ask/{documentId}

// Current (Wrong)
- getChatSessions() → GET /sessions
- createChatSession() → POST /sessions

// Should Be
- listChatSessions(projectId?, limit?) → GET /api/chat/sessions
- createChatSession(documentId?, scope?) → POST /api/chat/sessions
```

---

## 🗂️ DATA STRUCTURES TO UPDATE

### ChatMessage Type
```typescript
// Add these fields
interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  status: 'pending' | 'done' | 'failed' // Current status
  citations?: Array<{
    source: string
    page?: number
    text: string
  }>
  created_at: string
  sources?: ChatResponse['sources'] // Add sources for RAG
}
```

### ChatSession Type
```typescript
interface ChatSession {
  session_id: string
  title?: string
  document_id?: string | null
  project_id?: string | null
  model?: string
  scope?: 'document' | 'project' | 'global'
  started_at: string
  updated_at: string
  message_count?: number
}
```

### Document Type (Extended)
```typescript
interface Document {
  id: string
  filename: string
  project_id?: string | null
  project_name?: string
  status: 'uploading' | 'ingesting' | 'ready' | 'failed'
  created_at: string
  download_url?: string
  view_url?: string
  ingest_progress?: number
  error_message?: string
}
```

---

## 🧪 TESTING CHECKLIST

### Unit Tests
- [ ] Test API endpoint alignment
- [ ] Test chat message formatting
- [ ] Test session filtering
- [ ] Test document search/filter

### Integration Tests  
- [ ] Upload → Chat flow works end-to-end
- [ ] Session switching preserves message history
- [ ] Model switching updates subsequent messages
- [ ] Document library filters work correctly

### E2E Tests
- [ ] User can upload, chat, and see history on mobile
- [ ] User can switch between sessions
- [ ] User can search and filter documents
- [ ] Offline mode gracefully degrades

### Manual Testing
- [ ] Test on iOS and Android
- [ ] Test with slow network (throttled)
- [ ] Test with interrupted connections (retry)
- [ ] Test with large documents (>50MB)
- [ ] Test with long conversations (100+ messages)

---

## 📋 DOCUMENTATION UPDATES

- [ ] Update mobile README with feature list
- [ ] Document new screens and workflows
- [ ] Add API endpoint reference
- [ ] Document offline mode behavior
- [ ] Add troubleshooting guide
- [ ] Update MOBILE_BUILD_GUIDE.md with new features

---

## 🎯 SUCCESS CRITERIA

### MVP Release
- [x] Core upload works
- [ ] Core chat works with history
- [ ] Session management UI present
- [ ] Document library present
- [ ] Model selection UI present
- [ ] Endpoint alignment complete
- [ ] Rich content rendering (Markdown minimum)
- [ ] Error handling with retry
- [ ] Feature parity ≥ 70%

### Production Release
- [ ] All critical features complete
- [ ] All high priority features complete
- [ ] Performance optimized
- [ ] Full test coverage
- [ ] Security audit passed
- [ ] Feature parity ≥ 90%

---

## 📌 QUICK REFERENCE: WHAT'S MISSING BY SCREEN

### ChatScreen Needs
- Session history loading from `getChatMessages()`
- Model selector with switching
- Suggested prompts display
- Rich content rendering (Markdown, code, Mermaid)
- Typing indicator
- Better error handling with retry
- Citation formatting
- Proper message status tracking

### DocumentUploadScreen Needs
- Link to document library
- Show recent uploads
- Display upload progress
- Better project selection UX

### NEW: ChatSessionsScreen
- List all sessions
- Search/filter sessions
- Switch between sessions
- Show session metadata

### NEW: DocumentLibraryScreen
- List all documents
- Search by filename
- Filter by project
- Bulk select/operations
- Show document status
- Download/retry buttons

### NEW: ProjectsScreen (Optional)
- List projects
- Show project statistics
- View project documents/sessions

---

## 🚀 DEPLOYMENT NOTES

### Before Release
- [ ] Bump version number
- [ ] Update changelog
- [ ] Test on real devices
- [ ] Run security scan
- [ ] Performance test
- [ ] User acceptance testing

### Release
- [ ] Build APK/IPA
- [ ] Test build on devices
- [ ] Submit to stores
- [ ] Create release notes

### Post-Release
- [ ] Monitor crash reports
- [ ] Track feature usage
- [ ] Collect user feedback
- [ ] Plan phase 2 features

---

**Last Updated:** April 17, 2026  
**Created By:** GitHub Copilot  
**Status:** Ready for Implementation
