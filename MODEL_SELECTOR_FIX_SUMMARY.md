# Model Selector Fix Summary

## Problem Identified

The Task Mapping dropdowns were not loading models correctly because:

1. **Incorrect filtering logic**: The component was filtering models inconsistently
2. **No provider status checking**: Disabled providers were still showing their models
3. **State vs status confusion**: Model state and provider status were not properly differentiated

## Changes Made

### 1. `frontend/src/components/ModelSelector.tsx`

#### Provider Status Filtering (NEW)
```typescript
// Skip providers that are disabled
if (provider.status === "disabled") {
  continue
}
```

#### Model State Filtering (CORRECTED)
```typescript
// Filter by model status: ACTIVE and MAINTENANCE are visible
models = models.filter(m => m.state === "active" || m.state === "maintenance")

// Filter selectable only (exclude MAINTENANCE)
if (selectableOnly) {
  models = models.filter(m => m.state === "active")
}
```

#### Provider Status Display (NEW)
- Added "Provider Offline" badge when provider status is "disconnected" or "error"
- Models from offline providers are visible but disabled

#### Disabled State Logic (CORRECTED)
```typescript
const isProviderOffline = group.provider.status === "disconnected" || group.provider.status === "error"
const isMaintenanceDisabled = model.state === "maintenance" && selectableOnly
const isDisabled = isMaintenanceDisabled || isProviderOffline
```

## Data Flow (Corrected)

```
Database (managed_models table)
    ↓
get_all_providers() - Loads all providers with their models
    ↓
/api/models/v2/catalog - Returns provider-model relationships
    ↓
AdminModelManagementPage - Uses v2GetCatalog()
    ↓
ModelSelector Component
    ↓
    ├─ Filter: provider.status !== "disabled"
    ├─ Filter: model.state IN ("active", "maintenance")
    ├─ Filter: selectableOnly ? model.state === "active" : true
    ├─ Group by provider
    └─ Render with status badges
```

## Status Handling

### Model States
| State | Visible | Selectable | Badge |
|-------|---------|------------|-------|
| `active` | ✅ Yes | ✅ Yes | None |
| `maintenance` | ✅ Yes | ❌ No | "Maintenance" |
| `inactive` | ❌ No | ❌ No | Hidden |
| `retired` | ❌ No | ❌ No | Hidden |

### Provider Status
| Status | Models Visible | Models Selectable | Badge |
|--------|----------------|-------------------|-------|
| `active` | ✅ Yes | ✅ Yes | None |
| `connected` | ✅ Yes | ✅ Yes | None |
| `disconnected` | ✅ Yes | ❌ No | "Provider Offline" |
| `error` | ✅ Yes | ❌ No | "Provider Offline" |
| `disabled` | ❌ No | ❌ No | Hidden entirely |

## Search Functionality

Search works across:
- ✅ Model ID (`model.id`)
- ✅ Model Name (`model.name`)
- ✅ Provider Name (`provider.name`)
- ✅ Provider Vendor (`provider.vendor`)

## Testing Checklist

- [ ] All ACTIVE models appear in dropdown
- [ ] MAINTENANCE models appear but are disabled
- [ ] INACTIVE models are hidden
- [ ] RETIRED models are hidden
- [ ] Models from disabled providers are hidden
- [ ] Models from disconnected providers show "Provider Offline" badge
- [ ] Provider grouping works correctly
- [ ] Search filters across model and provider names
- [ ] Task Mapping uses same model source as New Chat
- [ ] No provider-specific hardcoding exists

## API Endpoints Used

1. **`GET /api/models/v2/catalog`** - Full provider-model catalog (admin only)
2. **`GET /api/models/available`** - Available models for users (includes v2_providers)

Both endpoints return the same provider-model structure from the database.
