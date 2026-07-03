# 🎨 Modern Design System - Quick Reference Card

## Import What You Need

```typescript
// Theme tokens
import { theme } from "@/theme/theme"

// Utility styles
import { utilityStyles } from "@/theme/utilityStyles"

// Animations
import { animations } from "@/theme/animations"

// Components
import { Button, Card, Input, Badge, GlassPanel, Divider, Spinner, Text } from "@/components/styled"
```

## Components Cheat Sheet

### Button
```typescript
<Button variant="primary|secondary|ghost|danger" size="sm|md|lg" loading>Label</Button>
```
- Variants: primary (default), secondary, ghost, danger
- Sizes: sm, md, lg
- States: loading, disabled
- Hover effects: Built-in glow and lift

### Card
```typescript
<Card hover={true}>Content</Card>
```
- Modern glassmorphism effect
- Hover effect enabled by default
- Perfect for content containers
- Built-in shadows and borders

### Input
```typescript
<Input label="Label" placeholder="Hint" error="Error message" type="email" />
```
- Label support
- Error state with color change
- Smooth focus transitions
- Auto-managed focus state

### Badge
```typescript
<Badge variant="primary|success|warning|error|secondary">Status</Badge>
```
- 5 color variants
- Gradient backgrounds
- Perfect for tags and labels

### Text
```typescript
<Text variant="heading1|heading2|heading3|heading4|heading5|bodyLarge|body|bodySmall|caption" color="primary|secondary|error|gray">
  Content
</Text>
```
- 9 typography variants
- Multiple colors
- Semantic HTML support (h1-h5)

### GlassPanel
```typescript
<GlassPanel intensity="light|medium|dark">Content</GlassPanel>
```
- Glassmorphism effect
- 3 intensity levels
- Modern backdrop blur

### Spinner
```typescript
<Spinner size="sm|md|lg" color="primary|secondary|white" />
```
- 3 sizes
- 3 color options
- Smooth rotation animation

### Divider
```typescript
<Divider variant="solid|dashed|dotted" color="primary|secondary|muted" margin="sm|md|lg" />
```
- Multiple line styles
- Color options
- Customizable spacing

## Theme Tokens

### Colors
```typescript
theme.colors.primary[50-950]        // Blue palette
theme.colors.secondary[50-950]      // Cyan palette
theme.colors.accent[50-950]         // Orange palette
theme.colors.success[50-950]        // Green
theme.colors.warning[50-950]        // Amber
theme.colors.error[50-950]          // Red
theme.colors.gray[50-950]           // Grayscale
```

### Typography
```typescript
theme.typography.fontSize           // xs, sm, base, lg, xl, 2xl, 3xl, 4xl, 5xl, 6xl
theme.typography.fontWeight         // thin, extralight, light, normal, medium, semibold, bold, extrabold, black
theme.typography.fontFamily.sans    // System font stack
theme.typography.fontFamily.mono    // Monospace fonts
```

### Spacing
```typescript
theme.spacing[0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24]
// 0px, 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px, 48px, 64px, 80px, 96px
```

### Border Radius
```typescript
theme.borderRadius[none, xs, sm, base, md, lg, xl, 2xl, 3xl, full]
// 0px, 4px, 6px, 8px, 12px, 16px, 20px, 24px, 32px, 9999px
```

### Shadows
```typescript
theme.shadows.xs        // Subtle shadow
theme.shadows.md        // Medium shadow
theme.shadows.lg        // Large shadow
theme.shadows.glow      // Glow effect
theme.shadows.glowCyan  // Cyan glow
```

### Gradients
```typescript
theme.gradients.primary      // Blue gradient
theme.gradients.secondary    // Cyan gradient
theme.gradients.accent       // Orange gradient
theme.gradients.darkBg       // Dark background gradient
theme.gradients.glass        // Glass effect gradient
```

### Transitions
```typescript
theme.transitions.duration.fast      // 150ms
theme.transitions.duration.normal    // 200ms
theme.transitions.duration.slow      // 300ms
theme.transitions.timing.easeOut     // cubic-bezier(0, 0, 0.2, 1)
```

## Utility Styles

### Layout Utilities
```typescript
utilityStyles.flexCenter        // flex, centered
utilityStyles.flexBetween       // flex, space-between
utilityStyles.flexCol           // flex column
utilityStyles.flexColCenter     // flex column, centered
utilityStyles.grid              // display: grid
utilityStyles.gridCol2          // 2 columns
utilityStyles.gridCol3          // 3 columns
```

### Glass Effects
```typescript
utilityStyles.glass        // Medium glass
utilityStyles.glassLight   // Light glass
utilityStyles.glassDark    // Dark glass
```

### Card Styling
```typescript
utilityStyles.card         // Card base styles
utilityStyles.cardHover    // Hover state
```

### Button Styling
```typescript
utilityStyles.button        // Base button
utilityStyles.buttonPrimary // Primary variant
utilityStyles.buttonSecondary // Secondary variant
utilityStyles.buttonGhost   // Ghost variant
```

### Text Styling
```typescript
utilityStyles.heading1      // h1 style
utilityStyles.heading2      // h2 style
utilityStyles.body          // Regular text
utilityStyles.bodySmall     // Small text
utilityStyles.caption       // Caption text
```

## Common Patterns

### Card with Content
```typescript
<Card>
  <Text variant="heading3">Title</Text>
  <Text variant="body">Description</Text>
  <Button variant="primary">Action</Button>
</Card>
```

### Form Container
```typescript
<Card style={{ maxWidth: 400 }}>
  <Input label="Username" placeholder="john_doe" />
  <Input label="Email" type="email" placeholder="john@example.com" />
  <Button variant="primary" style={{ width: "100%" }}>Submit</Button>
</Card>
```

### Header Section
```typescript
<div style={{ marginBottom: theme.spacing.8 }}>
  <Text variant="heading2" style={{ marginBottom: theme.spacing.2 }}>Section Title</Text>
  <Text variant="bodySmall" color={400}>Subtitle or description</Text>
</div>
```

### Loading State
```typescript
<Button loading={isLoading} onClick={handleSubmit}>
  {isLoading ? "Loading..." : "Submit"}
</Button>
```

### Grid Layout
```typescript
<div style={{
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
  gap: theme.spacing.6,
}}>
  <Card>Item 1</Card>
  <Card>Item 2</Card>
  <Card>Item 3</Card>
</div>
```

### Status Badge
```typescript
<div style={{ display: "flex", gap: theme.spacing.2 }}>
  <Badge variant="success">Active</Badge>
  <Badge variant="warning">Pending</Badge>
  <Badge variant="error">Failed</Badge>
</div>
```

## Animation Patterns

### Fade In
```typescript
style={{
  ...animations.fadeIn,
}}
```

### Slide Up
```typescript
style={{
  ...animations.slideInUp,
}}
```

### Smooth Transitions
```typescript
style={{
  ...utilityStyles.card,
  ...animations.hoverTransition,
}}
```

### Staggered Animation
```typescript
style={{
  animation: `slideInUp 300ms ease-out ${index * 100}ms both`,
}}
```

## Style Override Pattern

```typescript
// Combine with custom properties
style={{
  ...utilityStyles.card,
  maxWidth: 500,
  // Override as needed
  padding: theme.spacing.8,
}}

// Or use conditionals
style={{
  ...utilityStyles.card,
  ...(isSelected && { border: `2px solid ${theme.colors.primary[500]}` }),
}}
```

## Colors at a Glance

| Use | Color | Token |
|-----|-------|-------|
| Primary Action | Blue | `theme.colors.primary[500]` = #5B88FF |
| Secondary Action | Cyan | `theme.colors.secondary[500]` = #1FE7FF |
| Success | Green | `theme.colors.success[500]` = #22C55E |
| Warning | Amber | `theme.colors.warning[500]` = #F59E0B |
| Error | Red | `theme.colors.error[500]` = #EF4444 |
| Text Primary | White | `#FFFFFF` |
| Text Secondary | Gray | `theme.colors.gray[300]` = #D1D5DB |
| Background | Dark | `#0F1117` |

## Don'ts ❌

- ❌ Don't hardcode colors: Use `theme.colors.*`
- ❌ Don't hardcode spacing: Use `theme.spacing.*`
- ❌ Don't build buttons from scratch: Use `<Button />`
- ❌ Don't create custom cards: Use `<Card />`
- ❌ Don't hardcode px values: Use theme tokens
- ❌ Don't skip animations: Use `animations.*`

## Do's ✅

- ✅ Use theme tokens for everything
- ✅ Compose styles with spread operators
- ✅ Reuse components from `styled.tsx`
- ✅ Leverage utility styles
- ✅ Add animations to interactions
- ✅ Keep spacing consistent
- ✅ Follow TypeScript types

---

**Quick tip:** Use the `DesignSystemShowcase.tsx` component to see all available options visually!
