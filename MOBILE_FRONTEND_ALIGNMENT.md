# DocIntel Mobile & Frontend Alignment

## Overview

This document outlines the synchronization between the React Web Frontend and React Native Mobile App to ensure consistent user experience, API contracts, and data handling.

---

## File Structure Alignment

Both applications follow a similar directory structure for consistency:

```
frontend/src/
├── api/               # API client methods
├── assets/            # Images, logos
├── components/        # Reusable UI components
├── constants.ts       # Shared constants (API endpoints, messages)
├── hooks/             # React hooks (useEcNumber, useSyncEvents)
├── pages/             # Full-page components (Frontend only)
├── screens/           # Screen components (Mobile only)
├── theme/
│   └── colors.ts      # Shared ZETDC color palette
├── types/
│   └── api.ts         # TypeScript interfaces
└── App.tsx            # Root component

mobile/src/
├── api/               # API client (same as frontend)
├── assets/            # Images, logos
├── constants.ts       # Shared constants
├── hooks/             # React hooks (platform-adapted)
├── screens/           # Screen components
├── theme/
│   └── colors.ts      # Identical to frontend
├── types/
│   └── api.ts         # Synchronized with frontend
└── App.tsx            # Root component (different from frontend)
```

---

## Synchronized Files

### 1. **Type Definitions** (`types/api.ts`)
**Status:** ✅ Synchronized

Both use identical TypeScript interfaces:
- `DocumentAnalysisResponse` - Analysis results with metadata
- `ChatResponse` - Union type: `ChatAskOkResponse | ChatAskQueuedResponse`
- `LoginResponse` - Auth response with role, email, user_id
- `ModelsAvailableResponse`, `AdminSettingsResponse`, etc.

**Update process:** When backend API changes, update both files identically.

### 2. **Theme / Colors** (`theme/colors.ts`)
**Status:** ✅ Synchronized

Identical ZETDC color palette:
```typescript
export const colors = {
  primary: "#0B4EA2",       // Navy blue
  secondary: "#FDB813",     // Gold
  accentOrange: "#F36F21",  // Orange
  accentRed: "#C1121F",     // Red
  textPrimary: "#0A1628",   // Dark navy
  textMuted: "#4A5E82",     // Mid-blue
  // ... etc
}
```

### 3. **Constants** (`constants.ts`)
**Status:** ✅ New (Synchronized)

Shared constants for API endpoints, error messages, validation rules:
```typescript
export const API_ENDPOINTS = {
  AUTH_LOGIN: "/auth/login",
  DOCUMENTS: "/documents",
  PROJECTS: "/projects",
  // ...
}

export const ERROR_MESSAGES = {
  SESSION_EXPIRED: "Session expired. Please sign in again.",
  // ...
}

export const VALIDATION = {
  ZETDC_EMAIL_DOMAIN: "@zetdc.co.zw",
  MAX_FILE_SIZE_MB: 64,
}
```

### 4. **API Client** (`api/client.ts`)
**Status:** ✅ Synchronized

**Shared methods:**
- `login()`, `requestEmailOtp()`, `verifyEmailOtp()`
- `uploadDocument()`, `getDocumentAnalysis()`
- `getProjects()`, `createProject()`
- `chatWithDocument()`, `getMe()`
- `logout()`, `getAvailableModels()`

**Key differences:**
- Frontend: Uses `localStorage` and Vite's `import.meta.env`
- Mobile: Uses `AsyncStorage` and Expo's `process.env.EXPO_PUBLIC_`
- Error handling is **identical** - both use `ApiError` class

**Async handling:**
- Frontend's `setAuthToken()` is synchronous
- Mobile's `setAuthToken()` is async (platform requirement)
- Both are called appropriately in their contexts

### 5. **React Hooks** (`hooks/useEcNumber.ts`, `hooks/useSyncEvents.ts`)
**Status:** ✅ Platform-adapted (behavior identical)

Hooks are platform-specific but provide identical behavior:

**`useEcNumber`:**
- Frontend: `localStorage`
- Mobile: `AsyncStorage`
- Both provide: `{ ecNumber, setEcNumber }`

**`useSyncEvents`:**
- Both subscribe to `/api/sync/events` SSE stream
- Both handle: `session.logout`, `training.complete`
- Frontend uses Vite env, Mobile uses Expo env

---

## Environment Variables

### Frontend (.env / .env.local)
```bash
VITE_API_BASE_URL=http://localhost:8000
```

### Mobile (app.json / .env)
```bash
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
```

Both default to `http://localhost:8000` if not set.

---

## Component / Screen Structure

### Frontend Pages
- `DocumentViewPage.tsx` - Document analysis + copilot chat
- `MyWorkPage.tsx` - Project/document browser
- `AdminSettingsPage.tsx` - Admin panel
- `TrainingRoomPage.tsx` - Training setup

### Mobile Screens
- `ChatScreen.tsx` - Chat interface with EC history
- `DocumentUploadScreen.tsx` - Document ingestion + metadata

**Alignment note:** Mobile provides a focused subset of desktop features (chat + upload). Full "My Work" and admin functionality can be added screens as needed.

---

## Unification Checklist

- [x] **Type Definitions** - Identical `types/api.ts`
- [x] **API Client** - Synchronized with identical methods
- [x] **Error Handling** - Both use `ApiError` class
- [x] **Color Palette** - Identical `colors.ts`
- [x] **Constants** - New shared `constants.ts` in both
- [x] **Hooks** - Platform-adapted but behavior-identical
- [x] **Auth Flow** - EC + Password, Email OTP (both support)
- [x] **Storage** - Platform-appropriate (localStorage vs AsyncStorage)
- [x] **SSE Events** - Both listen to `/api/sync/events`

---

## Maintenance Guidelines

### When adding new API endpoints:

1. **Backend:** Add endpoint to FastAPI `app/main.py`
2. **Types:** Update both `frontend/src/types/api.ts` AND `mobile/src/types/api.ts`
3. **Constants:** Add to both `frontend/src/constants.ts` AND `mobile/src/constants.ts`
4. **Client:** Add method to both `frontend/src/api/client.ts` AND `mobile/src/api/client.ts`
5. **UI:** Implement platform-specific components/screens as needed

### When updating API responses:

- Always update TypeScript interfaces in BOTH apps
- Test with both web and mobile to ensure compatibility
- Keep error handling consistent between both

### When adding new features:

- Use shared `constants.ts` for messages and endpoints
- Use shared `theme/colors.ts` for styling
- Keep similar component/screen structure for easy maintenance

---

## Cross-Platform Testing

Before deployment:
1. ✅ Test login/logout on both web and mobile
2. ✅ Test document upload and analysis on both
3. ✅ Test chat functionality on both
4. ✅ Verify colors and spacing are consistent
5. ✅ Test with both `localhost` and remote backends
6. ✅ Verify SSE events work (logout, training complete)

---

## Quick Reference

| Feature | Frontend | Mobile | Sync Status |
|---------|----------|--------|-------------|
| Auth Flow | ✅ EC + Email | ✅ EC + Email | ✅ Identical |
| API Client | ✅ Fetch + localStorage | ✅ Fetch + AsyncStorage | ✅ Sync |
| Types | ✅ Complete | ✅ Complete | ✅ Identical |
| Colors | ✅ ZETDC | ✅ ZETDC | ✅ Identical |
| Hooks | ✅ Web-adapted | ✅ RN-adapted | ✅ Behavior-sync |
| Constants | ✅ New | ✅ New | ✅ Identical |
| Error Handling | ✅ ApiError | ✅ ApiError | ✅ Identical |

---

## Support

For questions about alignment, refer to:
- API Types: `{frontend,mobile}/src/types/api.ts`
- Client Methods: `{frontend,mobile}/src/api/client.ts`
- Constants: `{frontend,mobile}/src/constants.ts`
- Theme: `{frontend,mobile}/src/theme/colors.ts`
