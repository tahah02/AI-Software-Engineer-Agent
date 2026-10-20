# Frontend Design Toolkit & Skill Activation Policy — AAISE

## 1. Overview & Purpose
This document catalogs the frontend design toolkit, specialized skills, design reference integrations, and browser testing tools configured for the Autonomous AI Software Engineer (AAISE) project. It defines the specific activation policy and division of responsibilities to ensure high-craft user interfaces while preventing tool conflict.

---

## 2. Toolkit Inventory & Responsibilities

| Tool / Skill | Upstream Source | Primary Responsibility | When to Activate |
| :--- | :--- | :--- | :--- |
| **Emil Kowalski Design Skills** (`emil-design-eng`, `animate`, `review-animations`) | `https://github.com/emilkowalski/skills.git` | Motion engineering, snappy easing curves, interaction polish, animation reviews | When crafting component transitions, hover states, modal animations, or reviewing motion code |
| **Impeccable** (`impeccable`) | `https://github.com/pbakaus/impeccable.git` / `impeccable.style` | Design critique, typography scales, spacing rhythm, anti-generic AI layout audits, accessibility | When performing comprehensive design audits, refactoring UI hierarchy, or reviewing component styling |
| **Taste Skill** (`design-taste-frontend`) | `https://github.com/Leonxlnx/taste-skill.git` | Visual direction, layout composition, dashboard aesthetic standards, anti-slop guidelines | When establishing new screen layouts (chat workspace, file explorer, metrics dashboards) |
| **Figma MCP** (`figma-developer-mcp`) | Stdio bridge / Figma REST API | Reading design tokens, inspecting Figma component trees, design-to-code fidelity | When translating approved Figma designs or design system variables into React components |
| **Playwright & Playwright MCP** | `https://github.com/microsoft/playwright` / `@playwright/mcp` | Browser automation, visual inspection, responsive layout verification, E2E tests | When testing frontend components, capturing screenshots, verifying responsive layouts and forms |

---

## 3. Skill Activation Policy & Division of Work

To avoid conflicting style directives and unnecessary token overhead:
1. **Never activate all design skills simultaneously**: Use the minimum toolset required for the specific task.
2. **Project Design System is the Primary Authority**: `docs/FRONTEND_DESIGN_SYSTEM.md` is the authoritative source of truth for AAISE colors, typography, and spacing. External skills refine and enforce these rules rather than overriding them.
3. **Task-Based Activation Routing**:

```
                                [Frontend Task Arrives]
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
         v                                 v                                 v
[Layout & Composition]           [Motion & Micro-Interaction]       [Verification & Audit]
  - Use `design-taste-frontend`    - Use `emil-design-eng`            - Design polish: `impeccable`
  - Use `docs/FRONTEND_DESIGN_...` - Use `animate` (< 250ms curves)   - Motion audit: `review-animations`
  - Inspect Figma if available     - Check composite properties only  - Browser test: Playwright
```

---

## 4. MCP Servers Configuration & Verification Status

The project configures two Model Context Protocol (MCP) servers in `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "cmd.exe",
      "args": ["/c", "npx", "--yes", "@playwright/mcp@latest"]
    },
    "figma": {
      "command": "cmd.exe",
      "args": ["/c", "npx", "--yes", "figma-developer-mcp", "--stdio"],
      "env": {
        "FIGMA_API_KEY": "%FIGMA_API_KEY%"
      }
    }
  }
}
```

### 4.1 Tool D: Figma MCP Server
- **Engine**: `figma-developer-mcp` (Stdio Process).
- **Authentication Status**: **VERIFIED & CONNECTED**.
  - Verified against Figma REST API: User `Muhammad Taha Hussain` (`muhammadtahahussain020@gmail.com`).
  - Stored securely in Windows User Environment variables (`FIGMA_API_KEY`), never hardcoded in git tracked files.
- **Purpose**: Enables inspecting design components, reading variables/design tokens, and translating frames into React components.

### 4.2 Tool E: Playwright & Playwright MCP
- **Package**: `@playwright/mcp@latest` (Playwright Engine `v1.64.1` verified locally).
- **Transport**: Stdio process (`cmd.exe /c npx --yes @playwright/mcp@latest`).
- **Connection Status**: **VERIFIED**. Local Playwright CLI and `@playwright/mcp` options are installed and functional.
- **Capabilities & Usage**:
  - Headless browser navigation to local Next.js development server (`http://localhost:3000`).
  - Taking full-page and component snapshots (`snapshot-mode: full`).
  - Verifying responsive breakpoints (mobile 375px, tablet 768px, desktop 1440px).
  - Inspecting DOM accessibility trees and console error logs.
