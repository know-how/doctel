# Mobile App Feature Parity Analysis

**Last Updated:** April 17, 2026  
**Status:** Comprehensive comparison between Frontend (DocumentViewPage, MyWorkPage, AdminSettingsPage, TrainingRoomPage) and Mobile (ChatScreen, DocumentUploadScreen)

---

## EXECUTIVE SUMMARY

The mobile app currently has **~30% feature parity** with the frontend. Core chat and document upload functionality exists, but most advanced features, UI components, analytics, and management capabilities are missing. The mobile app focuses on essential chat and upload operations, while the frontend provides comprehensive project management, AI training, advanced diagnostics, and admin controls.

---

## 1. PAGES/SCREENS AVAILABLE

### Frontend (4 Pages)
- ✅ **DocumentViewPage** - Main chat/analysis interface for documents
- ✅ **MyWorkPage** - Project management, document library, session history
- ✅ **AdminSettingsPage** - System configuration and audit logs
- ✅ **TrainingRoomPage** - Model training, LoRA adapter management, intelligence router

### Mobile (2 Screens)
- ✅ **ChatScreen** - Document analysis and Q&A (minimal feature subset)
- ✅ **DocumentUploadScreen** - Basic document upload with project selection
- ❌ **MyWorkPage equivalent** - NO project management or document library screen
- ❌ **AdminSettingsPage equivalent** - NO admin/settings screen
- ❌ **TrainingRoomPage equivalent** - NO training room or model management

**Gap**: Mobile is missing 2 out of 4 pages (50% of functionality)

---

## 2. CHAT & MESSAGING FEATURES

### Frontend (DocumentViewPage - Comprehensive)
✅ **Core Chat**
- Document-scoped chat sessions
- Global chat (search across all documents)
- Chat message history with citations
- Optimistic UI updates with status tracking (sending → waiting → success/error)
- Typing indicator animation
- Auto-scroll chat to bottom on new messages
- Message retry on failure
- Rich content rendering (Markdown, code blocks, Mermaid diagrams, embedded charts)

✅ **Chat Sessions**
- Create chat sessions with scope: `document`, `project`, `global`
- List all chat sessions with filtering
- Load conversation history (up to 1000 messages)
- Session persistence in localStorage
- Query-able session history with search

✅ **Model Selection During Chat**
- Real-time model switching mid-conversation
- Model persistence (localStorage)
- Display of model labels/friendly names
- Offline mode detection (installed models only)
- Default model fallback logic

✅ **Suggested Prompts**
- Document-specific suggested prompts
- Global hardcoded suggestions for first-time users
- Dynamic prompt generation via API
- Prompt grouping support

✅ **Chat Context & Scope**
- Document scope: RAG over single document
- Project scope: RAG over all documents in project
- Global scope: Search across all documents + web fallback
- Scope toggle UI (dropdown menu)

### Mobile (ChatScreen - Minimal)
✅ **Core Chat**
- Single chat endpoint: `chatWithDocument()`
- Question/answer with sources
- Optimistic message display
- Loading state
- Basic error handling

❌ **Missing**
- ❌ Global chat (only document-scoped)
- ❌ Chat sessions (no persistent conversation management)
- ❌ Session history listing
- ❌ Message retry UI
- ❌ Rich content rendering (no Markdown, code blocks, Mermaid, charts)
- ❌ Real-time model switching
- ❌ Model selection UI during chat
- ❌ Typing indicator
- ❌ Search scope toggle (project/all)
- ❌ Suggested prompts display
- ❌ Chat citations formatting

---

## 3. DOCUMENT OPERATIONS

### Frontend (MyWorkPage + DocumentViewPage - Comprehensive)
✅ **Document Management**
- List all documents with pagination
- Search documents by filename/content
- Filter by project
- Bulk select documents (checkbox)
- Bulk operations:
  - Move documents to project
  - Retry ingestion
  - Download selected documents
  - Delete (implied)

✅ **Document Upload**
- File upload with metadata:
  - Project assignment (existing or new)
  - Document type
  - Document date
- Metadata file support
- Ingest status monitoring
- Real-time ingestion progress (EventSource streaming)
- Fallback to polling if EventSource unavailable
- Progress percentage + ETA display
- Retry ingestion on failure

✅ **Document Analysis**
- Get document analysis (executive summary, detailed summary, topics, entities, sentiment)
- Document prompts (suggested questions specific to document)
- Reference document selection for multi-doc RAG
- Document-level analytics in sidebar

### Mobile (DocumentUploadScreen - Minimal)
✅ **Document Upload**
- Basic file picker (PDF, DOCX, TXT)
- Project selection (existing or new)
- Document type metadata
- Document date metadata
- Upload status messaging

❌ **Missing**
- ❌ Document list/library
- ❌ Search documents
- ❌ Filter by project
- ❌ Bulk operations
- ❌ Ingest status monitoring
- ❌ Ingestion progress streaming
- ❌ Real-time progress updates
- ❌ Retry ingestion UI
- ❌ Download documents
- ❌ Document analysis on mobile
- ❌ Executive summary display on chat
- ❌ Detailed summary display
- ❌ Reference document selection

---

## 4. PROJECT MANAGEMENT FEATURES

### Frontend (MyWorkPage - Comprehensive)
✅ **Project Management**
- List all projects with metadata (name, role, document count, session count)
- Create new projects during upload
- Assign documents to projects
- Move documents between projects (bulk)
- Project-level analytics:
  - Document count per project
  - Session count per project
  - Models used per project
  - Total size estimates
  - Recent activity timestamps

✅ **Project Analytics**
- Overview stats: Total documents, total conversations, models used
- Per-project breakdown: Docs, sessions, size, models, last activity
- Recent uploads list
- Top projects ranking
- Global session count

✅ **Project Access Control**
- View user role per project (RBAC integration)
- Error messaging for access denied

### Mobile (DocumentUploadScreen - Minimal)
✅ **Basic Project Support**
- Select existing project or create new
- Project name for new projects

❌ **Missing**
- ❌ Project list/library screen
- ❌ Project analytics/dashboard
- ❌ View project documents
- ❌ View project sessions
- ❌ Project metadata display
- ❌ RBAC role display
- ❌ Access control UI

---

## 5. MODEL SELECTION & CONFIGURATION

### Frontend (DocumentViewPage - Comprehensive)
✅ **Model Management**
- List available models
- Display installed (offline) models
- Real-time model switching during chat
- Model persistence to localStorage
- Default model fallback logic
- Model labels/friendly names display
- Offline mode detection
- Model pull (download) functionality with progress

✅ **Model Pull UI**
- Pull modal for downloading models
- Progress bar with percentage
- ETA display
- Attempt counter
- Pull logs/event stream
- Error display
- Automatic polling for pull status
- Success notification with model refresh

✅ **Model Configuration**
- Set model per chat session
- Fallback to default if offline
- Warn user if selected model unavailable

### Mobile (ChatScreen - Minimal)
✅ **Minimal Support**
- Load available models via API call
- Default model selection

❌ **Missing**
- ❌ Model selection UI
- ❌ Model switching during chat
- ❌ Model labels display
- ❌ Offline mode detection
- ❌ Model pull UI
- ❌ Download model progress tracking
- ❌ Model installation management

---

## 6. DIAGRAM & CHART GENERATION

### Frontend (DocumentViewPage - Comprehensive)
✅ **Diagram Generation**
- Flowchart generation via `/api/flowchart/generate`
- Mermaid diagram syntax support
- Text-to-diagram conversion
- Diagram seed from document summary
- Model selection for diagram generation
- Embedded Mermaid rendering in chat

✅ **Chart Building**
- CSV file upload and analysis
- Column detection (numeric vs categorical)
- Chart type selection (bar, line, etc.)
- X-axis and Y-axis configuration
- Chart generation with `/api/charts/build`
- Embedded chart image display in chat
- Chart attached to session for context

### Mobile (ChatScreen - None)
❌ **Completely Missing**
- ❌ Diagram generation
- ❌ Chart building
- ❌ File upload for charts
- ❌ Mermaid rendering
- ❌ Chart display

**Impact**: Mobile users cannot generate or view visual representations.

---

## 7. HISTORY & SESSION FEATURES

### Frontend (MyWorkPage + DocumentViewPage - Comprehensive)
✅ **Session History**
- List all chat sessions with metadata
- Sessions grouped by project
- Session titles/descriptions
- Last updated timestamp
- Model used per session
- Document associations
- Session count by project

✅ **Summary History**
- Retrieve user summary history across documents
- Document summaries linked to entries
- Used for context and reference

✅ **Session Browsing**
- Modal to view all sessions
- Search/filter sessions
- Load session by ID
- Restore full conversation history
- See all messages in session

### Mobile (ChatScreen - Minimal)
✅ **Minimal Support**
- Load user history via `getUserHistory()`
- Load summary history via `getSummaryHistory()`
- Display in chat (read-only)

❌ **Missing**
- ❌ Session list/management screen
- ❌ Switch between sessions
- ❌ Session creation UI
- ❌ Session history modal
- ❌ Persistent session storage
- ❌ Session-scoped chat context

---

## 8. UI/UX COMPONENTS & PATTERNS

### Frontend (DocumentViewPage + MyWorkPage + AdminSettingsPage)
✅ **Modals & Overlays**
- Model selection dropdown with click-outside detection
- Chat history modal with search
- Diagram generation modal
- Chart builder modal
- Model pull progress modal
- Metadata editor modal
- Reference document selector modal
- Intro animation overlay

✅ **Dropdowns & Menus**
- Model selector (with labels)
- Scope toggle (project/all)
- Chart type selector
- Project selector
- Bulk action selector (move to project, retry, download)
- Settings category sidebar navigation

✅ **Panels & Sidebars**
- Left sidebar for navigation
- Right sidebar for project analytics
- Collapsible settings category panels
- Admin settings tabs (8 categories)

✅ **Forms & Inputs**
- Search boxes with debouncing
- Text input for prompts
- File picker (drag-drop + click)
- Metadata inputs (type, date, project)
- JSON editor for settings
- Checkbox toggles
- Radio buttons (new/existing project)

✅ **Status Indicators**
- Typing indicator (animated dots)
- Loading spinners
- Progress bars
- Status pills (running, done, error, pending)
- Error messages with colors
- Success messages
- Info tooltips
- UI status badges

✅ **Lists & Tables**
- Document list with checkboxes
- Session list with metadata
- Project list with cards
- Analytics cards
- Audit logs table
- Adapter records table

✅ **Rich Content Display**
- Markdown rendering
- Code block syntax highlighting
- Mermaid diagram rendering
- Chart image display
- Citation formatting
- Source links
- Embedded images

✅ **Navigation**
- Tab navigation (Copilot, My Work, Admin, Training)
- Breadcrumb trails (implied)
- Page transitions
- Modal stacking

### Mobile (ChatScreen + DocumentUploadScreen - Minimal)
✅ **Basic Components**
- Text inputs (question, project name, etc.)
- Pressable buttons
- ScrollView
- ActivityIndicator
- Chip selectors (project selection)

❌ **Missing**
- ❌ Modal dialogs (except basic feedback)
- ❌ Dropdown menus
- ❌ Tab navigation
- ❌ Sidebar navigation
- ❌ Advanced form controls
- ❌ Search/filter UI
- ❌ Bulk action UI
- ❌ Status pills/badges
- ❌ Analytics cards
- ❌ Rich content rendering (Markdown, code blocks, Mermaid, charts)
- ❌ Drag-drop file upload
- ❌ Progress bars/indicators
- ❌ Typed lists/tables
- ❌ Checkbox multi-select
- ❌ Modal stacking

---

## 9. API ENDPOINTS BEING CALLED

### Frontend API Calls (api/client.ts)
✅ **Authentication**
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/email/request`
- `POST /auth/email/verify`
- `GET /users/me`

✅ **Documents**
- `POST /documents` (upload)
- `GET /documents/{id}/analysis`
- `GET /documents/{id}/prompts`
- `POST /documents/{id}/chat` (implied)
- `GET /documents/{id}/file` (download)
- `GET /api/ingest/status`
- `GET /api/ingest/stream` (EventSource)
- `POST /api/ingest/retry`
- `PUT /api/documents/{id}/project`
- `GET /api/documents/{id}/download`

✅ **Chat**
- `POST /api/ask/{documentId}` (document-scoped chat)
- `POST /api/ask` (global chat)
- `POST /api/chat/sessions` (create)
- `GET /api/chat/sessions/{id}/messages`
- `POST /api/chat/sessions/{id}/model` (set model)
- `GET /api/chat/sessions` (list)

✅ **Projects**
- `POST /projects` (create)
- `GET /projects` (list)
- `GET /projects/{id}/analysis`
- `GET /api/me/projects`
- `GET /api/me/documents`

✅ **Models**
- `GET /api/models/available`
- `POST /api/models/pull` (start download)
- `GET /api/models/pull/status/{model}`
- `GET /api/models/labels`

✅ **Diagrams & Charts**
- `POST /api/flowchart/generate`
- `POST /api/charts/analyze` (CSV analysis)
- `POST /api/charts/build` (chart generation)
- `GET /api/charts/{id}` (retrieve chart)

✅ **Admin & Settings**
- `GET /admin/settings`
- `PATCH /admin/settings`
- `POST /admin/settings/test`
- `POST /admin/settings/backup`
- `GET /admin/settings/audit`
- `GET /api/settings/ui`

✅ **Bootstrap & Status**
- `GET /api/bootstrap/status`

✅ **History**
- `GET /users/me/summary-history`

### Mobile API Calls (api/client.ts)
✅ **Authentication** (Same as frontend)
- `POST /auth/login`
- `POST /auth/email/request`
- `POST /auth/email/verify`
- `POST /auth/logout`
- `GET /users/me`

✅ **Documents**
- `POST /documents` (upload)
- `GET /documents/{id}/prompts`
- `GET /documents/{id}/analysis`
- `GET /api/ingest/status`

✅ **Chat**
- `POST /documents/{id}/chat` (endpoint differs from frontend!)
- `GET /users/me/history`
- `GET /users/me/summary-history`

✅ **Projects**
- `POST /projects` (create)
- `GET /projects` (list)
- `GET /api/me/documents`

✅ **Models**
- `GET /api/models/available`

✅ **Sessions** (Different from frontend)
- `GET /sessions` (list - different path!)
- `POST /sessions` (create - different path!)

❌ **Missing from Mobile**
- ❌ `POST /api/ask/{documentId}` (no document scoped chat)
- ❌ `POST /api/ask` (no global chat)
- ❌ `GET /api/chat/sessions/{id}/messages` (no message history loading)
- ❌ `POST /api/chat/sessions/{id}/model` (no model switching)
- ❌ `GET /api/models/pull` (no model download)
- ❌ `GET /api/models/pull/status/{model}`
- ❌ `GET /api/models/labels`
- ❌ `POST /api/flowchart/generate`
- ❌ `POST /api/charts/analyze`
- ❌ `POST /api/charts/build`
- ❌ `/admin/*` (all admin endpoints)
- ❌ `GET /api/settings/ui`
- ❌ `GET /api/bootstrap/status`
- ❌ `POST /api/documents/{id}/project` (move between projects)
- ❌ `GET /api/documents/{id}/download` (bulk download)

### API Endpoint Discrepancies

| Feature | Frontend Endpoint | Mobile Endpoint | Status |
|---------|-------------------|-----------------|--------|
| Chat with document | `POST /api/ask/{documentId}` | `POST /documents/{id}/chat` | ⚠️ Different |
| List sessions | `GET /api/chat/sessions` | `GET /sessions` | ⚠️ Different |
| Create session | `POST /api/chat/sessions` | `POST /sessions` | ⚠️ Different |
| Get messages | `GET /api/chat/sessions/{id}/messages` | ❌ Not implemented | ❌ Missing |

---

## 10. KEY UI/UX PATTERNS USED

### Frontend Patterns
✅ **Modal-First Design**
- Multiple concurrent modals (history, model pull, diagram, chart builder)
- Click-outside detection for dismissal
- Modal stacking with appropriate z-index

✅ **Real-Time Updates**
- EventSource streaming (ingestion status, model pull)
- Polling with adaptive intervals (configurable)
- Background polling with exponential backoff
- Progress tracking with ETA

✅ **Optimistic UI**
- Show user messages immediately
- Show typing indicator while waiting
- Replace with actual response on success
- Show error state on failure with retry option

✅ **Rich Content Rendering**
- Markdown parsing with syntax highlighting
- Embedded Mermaid diagrams
- Inline chart images
- Citation formatting with source links

✅ **Persistent State**
- localStorage for auth token
- localStorage for model preference
- localStorage for chat session IDs
- BroadcastChannel for cross-tab sync

✅ **Accessibility Patterns**
- Form validation with error display
- Loading states with disabled controls
- Keyboard navigation (implied)
- Color-coded status indicators

✅ **Analytics Dashboard**
- Card-based layout
- Stat counters
- Project-level breakdown
- Session grouping by project
- Recent items lists

### Mobile Patterns
✅ **Simple List-Based**
- ScrollView for content areas
- Chip selectors for choices
- Text input for search/entry
- Pressable buttons for actions

❌ **Missing Advanced Patterns**
- ❌ No modals (except native alerts)
- ❌ No real-time streaming
- ❌ Limited optimistic updates
- ❌ No rich content rendering
- ❌ No analytics dashboard
- ❌ No advanced state persistence
- ❌ Limited error recovery UI

---

## FEATURE PARITY SUMMARY TABLE

| Category | Frontend | Mobile | Coverage | Priority |
|----------|----------|--------|----------|----------|
| **Pages** | 4 | 2 | 50% | HIGH |
| **Chat Features** | 10+ | 1 | 10% | HIGH |
| **Chat Sessions** | Full | None | 0% | HIGH |
| **Document Ops** | 8+ | 1 | 12% | HIGH |
| **Project Management** | 6+ | 1 | 16% | MEDIUM |
| **Model Selection** | Full | None | 0% | MEDIUM |
| **Diagrams/Charts** | Both | Neither | 0% | LOW |
| **History/Sessions** | Full | Partial | 40% | MEDIUM |
| **UI Components** | 15+ | 5 | 33% | HIGH |
| **API Endpoints** | 35+ | 12 | 34% | CRITICAL |

**Overall Feature Parity: ~28%**

---

## MOBILE FEATURES MISSING - DETAILED ACTION LIST

### 🔴 CRITICAL (Must Have)
1. **Chat Session Management**
   - Implement session list screen
   - Add session creation UI
   - Load conversation history from session
   - Add session switching capability
   - Display session metadata (title, date, model)

2. **Document Library**
   - Create MyDocuments screen
   - List all uploaded documents
   - Search/filter documents
   - Add project filter
   - Implement bulk select
   - Add bulk download
   - Add bulk retry ingest

3. **API Endpoint Alignment**
   - Change `POST /documents/{id}/chat` to `POST /api/ask/{documentId}` (frontend compatible)
   - Change `GET /sessions` to `GET /api/chat/sessions`
   - Change `POST /sessions` to `POST /api/chat/sessions`
   - Implement `/api/chat/sessions/{id}/messages`

4. **Message History Loading**
   - Load previous messages from session
   - Display full conversation history
   - Implement message pagination

5. **Rich Content Rendering**
   - Add Markdown parser (react-markdown or similar)
   - Add Mermaid diagram renderer
   - Support code block syntax highlighting
   - Embed chart images

### 🟡 HIGH PRIORITY (Should Have)
6. **Model Selection UI**
   - Add model selector dropdown
   - Implement model switching during chat
   - Display model labels
   - Show installed vs available models
   - Add offline mode indicator

7. **Improved Analytics**
   - Show document analysis (executive summary, topics, entities)
   - Display ingest status and progress
   - Show citation sources
   - Display sentiment indicators

8. **Advanced Chat Features**
   - Global chat mode (cross-document search)
   - Project-scoped chat
   - Suggested prompts display
   - Real-time typing indicator
   - Message retry UI

9. **Better Error Handling**
   - Retry ingestion button
   - Network error messages with retry
   - Auth expiration handling with re-login
   - Ingestion failure recovery

### 🟢 MEDIUM PRIORITY (Nice to Have)
10. **Project Management**
    - Create project management screen
    - Add project analytics
    - Show project documents
    - Display project-level statistics

11. **Diagram & Chart Features**
    - Flowchart generation
    - CSV chart builder
    - Chart type selection
    - Embedded diagram rendering

12. **Advanced Settings**
    - Admin settings screen
    - Model pull/download UI
    - Training room interface
    - Audit logs view

---

## IMPLEMENTATION ROADMAP

### Phase 1: Core Features (Week 1-2)
- [x] API endpoint alignment
- [ ] Chat session management screen
- [ ] Session history loading
- [ ] Document library screen
- [ ] Document search & filter

### Phase 2: UI/UX Polish (Week 2-3)
- [ ] Model selection UI
- [ ] Rich content rendering (Markdown, code)
- [ ] Mermaid diagram support
- [ ] Better error messages
- [ ] Loading states & progress

### Phase 3: Advanced Features (Week 3-4)
- [ ] Global chat mode
- [ ] Project management screen
- [ ] Admin settings screen (if needed)
- [ ] Document analysis display
- [ ] Chart generation

### Phase 4: Optimization & Testing (Week 4-5)
- [ ] Performance tuning
- [ ] Offline mode testing
- [ ] Cross-platform testing (iOS/Android)
- [ ] Accessibility review
- [ ] User testing

---

## KEY UI/UX IMPROVEMENTS FOR MOBILE

### Before (Current State)
```
Screen 1: Chat (limited - no history, no model selection)
Screen 2: Upload (basic - no library, no bulk operations)
```

### After (Full Parity)
```
Screen 1: Chat (with history, session switching, model selection, rich content)
Screen 2: Upload (with library, search, filter, bulk ops)
Screen 3: Sessions (history, metadata, grouping by project)
Screen 4: Documents (library, search, filter, download, retry)
Screen 5: Projects (management, analytics, statistics)
Screen 6: Settings (if admin features needed)
```

### UI Component Updates
- Add **modal dialogs** for session history, model selection
- Add **dropdown menus** for model/scope/project selection
- Add **search bars** with filters
- Add **chip/tag components** for bulk selection
- Add **progress bars** for ingestion tracking
- Add **status badges** for document/session status
- Add **analytics cards** for project statistics
- Add **syntax highlighting** for code blocks
- Add **Mermaid renderer** for diagrams

---

## NOTES FOR MOBILE DEVELOPERS

### TypeScript Alignment
- Update type imports in mobile `api/client.ts` to match frontend
- Ensure `ChatResponse` type includes all fields from frontend
- Use discriminated unions for message types (user, assistant, system)

### State Management
- Consider adding Redux/Zustand for session state
- Implement localStorage-like AsyncStorage for persistence
- Add BroadcastChannel equivalent for mobile (possibly using background processes)

### Performance Considerations
- Virtualize long lists (sessions, documents, messages)
- Implement pagination for document library
- Cache document analysis results
- Use lazy loading for attachments/images

### Security
- Use HTTP-only storage for auth token
- Validate API responses
- Implement certificate pinning for production
- Clear sensitive data on logout

### Testing
- Unit tests for API client functions
- Integration tests for chat flow
- E2E tests for upload + chat workflow
- Mock API responses for offline testing

---

## REFERENCE LINKS
- Frontend pages: `/frontend/src/pages/`
- Frontend API: `/frontend/src/api/client.ts`
- Mobile screens: `/mobile/src/screens/`
- Mobile API: `/mobile/src/api/client.ts`
- Frontend types: `/frontend/src/types/api.ts`
- Mobile types: `/mobile/src/types/api.ts`
