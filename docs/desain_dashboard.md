# Dashboard Design System — Gaet Operations Hub

> **Authority Document**: This file is the single source of truth for all visual identity, component usage, user interaction, and layout rules for the **Gaet Operations Dashboard**. Any future changes to `dashboard/static/index.html` or `dashboard/server.py` MUST strictly comply with the patterns, design tokens, and decision rules documented here.

---

## 1. Project Context & Product Overview

### What is Gaet?
`gaet` is a lightweight, zero-dependency **PostgreSQL Database Backup & Synchronization System**. It provides a CLI and a companion Web Operations Hub to backup, restore, compare (`diff`), diagnose (`doctor`), and synchronize PostgreSQL databases between local environments and cloud targets (e.g. Supabase, Neon, AWS RDS, GCP CloudSQL, or socket/network instances).

### Target Audience & Core Jobs
- **Target Users**: Database Administrators, DevOps Engineers, and Full-Stack Developers managing PostgreSQL databases.
- **Main Jobs**:
  1. Monitor real-time synchronization status between local PostgreSQL and cloud targets.
  2. Perform on-demand backups (`push`), restores (`fetch`), and snapshot file management.
  3. Inspect table-by-table schema differences and record counts.
  4. Run system diagnostics (`doctor`) and manage environment configuration (`.env`).
  5. Monitor live operation logs and auto-backup schedules.

### Information Architecture
- **Header**: Branding, Version Badge (`gaet v3.0.2`), Navigation Tabs, Live Status Pulse Pill, Diagnostic Action (`🩺 Doctor Check`), Refresh Action, Theme Switcher (Dark/Light).
- **Tab 1: Overview**: System Health Banners, Stat Cards (Local DB Size, Cloud DB Size, Total Rows, Backup Count), Table Schema Matrix with per-table Sync Actions, Quick Actions Bar, and Live Activity Log stream.
- **Tab 2: Snapshots**: Local Snapshot Management Table, Retention Rules Indicator, Download/Restore/Delete actions.
- **Tab 3: Real-Time Logs**: Full log viewer with live 3-second auto-polling and clear log functionality.
- **Tab 4: Settings**: Card-based configuration for Local DB, Cloud Target DB, Auto-Backup Retention, Dashboard Port/Host, Diagnostics, Active Environment Grid, and Shell Env Exporter.

---

## 2. Current UI Architecture

The Gaet Dashboard is purposefully engineered with **zero external JavaScript or CSS framework dependencies** to ensure maximum performance, security, and portability:

```text
dashboard/
├── server.py              # Lightweight Python stdlib (http.server) API & static file server
├── static/
│   └── index.html         # Single-file HTML5 app containing CSS Tokens, Component UI, and Vanilla JS
```

### Key Technical Patterns
- **Styling**: Pure Vanilla CSS using CSS Custom Properties (`:root` for Dark Theme, `[data-theme="light"]` for Light Theme).
- **Icons**: Clean Unicode emojis and SVG icons matching developer tool aesthetics.
- **Typography**: Google Fonts (`Inter` for UI typography, `JetBrains Mono` for code snippets, SQL schemas, and tables).
- **State & Polling**: Native Vanilla JS with `fetch()` API. Auto-polls `/api/status` every 4 seconds and `/api/logs` every 3 seconds.

---

## 3. Design Character & Aesthetic Rules

The visual identity of Gaet is **Operations-First, High-Density, and Terminal-Inspired**.

### Observable Design Rules
1. **High Information Density**: Present database metrics, row counts, and connection strings clearly without unnecessary whitespace padding.
2. **Dual-Theme Support**: Dark Mode as default (`#0b0f17`) for terminal-oriented workflows; Light Mode (`#f8fafc`) with rich contrast.
3. **Glassmorphism Header & Card Surfaces**: Subtle backdrop filters (`backdrop-filter: blur(16px)`) with crisp borders (`rgba(255, 255, 255, 0.08)`).
4. **Terminal Accent Elements**: Monospace data display, live pulsing indicator dots (`.live-pulse`), and console boxes (`.console-box`).
5. **Clear Status Visuals**: Color-coded status badges (`✓ Synced`, `✗ Diff Detected`, `Unreachable`) for instant situational awareness.

---

## 4. Design Principles

1. **Information Over Decoration**: Every card, badge, and color MUST represent real system state. Never add visual elements purely for decoration.
2. **Instant Status Visibility**: Connection health and sync diff status must be recognizable within 1 second of landing on the page.
3. **Explicit Destructive Safeguards**: Destructive actions (Database Restores, Snapshot Deletions) MUST require user confirmation dialogs and destructive button styling (`.btn-danger`).
4. **Subtle Micro-Animations**: Transitions for tab switching, modal fade-ins, and button hovers must be smooth (150ms–250ms) and never block user action.
5. **Strict Monospace Data Hygiene**: Database names, file paths, connection strings, SQL tables, and row counts must always use `JetBrains Mono`.

---

## 5. Design Tokens

### Spacing Scale
| Token / Value | Usage |
| :--- | :--- |
| `2px` | Micro padding (badges, inner borders) |
| `4px / 6px` | Inner gap between tab icons and text, small pill paddings |
| `8px` | Small button padding (`5px 10px` / `8px 16px`), input field padding |
| `12px / 14px` | Card header gaps, banner paddings |
| `16px` | Grid layout gaps (`stat-grid`, `config-grid-styled`) |
| `20px` | Card body internal padding, modal header/body padding |
| `24px` | Main content container padding (`.main-content`), section margins |
| `32px` | Major section separation |

### Border Radius Scale
- **Default Card Radius (`--radius`)**: `12px`
- **Small Control Radius (`--radius-sm`)**: `8px`
- **Extra Small Badge/Button Radius**: `6px`
- **Pill / Circular Radius**: `999px` (Status pills, version badges)

### Shadow Scale
- **Card Hover Shadow**: `0 8px 20px rgba(0, 0, 0, 0.2)`
- **Modal Box Shadow**: `0 12px 32px rgba(0, 0, 0, 0.4)`
- **Primary Button Shadow**: `0 4px 12px rgba(37, 99, 235, 0.3)`
- **Logo Icon Glow**: `0 4px 12px rgba(59, 130, 246, 0.3)`

---

## 6. Typography System

### Font Families
- **Primary UI Font (`--font-sans`)**: `'Inter', -apple-system, BlinkMacSystemFont, sans-serif`
- **Monospace Code & Data Font (`--font-mono`)**: `'JetBrains Mono', monospace`

### Scale & Hierarchy
| Level | Font Size | Weight | Line Height | Letter Spacing | Font Family | Example Target |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Page Title** | `20px` | 700 | 1.2 | `-0.02em` | Sans | Logo Header (`.logo-text h1`) |
| **Section Title** | `16px` | 600 | 1.3 | `-0.01em` | Sans | Card Headers (`h2`, `h3`) |
| **Body / Inputs** | `13px / 14px` | 400 / 500 | 1.5 | Normal | Sans | Card descriptions, Form fields |
| **Navigation** | `13px` | 600 | 1.0 | Normal | Sans | Header Tabs (`.tab-btn`) |
| **Stat Numbers** | `24px` | 700 | 1.1 | `-0.02em` | Sans / Mono | Stat Card Values (`.stat-value`) |
| **Table Data** | `13px` | 500 | 1.4 | Normal | Monospace | Table names, Row counts |
| **Meta / Hints** | `11px / 12px` | 400 / 500 | 1.4 | Normal | Sans / Mono | Form hints, Version badges |

---

## 7. Color System & Theme Specifications

### Color Tokens Matrix

| Semantic Role | Dark Mode (`:root`) | Light Mode (`[data-theme="light"]`) | Usage |
| :--- | :--- | :--- | :--- |
| **Background Primary** | `#0b0f17` | `#f8fafc` | Main application background |
| **Background Secondary** | `#111827` | `#f1f5f9` | Header, side panels, hover bases |
| **Card Surface** | `rgba(17, 24, 39, 0.7)` | `rgba(255, 255, 255, 0.9)` | Cards, tables, modal containers |
| **Card Hover Surface** | `rgba(31, 41, 55, 0.8)` | `#ffffff` | Elevated interactive cards |
| **Border Neutral** | `rgba(255, 255, 255, 0.08)` | `rgba(0, 0, 0, 0.08)` | Dividers, card outlines |
| **Border Accent** | `rgba(59, 151, 151, 0.35)` | `rgba(59, 151, 151, 0.4)` | Active states, primary focus |
| **Text Primary** | `#f3f4f6` | `#0f172a` | Primary titles, table headers |
| **Text Secondary** | `#9ca3af` | `#475569` | Subtitles, labels, descriptions |
| **Text Muted** | `#6b7280` | `#94a3b8` | Metadata, disabled text, hints |
| **Primary Accent (Logo Teal)** | `#3b9797` | `#2b7a7a` | Primary buttons, active tabs, main accents |
| **Accent Hover** | `#2b7a7a` | `#1e5959` | Primary button hover |
| **Accent Crimson (Logo Crimson)** | `#ae2448` (`rgba(174,36,72,0.15)`) | `#901b39` (`rgba(144,27,57,0.1)`) | Logo secondary gradient, cloud badges |
| **Status Green (Success)**| `#10b981` (`rgba(16,185,129,0.12)`) | `#059669` (`rgba(5,150,105,0.1)`) | Synced state, success toasts |
| **Status Red (Danger)** | `#ef4444` (`rgba(239,68,68,0.12)`) | `#dc2626` (`rgba(220,38,38,0.1)`) | Out of sync, delete actions, errors |
| **Status Yellow (Warning)**| `#f59e0b` (`rgba(245,158,11,0.12)`) | `#d97706` (`rgba(217,119,6,0.1)`) | Unreachable DB, warnings |

---

## 8. Layout & Responsive System

### Grid System
- **Max Width**: `1280px` (centered via `margin: 0 auto`).
- **Stat Cards Grid**: `repeat(4, 1fr)` on Desktop, `repeat(2, 1fr)` on Tablet (`<= 960px`), `1fr` on Mobile (`<= 560px`).
- **Settings Layout**: 2-column grid (`240px` sidebar + `1fr` main panel) on Desktop, stacks vertically on Mobile (`<= 768px`).

### Breakpoints
- **Desktop**: `> 960px`
- **Tablet**: `561px – 960px`
- **Mobile**: `<= 560px`

---

## 9. Component Specifications & Usage Rules

### Button Variants
- **Primary (`.btn-primary`)**: Major workflow triggers (`Save & Apply Configuration`, `Copy to Clipboard`).
- **Secondary (`.btn-secondary`)**: Neutral actions (`Refresh`, `🩺 Doctor Check`, `🔍 Diff Analysis`, `⚡ Dry Run`, `☁️ Test Connection`).
- **Danger (`.btn-danger`)**: Destructive actions (`Delete Snapshot`, `Restore Database`).
- **Warning (`.btn-warning`)**: State-toggle actions (`Enable Auto-Backup`).

### Table Schema Matrix (`.data-table`)
- Alternating subtle row backgrounds with clean hover highlight (`rgba(255, 255, 255, 0.02)`).
- Monospace font for table names and record counts.
- Right-aligned numbers for quick visual parsing.
- Per-table Quick Action buttons (`Push Sync`).

### Modals & Dialogs (`.modal-backdrop`)
- Fixed position backdrop with `backdrop-filter: blur(4px)`.
- Max-width options: `720px` (Doctor / Diff output), `650px` (Export output).
- Dark terminal console output box (`.console-box`) with syntax-highlighted text (`#38bdf8` on `#0f172a`).

---

## 10. Anti-AI-Slop & Do Not Invent Rules

### ❌ Anti-AI-Slop Rules
1. **NO Generic SaaS Gradients**: Do NOT add purple-pink decorative gradients to cards. Use solid dark/light card backgrounds (`var(--bg-card)`).
2. **NO Floating 3D Blobs**: Do NOT introduce decorative animated background spheres or irrelevant 3D illustrations.
3. **NO Fake Numbers**: Every number displayed in stat cards or tables MUST reflect live PostgreSQL CLI & database state.
4. **NO Arbitrary Glassmorphism Overuse**: Glassmorphism is strictly reserved for the sticky top header and stat card containers.

### 🛑 "Do Not Invent" Rules
1. **DO NOT introduce external frameworks**: No React, Vue, Svelte, TailwindCSS, or Bootstrap. Keep `index.html` vanilla.
2. **DO NOT alter CSS token variable names**: Preserve existing names (`--bg-primary`, `--accent`, `--green`, etc.).
3. **DO NOT change font dependencies**: Stick to Google Fonts `Inter` and `JetBrains Mono`.
4. **DO NOT modify Python stdlib server architecture**: Keep `server.py` lightweight and built on `http.server`.

---

## 11. Visual QA & Definition of Done

Before marking any UI/UX dashboard task complete, execute the following checklist:

1. **Theme Verification**: Test in both Dark Mode (`:root`) and Light Mode (`[data-theme="light"]`).
2. **Responsive Verification**: Test at `1280px`, `768px`, and `375px` viewports.
3. **Data Accuracy**: Verify that all table row counts match CLI output (`gaet status`).
4. **Interactive Polish**: Ensure spinners appear on buttons during active fetch requests.
5. **Toast Feedback**: Verify that success or error toast notifications display for all POST actions.
