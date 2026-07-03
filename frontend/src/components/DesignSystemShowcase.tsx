/**
 * Modern Design System Showcase
 * Interactive component demonstrating all available design tokens and components
 * Visit /design-system to view this showcase
 */

import React, { useState } from "react"
import { theme } from "../../theme/theme"
import { utilityStyles } from "../../theme/utilityStyles"
import {
  Button,
  Card,
  Input,
  Badge,
  GlassPanel,
  Divider,
  Spinner,
  Text,
} from "../styled"

export const DesignSystemShowcase: React.FC = () => {
  const [loading, setLoading] = useState(false)

  return (
    <div
      style={{
        maxWidth: "1400px",
        margin: "0 auto",
        padding: theme.spacing.8,
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: theme.spacing.12 }}>
        <Text variant="heading1" style={{ marginBottom: theme.spacing.2 }}>
          🎨 Modern Design System
        </Text>
        <Text variant="bodyLarge" color={400}>
          Beautiful, futuristic, and consistent UI components for DocIntel
        </Text>
      </div>

      {/* Color Palette Section */}
      <div style={{ marginBottom: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Color Palette
        </Text>

        {/* Primary Colors */}
        <div style={{ marginBottom: theme.spacing.8 }}>
          <Text variant="heading4" style={{ marginBottom: theme.spacing.4 }}>
            Primary Colors
          </Text>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: theme.spacing.4,
            }}
          >
            {Object.entries(theme.colors.primary).map(([key, value]) => (
              <div key={key}>
                <div
                  style={{
                    width: "100%",
                    height: 60,
                    borderRadius: theme.borderRadius.lg,
                    background: value,
                    marginBottom: theme.spacing.2,
                    boxShadow: `0 4px 12px ${value}40`,
                    border: `1px solid rgba(255,255,255,0.1)`,
                  }}
                />
                <Text variant="caption" color={500}>
                  {key}
                </Text>
              </div>
            ))}
          </div>
        </div>

        {/* Secondary Colors */}
        <div style={{ marginBottom: theme.spacing.8 }}>
          <Text variant="heading4" style={{ marginBottom: theme.spacing.4 }}>
            Secondary Colors
          </Text>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: theme.spacing.4,
            }}
          >
            {Object.entries(theme.colors.secondary).map(([key, value]) => (
              <div key={key}>
                <div
                  style={{
                    width: "100%",
                    height: 60,
                    borderRadius: theme.borderRadius.lg,
                    background: value,
                    marginBottom: theme.spacing.2,
                    boxShadow: `0 4px 12px ${value}40`,
                    border: `1px solid rgba(255,255,255,0.1)`,
                  }}
                />
                <Text variant="caption" color={500}>
                  {key}
                </Text>
              </div>
            ))}
          </div>
        </div>
      </div>

      <Divider margin="lg" />

      {/* Buttons Section */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Buttons
        </Text>

        {/* Primary Buttons */}
        <div style={{ marginBottom: theme.spacing.8 }}>
          <Text variant="heading4" style={{ marginBottom: theme.spacing.4 }}>
            Primary
          </Text>
          <div style={{ display: "flex", gap: theme.spacing.4, flexWrap: "wrap" }}>
            <Button variant="primary" size="sm">
              Small
            </Button>
            <Button variant="primary" size="md">
              Medium
            </Button>
            <Button variant="primary" size="lg">
              Large
            </Button>
            <Button
              variant="primary"
              loading={loading}
              onClick={() => {
                setLoading(true)
                setTimeout(() => setLoading(false), 2000)
              }}
            >
              {loading ? "Loading..." : "Click me"}
            </Button>
          </div>
        </div>

        {/* Secondary Buttons */}
        <div style={{ marginBottom: theme.spacing.8 }}>
          <Text variant="heading4" style={{ marginBottom: theme.spacing.4 }}>
            Secondary
          </Text>
          <div style={{ display: "flex", gap: theme.spacing.4, flexWrap: "wrap" }}>
            <Button variant="secondary" size="sm">
              Small
            </Button>
            <Button variant="secondary" size="md">
              Medium
            </Button>
            <Button variant="secondary" size="lg">
              Large
            </Button>
          </div>
        </div>

        {/* Ghost Buttons */}
        <div style={{ marginBottom: theme.spacing.8 }}>
          <Text variant="heading4" style={{ marginBottom: theme.spacing.4 }}>
            Ghost
          </Text>
          <div style={{ display: "flex", gap: theme.spacing.4, flexWrap: "wrap" }}>
            <Button variant="ghost" size="sm">
              Small
            </Button>
            <Button variant="ghost" size="md">
              Medium
            </Button>
            <Button variant="ghost" size="lg">
              Large
            </Button>
          </div>
        </div>

        {/* Danger Buttons */}
        <div>
          <Text variant="heading4" style={{ marginBottom: theme.spacing.4 }}>
            Danger
          </Text>
          <div style={{ display: "flex", gap: theme.spacing.4, flexWrap: "wrap" }}>
            <Button variant="danger" size="sm">
              Delete
            </Button>
            <Button variant="danger" size="md">
              Remove
            </Button>
            <Button variant="danger" size="lg">
              Dangerous Action
            </Button>
          </div>
        </div>
      </div>

      <Divider margin="lg" />

      {/* Cards Section */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Cards & Panels
        </Text>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: theme.spacing.6,
          }}
        >
          {/* Basic Card */}
          <Card>
            <Text variant="heading4" style={{ marginBottom: theme.spacing.3 }}>
              Basic Card
            </Text>
            <Text variant="body" color={400}>
              A clean, modern card component with hover effects and subtle gradients
            </Text>
          </Card>

          {/* Glass Panel */}
          <GlassPanel intensity="medium">
            <Text variant="heading4" style={{ marginBottom: theme.spacing.3 }}>
              Glass Panel
            </Text>
            <Text variant="body" color={400}>
              Glassmorphism effect with backdrop blur for modern aesthetics
            </Text>
          </GlassPanel>

          {/* Dark Glass Panel */}
          <GlassPanel intensity="dark">
            <Text variant="heading4" style={{ marginBottom: theme.spacing.3 }}>
              Dark Glass
            </Text>
            <Text variant="body" color={400}>
              Dark variant perfect for contrast on lighter backgrounds
            </Text>
          </GlassPanel>
        </div>
      </div>

      <Divider margin="lg" />

      {/* Inputs Section */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Forms & Inputs
        </Text>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: theme.spacing.6,
          }}
        >
          <Input label="Text Input" placeholder="Enter some text..." />
          <Input label="Email" type="email" placeholder="your@email.com" />
          <Input label="Password" type="password" placeholder="••••••••" />
          <Input
            label="With Error"
            placeholder="This has an error"
            error="This field is required"
          />
        </div>
      </div>

      <Divider margin="lg" />

      {/* Badges Section */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Badges
        </Text>

        <div style={{ display: "flex", gap: theme.spacing.4, flexWrap: "wrap" }}>
          <Badge variant="primary">Primary</Badge>
          <Badge variant="secondary">Secondary</Badge>
          <Badge variant="success">Success</Badge>
          <Badge variant="warning">Warning</Badge>
          <Badge variant="error">Error</Badge>
        </div>
      </div>

      <Divider margin="lg" />

      {/* Spinners Section */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Loading States
        </Text>

        <div
          style={{
            display: "flex",
            gap: theme.spacing.8,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <div style={{ textAlign: "center" }}>
            <Spinner size="sm" />
            <Text variant="caption" style={{ marginTop: theme.spacing.2, display: "block" }}>
              Small
            </Text>
          </div>
          <div style={{ textAlign: "center" }}>
            <Spinner size="md" />
            <Text variant="caption" style={{ marginTop: theme.spacing.2, display: "block" }}>
              Medium
            </Text>
          </div>
          <div style={{ textAlign: "center" }}>
            <Spinner size="lg" />
            <Text variant="caption" style={{ marginTop: theme.spacing.2, display: "block" }}>
              Large
            </Text>
          </div>
          <div style={{ textAlign: "center" }}>
            <Spinner size="lg" color="secondary" />
            <Text variant="caption" style={{ marginTop: theme.spacing.2, display: "block" }}>
              Secondary
            </Text>
          </div>
        </div>
      </div>

      <Divider margin="lg" />

      {/* Typography Section */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Typography
        </Text>

        <div style={{ display: "flex", flexDirection: "column", gap: theme.spacing.4 }}>
          <Text variant="heading1">Heading 1 - Main Title</Text>
          <Text variant="heading2">Heading 2 - Section Title</Text>
          <Text variant="heading3">Heading 3 - Subsection</Text>
          <Text variant="heading4">Heading 4 - Card Title</Text>
          <Text variant="heading5">Heading 5 - Small Title</Text>
          <Text variant="bodyLarge">
            Large body text - Used for prominent descriptions and key content
          </Text>
          <Text variant="body">
            Regular body text - This is the standard text size for most content on the page
          </Text>
          <Text variant="bodySmall">
            Small body text - Used for secondary information and captions
          </Text>
          <Text variant="caption">
            Caption text - Used for labels, hints, and very small supporting text
          </Text>
        </div>
      </div>

      {/* Gradients Section */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Gradients
        </Text>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: theme.spacing.6,
          }}
        >
          {Object.entries(theme.gradients).map(([key, value]) => (
            <div key={key}>
              <div
                style={{
                  width: "100%",
                  height: 120,
                  borderRadius: theme.borderRadius.lg,
                  background: value,
                  marginBottom: theme.spacing.3,
                  border: `1px solid rgba(255,255,255,0.1)`,
                }}
              />
              <Text variant="caption" color={500}>
                {key}
              </Text>
            </div>
          ))}
        </div>
      </div>

      {/* Spacing Guide */}
      <div style={{ marginBottom: theme.spacing.12, marginTop: theme.spacing.12 }}>
        <Text variant="heading2" style={{ marginBottom: theme.spacing.6 }}>
          Spacing Scale
        </Text>

        <div style={{ display: "flex", gap: theme.spacing.6, flexWrap: "wrap" }}>
          {Object.entries(theme.spacing).map(([key, value]) => (
            <div key={key}>
              <div
                style={{
                  width: 120,
                  height: 40,
                  background: `linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%)`,
                  borderRadius: theme.borderRadius.md,
                  marginBottom: theme.spacing.2,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#FFFFFF",
                  fontSize: theme.typography.fontSize.xs,
                  fontWeight: theme.typography.fontWeight.bold,
                }}
              >
                {value}
              </div>
              <Text variant="caption" color={500}>
                {key}
              </Text>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
