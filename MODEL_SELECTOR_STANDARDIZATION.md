# Model Selector Standardization - Implementation Summary

## Issue Identified

The platform had multiple inconsistent model selector implementations:
- **New Chat**: Used `ModelConfigPanel` with flat model list
- **Documents**: Used custom inline model dropdown
- **Analyze**: Used `ProviderGroupedModelSelect` (correct implementation)
- **Task Mapping**: Used `ModelSelector` (correct implementation)

The root cause was that selectors were filtering for only `active` and `maintenance` states, while the database contains models with `installed` and `available` states.

## Database State Values Discovered

| Provider | Models | State |
|----------|--------|-------|
| Ollama | 4 | `installed` |
| OpenCode Zen | 20 | `available` |
| OpenCode Go | 14 | `available` |

## Files Modified

### 1. ModelSelector.tsx (Task Mapping)
**Changes:**
- Updated visible states to include `active`, `installed`, `available`, `maintenance`
- Updated selectable states to include `active`, `installed`, `available`
- Added status badges for "Installed" (green) and "Available" (blue)
- Fixed trigger active state detection

### 2. ProviderGroupedModelSelect.tsx (Documents/Analyze)
**Changes:**
- Updated visible states filter to include all valid states
- Added status badges for "Installed" and "Available" states
- Maintains provider grouping functionality

### 3. ModelContext.tsx (Global State)
**Changes:**
- Updated V2 provider model filtering to include `installed` and `available` states
- Task defaults are already being loaded from Task Mapping

### 4. NewChatPage.tsx
**Changes:**
- Replaced `ModelConfigPanel` with `ProviderGroupedModelSelect`
- Now uses `v2Providers` from ModelContext for provider-grouped display
- Added `capabilityFilter="chat"` to show only chat-capable models
- Uses `taskDefaults` for default model selection (already implemented in ModelContext)

### 5. types/api.ts
**Changes:**
- Updated `V2ModelMetadata.state` documentation to include all valid states
- Updated `isSelectable` and `isVisible` comments

## Valid Model States

| State | Visible | Selectable | Badge Color |
|-------|---------|------------|-------------|
| `active` | ✓ | ✓ | None |
| `installed` | ✓ | ✓ | Green |
| `available` | ✓ | ✓ | Blue |
| `maintenance` | ✓ | ✗ | Yellow |
| `inactive` | ✗ | ✗ | Hidden |
| `retired` | ✗ | ✗ | Hidden |
| `downloading` | ✓ | ✗ | Gray |
| `error` | ✓ | ✗ | Red |

## Remaining Work

### DocumentViewPage.tsx
Currently uses a custom inline dropdown. Needs to be replaced with `ProviderGroupedModelSelect`.

**Current Implementation:** Lines ~2600-2760 contain a complex inline model selector that:
- Groups models as "Cloud/API" vs "Local"
- Shows pull status for Ollama models
- Has capability badges

**Recommended Change:** Replace with `ProviderGroupedModelSelect` while preserving:
- Pull functionality for Ollama models (can be handled separately)
- Selected model display

### ModelConfigPanel.tsx
This component is now deprecated in favor of `ProviderGroupedModelSelect` or `ModelSelector`.

**Recommendation:** Remove usage from:
- NewChatPage.tsx (already done)
- Any other pages using it

## Source of Truth Architecture

```
Providers (DB)
    ↓
Fetched Models (via Fetch Models button)
    ↓
Managed Models (DB: managed_models table)
    ↓
Administrator Status (ACTIVE, MAINTENANCE, etc.)
    ↓
Task Mapping (DB: task_mappings table)
    ↓
UI Dropdowns (via ModelContext)
```

## Default Model Selection Flow

1. **User opens New Chat**
2. `ModelContext.setModelForTask("chat")` is called
3. Priority order:
   - Stored user preference (localStorage)
   - Task Mapping default for "chat"
   - Chat default from defaults
   - First available model

## Testing Checklist

- [ ] Task Mapping shows all providers (Ollama, OpenCode Zen, OpenCode Go)
- [ ] New Chat shows provider-grouped models
- [ ] New Chat default comes from Chat Task Mapping
- [ ] Documents page shows provider-grouped models
- [ ] Analyze page shows provider-grouped models
- [ ] Active models are selectable
- [ ] Installed models are selectable
- [ ] Available models are selectable
- [ ] Maintenance models are visible but disabled
- [ ] Inactive models are hidden
- [ ] Retired models are hidden
- [ ] Search filters models by name, provider, ID
- [ ] Provider status (connected/disconnected) affects model selection

## API Endpoints

- `GET /api/models/v2/catalog` - Full catalog with providers and models
- `GET /api/models/available` - Flat list with task defaults
- `POST /api/models/v2/select` - Auto-route for task

## Shared Components

### ProviderGroupedModelSelect
- Location: `frontend/src/components/ProviderGroupedModelSelect.tsx`
- Props: providers, value, onChange, placeholder, disabled, capabilityFilter, selectableOnly
- Features: Provider grouping, search, capability filtering, status badges

### ModelSelector
- Location: `frontend/src/components/ModelSelector.tsx`
- Props: providers, value, onChange, placeholder, disabled, capabilityFilter, selectableOnly
- Features: Provider grouping, search, keyboard navigation, dark theme

## Migration Guide

To replace a custom model selector:

```tsx
// OLD
<ModelConfigPanel
  selectedModel={model}
  availableModels={models}
  modelCapabilities={modelCapabilities}
  modelLabels={modelLabels}
  onSelect={handleModelChange}
  v2ModelIds={v2ModelIds}
/>

// NEW
<ProviderGroupedModelSelect
  providers={v2Providers}
  value={model}
  onChange={(modelId) => handleModelChange(modelId)}
  placeholder="Select a model..."
  selectableOnly={true}
  capabilityFilter="chat"
/>
```

## Environment Variables

No changes required. The system uses the existing database configuration.
