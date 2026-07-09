# Model Selector Redesign Summary

## Overview
Redesigned all model selection dropdowns across the platform to use the database as the single source of truth. Only models that have been fetched, saved, and actively managed by the administrator are now available for selection.

## Core Principle

**A model becomes available ONLY when:**
1. ✅ It exists on a provider
2. ✅ It has been fetched from that provider
3. ✅ It has been saved in the database (`managed_models` table)
4. ✅ Administrator has assigned status `ACTIVE` or `MAINTENANCE`

## Files Modified

### Backend Changes

#### `app/routers/models.py`
**Complete rewrite of `/api/models/available` endpoint:**

**Before:**
- Mixed hardcoded cloud provider models (Gemini, DeepSeek, OpenCode, HuggingFace)
- Merged legacy `settings.available_models`
- Included models from various service files

**After:**
- **ONLY** returns database-managed models from `managed_models` table
- Filters by status: `ACTIVE` (selectable) and `MAINTENANCE` (visible but disabled)
- Groups models by provider in the response
- Removes all hardcoded cloud service model injection
- Ollama models still included for backward compatibility (until imported to DB)

```python
# SOURCE OF TRUTH: Database-managed models ONLY
v2_providers = await get_all_providers(db)
db_models = await get_available_models(db, include_maintenance=True)

# Only ACTIVE models are "selectable"
selectable_models = [m for m in db_models if m.is_selectable]
visible_models = [m for m in db_models if m.is_visible]  # ACTIVE + MAINTENANCE
```

### Frontend Changes

#### `frontend/src/components/ProviderGroupedModelSelect.tsx` (NEW)
A new, reusable model selector component with:

**Features:**
- ✅ **Provider Grouping**: Models organized by provider (Google, OpenAI, Ollama, etc.)
- ✅ **Search**: Real-time filtering by model name, ID, or description
- ✅ **Status Indicators**: Shows ACTIVE vs MAINTENANCE status
- ✅ **Capability Filtering**: Filter by task capability (chat, vision, code, etc.)
- ✅ **Selectable Only Mode**: Option to exclude MAINTENANCE models
- ✅ **Local Models Support**: Includes Ollama models in separate group
- ✅ **Responsive Design**: Clean dropdown with proper z-index handling

**Props:**
```typescript
interface ProviderGroupedModelSelectProps {
  providers: V2Provider[]           // Array of providers with models
  value: string                     // Currently selected model ID
  onChange: (modelId, model, provider) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  capabilityFilter?: string         // Filter by capability
  selectableOnly?: boolean          // Only ACTIVE models (exclude MAINTENANCE)
  includeLocalModels?: boolean      // Include Ollama models
  localModels?: string[]            // Local Ollama model list
}
```

#### `frontend/src/components/index.ts`
Added export for `ProviderGroupedModelSelect`.

#### `frontend/src/pages/AdminModelManagementPage.tsx`
**Task Mapping Section Updated:**
- Replaced native `<select>` dropdown with `ProviderGroupedModelSelect`
- Now uses `selectableOnly={true}` to show only ACTIVE models for task assignment
- Added helpful text: "Only ACTIVE models are available for task mapping"

```tsx
<ProviderGroupedModelSelect
  providers={providers}
  value={current.modelId || ""}
  onChange={(modelId, model, provider) => {
    handleSetTaskMapping(taskType, provider?.id || "", modelId)
  }}
  placeholder="— Auto (recommended) —"
  selectableOnly={true}
  includeLocalModels={true}
/>
```

#### `frontend/src/pages/AnalyzeChatPage.tsx`
**Model Selector Updated:**
- Replaced custom dropdown with `ProviderGroupedModelSelect`
- Added `v2Providers` to `useModel()` destructuring
- Simplified `handleModelChange` function

#### `frontend/src/context/ModelContext.tsx`
Already provides `v2Providers` which is consumed by the new component.

## API Response Structure

### `GET /api/models/available`

**Response now includes enriched model details:**
```json
{
  "installed": ["model-id-1", "model-id-2"],
  "available": ["model-id-1", "model-id-2", "model-id-3"],
  "offline": false,
  "default_model": "model-id-1",
  "models": [
    {
      "name": "model-id-1",
      "provider_id": "openai",
      "size": 0,
      "ready": true,
      "capabilities": ["chat", "vision"],
      "status": "active",
      "is_selectable": true,
      "is_visible": true,
      "is_disabled": false
    }
  ],
  "v2_providers": [
    {
      "id": "openai",
      "name": "OpenAI",
      "models": [
        {
          "id": "gpt-4",
          "name": "GPT-4",
          "state": "active"
        }
      ]
    }
  ]
}
```

## Status Definitions

| Status | Visible in Dropdown | Selectable | Use Case |
|--------|---------------------|------------|----------|
| `ACTIVE` | ✅ Yes | ✅ Yes | Fully operational models |
| `MAINTENANCE` | ✅ Yes | ❌ No | Temporarily disabled with warning |
| `INACTIVE` | ❌ No | ❌ No | Hidden from all selectors |
| `RETIRED` | ❌ No | ❌ No | Permanently removed |

## Remaining Pages to Update

The following pages still use the old model selection pattern and should be updated:

1. **`DocumentViewPage.tsx`** - Has complex model selector with pull/download functionality
2. **`NewChatPage.tsx`** - Uses `ModelConfigPanel` component
3. **`AnalyzeClassificationPage.tsx`** - Simple model selector
4. **`AdminModelsPage.tsx`** - Model management page
5. **`AdminProvidersPage.tsx`** - Provider management

## Migration Guide for Developers

### Replacing Old Selectors

**Old Pattern:**
```tsx
const { availableModels, selectedModel, setSelectedModel } = useModel()

<select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}>
  {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
</select>
```

**New Pattern:**
```tsx
const { v2Providers, selectedModel, setSelectedModel } = useModel()

<ProviderGroupedModelSelect
  providers={v2Providers}
  value={selectedModel}
  onChange={(modelId) => setSelectedModel(modelId)}
  selectableOnly={true}  // Or false to show MAINTENANCE models
/>
```

## Testing Checklist

- [ ] Verify only ACTIVE models appear in task mapping dropdowns
- [ ] Verify MAINTENANCE models show as disabled with warning
- [ ] Verify INACTIVE/RETIRED models are completely hidden
- [ ] Verify search functionality works across all model names
- [ ] Verify provider grouping displays correctly
- [ ] Verify Ollama models appear in "Local" group
- [ ] Verify model selection persists across page navigation
- [ ] Verify API response time is acceptable (< 500ms)

## Security Considerations

1. **RBAC**: The backend still respects role-based access control for model visibility
2. **Department Restrictions**: Department-scoped models are filtered at the API level
3. **Audit Trail**: All model status changes are logged via the audit system

## Future Enhancements

1. Add "Recently Used" section to dropdown
2. Add capability icons inline with model names
3. Add provider status indicators (healthy/degraded/unhealthy)
4. Add "Favorite Models" feature for users
