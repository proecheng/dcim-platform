# Dark Theme Comprehensive Styling Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all white background issues and hardcoded colors across the entire application, ensuring consistent dark theme styling based on reference images (图片20.png, 图片39.png).

**Architecture:** Replace all hardcoded color values with CSS variables from the existing theme system. Update ECharts configurations to use theme-aware colors. Ensure all components render properly on dark backgrounds with readable text.

**Tech Stack:** Vue 3, SCSS, Element Plus, ECharts, CSS Custom Properties

---

## Reference Color Scheme (from 图片20.png, 图片39.png)

```scss
// Backgrounds
--bg-primary: #0a1628;           // Main background
--bg-secondary: #0d1b2a;         // Secondary background
--bg-tertiary: #112240;          // Tertiary (cards header)
--bg-card: rgba(26, 42, 74, 0.85); // Card background (semi-transparent)
--bg-card-solid: #1a2a4a;        // Card background (solid)

// Text
--text-primary: rgba(255, 255, 255, 0.95);   // Primary text (white)
--text-regular: rgba(255, 255, 255, 0.85);   // Regular text
--text-secondary: rgba(255, 255, 255, 0.65); // Secondary text
--text-placeholder: rgba(255, 255, 255, 0.45); // Placeholder

// Semantic Colors
--primary-color: #1890ff;        // Blue
--success-color: #52c41a;        // Green
--warning-color: #faad14;        // Orange/Yellow
--error-color: #f5222d;          // Red

// Accent
--accent-color: #00d4ff;         // Cyan highlight
```

---

## Task 1: Energy Statistics Page (energy/statistics.vue)

**Files:**
- Modify: `frontend/src/views/energy/statistics.vue`

**Step 1: Read the file to understand current structure**

Run: Read `frontend/src/views/energy/statistics.vue`

**Step 2: Update ECharts color configurations**

Replace hardcoded ECharts colors with theme-aware approach:
```typescript
// In script setup, add color constants using CSS variable values
const chartColors = {
  primary: '#1890ff',    // var(--primary-color)
  success: '#52c41a',    // var(--success-color)
  warning: '#faad14',    // var(--warning-color)
  error: '#f5222d',      // var(--error-color)
  text: 'rgba(255, 255, 255, 0.65)',
  axisLine: 'rgba(255, 255, 255, 0.1)',
}
```

Update chart options to use these colors and set dark backgrounds.

**Step 3: Update scoped styles**

Replace all hardcoded colors in `<style>` section:
- `#303133` → `var(--text-primary)`
- `#909399` → `var(--text-secondary)`
- `#eee` → `var(--border-color)`
- Add card backgrounds: `var(--bg-card-solid)`
- Add table dark styles

**Step 4: Run build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add frontend/src/views/energy/statistics.vue
git commit -m "fix(energy): update statistics page dark theme colors

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Energy Topology Page (energy/topology.vue)

**Files:**
- Modify: `frontend/src/views/energy/topology.vue`

**Step 1: Read the file**

**Step 2: Update icon and node colors**

Replace hardcoded colors with CSS variables:
- `#f5222d` → `var(--error-color)` (transformer)
- `#fa8c16` → `var(--warning-color)` (meter)
- `#1890ff` → `var(--primary-color)` (panel)
- `#52c41a` → `var(--success-color)` (circuit)
- `#722ed1` → `var(--info-color)` (device)

**Step 3: Update text and background styles**

Add dark theme styles:
```scss
.topology-page {
  :deep(.el-card) {
    background-color: var(--bg-card-solid);
    border-color: var(--border-color);
  }

  .node-label {
    color: var(--text-secondary);
  }
}
```

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 3: Energy Regulation Page (energy/regulation.vue)

**Files:**
- Modify: `frontend/src/views/energy/regulation.vue`

**Step 1: Read the file**

**Step 2: Update CSS styles**

Replace all hardcoded colors:
- `#409eff` → `var(--primary-color)`
- `#67c23a` → `var(--success-color)`
- `#e6a23c` → `var(--warning-color)`
- `#eee` → `var(--border-color)`
- `#909399` → `var(--text-secondary)`
- `#303133` → `var(--text-primary)`
- `#606266` → `var(--text-regular)`
- `#f5f7fa` → `var(--bg-tertiary)`

**Step 3: Add el-card and el-table dark styles**

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 4: Energy Suggestions Page (energy/suggestions.vue)

**Files:**
- Modify: `frontend/src/views/energy/suggestions.vue`

**Step 1: Read the file**

**Step 2: Update inline template styles**

Replace hardcoded icon wrapper colors with CSS variables or dynamic styles.

**Step 3: Update scoped styles**

Replace all hardcoded colors:
- Light backgrounds `#fef0f0`, `#fdf6ec`, `#f4f4f5` → semi-transparent dark equivalents
- Text colors → CSS variables
- Badge backgrounds → dark theme compatible

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 5: PUE Gauge Component (components/energy/PUEGauge.vue)

**Files:**
- Modify: `frontend/src/components/energy/PUEGauge.vue`

**Step 1: Read the file**

**Step 2: Update ECharts gauge options**

Replace hardcoded colors in gauge configuration:
- Gauge color array: use semantic colors
- Axis line/label colors: use theme-aware values
- Grid colors: use border color variable value

**Step 3: Update detail item styles**

Replace:
- `#f5f7fa` → `var(--bg-tertiary)`
- `#909399` → `var(--text-secondary)`
- `#303133` → `var(--text-primary)`

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 6: Power Card Component (components/energy/PowerCard.vue)

**Files:**
- Modify: `frontend/src/components/energy/PowerCard.vue`

**Step 1: Read the file**

**Step 2: Update computed color functions**

Replace hardcoded load rate colors with CSS variable values.

**Step 3: Update all CSS styles**

Replace all hardcoded text/border colors with CSS variables.

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 7: Cost Card Component (components/energy/CostCard.vue)

**Files:**
- Modify: `frontend/src/components/energy/CostCard.vue`

**Step 1: Read the file**

**Step 2: Update ECharts pie colors**

Use semantic color values in pie chart configuration.

**Step 3: Update template inline styles**

Replace hardcoded icon colors with dynamic or variable-based colors.

**Step 4: Update scoped styles**

Replace all hardcoded colors with CSS variables.

**Step 5: Run build to verify**

**Step 6: Commit**

---

## Task 8: Energy Suggestion Card Component (components/energy/EnergySuggestionCard.vue)

**Files:**
- Modify: `frontend/src/components/energy/EnergySuggestionCard.vue`

**Step 1: Read the file**

**Step 2: Update priority border colors**

Use CSS variables for priority indicators.

**Step 3: Update all text and background colors**

Replace:
- `#f0f9eb` → `rgba(82, 196, 26, 0.1)` (dark-compatible green bg)
- `#EBEEF5` → `var(--border-color)`
- All text colors → CSS variables

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 9: Suggestions Card Component (components/energy/SuggestionsCard.vue)

**Files:**
- Modify: `frontend/src/components/energy/SuggestionsCard.vue`

**Step 1: Read the file**

**Step 2: Update computed priority color function**

**Step 3: Update all hardcoded styles**

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 10: Status Tag Component (components/common/StatusTag.vue)

**Files:**
- Modify: `frontend/src/components/common/StatusTag.vue`

**Step 1: Read the file**

**Step 2: Update color map to use CSS variable values**

Replace hardcoded hex values with semantic colors from theme.

**Step 3: Run build to verify**

**Step 4: Commit**

---

## Task 11: Floor Layout Base Component (components/floor-layouts/FloorLayoutBase.vue)

**Files:**
- Modify: `frontend/src/components/floor-layouts/FloorLayoutBase.vue`

**Step 1: Read the file**

**Step 2: Update SVG colors**

Replace hardcoded SVG colors with CSS variable values or props for flexibility.

**Step 3: Update layout and legend styles**

Use CSS variables for backgrounds and text.

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 12: Asset Pages (asset/index.vue, asset/cabinet.vue)

**Files:**
- Modify: `frontend/src/views/asset/index.vue`
- Modify: `frontend/src/views/asset/cabinet.vue`

**Step 1: Read both files**

**Step 2: Update remaining hardcoded glow/shadow colors**

Replace rgba values with CSS variable-based equivalents.

**Step 3: Run build to verify**

**Step 4: Commit**

---

## Task 13: Operation Pages (workorder.vue, knowledge.vue)

**Files:**
- Modify: `frontend/src/views/operation/workorder.vue`
- Modify: `frontend/src/views/operation/knowledge.vue`

**Step 1: Read both files**

**Step 2: Update gradient backgrounds**

Use CSS variables for gradient colors where possible.

**Step 3: Update JS-based color maps**

Replace hardcoded category colors with theme-aware values.

**Step 4: Run build to verify**

**Step 5: Commit**

---

## Task 14: Login Page (login/index.vue)

**Files:**
- Modify: `frontend/src/views/login/index.vue`

**Step 1: Read the file**

**Step 2: Convert colors to CSS variables where appropriate**

Note: Login page has intentional custom design. Update for maintainability while preserving design.

**Step 3: Run build to verify**

**Step 4: Commit**

---

## Task 15: Final Build Verification and Testing

**Step 1: Run full build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 2: Review all modified files**

Ensure consistency across all changes.

**Step 3: Update documentation**

Update `progress.md` with V4.3.0 changes summary.

**Step 4: Final commit**

```bash
git add progress.md
git commit -m "docs: update progress with dark theme comprehensive fix V4.3.0

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Color Replacement Quick Reference

| Original | Replacement | Usage |
|----------|-------------|-------|
| `#303133` | `var(--text-primary)` | Primary text |
| `#606266` | `var(--text-regular)` | Regular text |
| `#909399` | `var(--text-secondary)` | Secondary text |
| `#C0C4CC` | `var(--text-placeholder)` | Placeholder |
| `#eee`, `#EBEEF5` | `var(--border-color)` | Borders |
| `#f5f7fa`, `#fafafa` | `var(--bg-tertiary)` | Light backgrounds |
| `#409eff`, `#1890ff` | `var(--primary-color)` | Primary blue |
| `#67c23a`, `#52c41a` | `var(--success-color)` | Success green |
| `#e6a23c`, `#faad14` | `var(--warning-color)` | Warning orange |
| `#f56c6c`, `#f5222d` | `var(--error-color)` | Error red |
| `white`, `#fff` | `var(--text-primary)` or keep for contrast | White text |

---

## Verification Checklist

After all tasks complete:
- [ ] All pages render with dark backgrounds
- [ ] All text is readable (good contrast)
- [ ] All ECharts charts have appropriate dark theme
- [ ] All tables have dark headers and proper row colors
- [ ] All cards have consistent dark backgrounds
- [ ] All forms have dark input fields
- [ ] Build passes without errors
- [ ] Documentation updated
