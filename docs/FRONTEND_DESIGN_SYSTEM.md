# Frontend Design System & Craft Standards — AAISE

## 1. Design Philosophy: The Developer's Workshop
The Autonomous AI Software Engineer (AAISE) frontend is a high-performance, professional, chat-first software engineering workspace inspired by modern developer environments (Linear, Cursor, GitHub, VS Code, Antigravity).

### Anti-Generic ("No AI-Slop") Directives
The interface must **never** feel like a generic AI template. Specifically, we prohibit:
- **No generic purple/indigo glow gradients** or neon glassmorphism effects.
- **No excessive border radii** (keep corners clean and subtle: 4px to 8px max).
- **No giant, decorative floating cards** with massive drop shadows (`shadow-2xl` is banned; use subtle `shadow-sm` or 1px border dividers).
- **No sluggish, decorative animations** (transitions must be crisp, functional, and strictly under 250ms).
- **No noisy, uncurated iconography** or mismatched visual metaphors.
- **No unnecessary client-side state duplication** or giant monolithic React components.

Prioritize **usability, information density, visual hierarchy, and performance** over ornamentation.

---

## 2. Color System & Surfaces

The color palette is engineered for prolonged engineering sessions in both Dark and Light modes. Dark mode is the primary developer theme.

### 2.1 Neutral Surfaces (Zinc / Slate Slate Balance)
| Token | Dark Mode (Default) | Light Mode | Purpose |
| :--- | :--- | :--- | :--- |
| `bg-canvas` | `#090A0F` (Deep Slate Black) | `#F8FAFC` (Cool Off-White) | Root application background |
| `bg-surface-1` | `#11131A` (Card / Sidebar) | `#FFFFFF` (Pure White) | Navigation panels, explorer, toolbars |
| `bg-surface-2` | `#181B26` (Active Item / Input) | `#F1F5F9` (Muted Gray) | Chat bubbles, active tabs, input boxes |
| `border-subtle` | `rgba(255, 255, 255, 0.08)` | `rgba(0, 0, 0, 0.08)` | Structural dividers, panels, card borders |
| `border-hover` | `rgba(255, 255, 255, 0.16)` | `rgba(0, 0, 0, 0.18)` | Interactive borders on focus / hover |

### 2.2 Typography Colors
| Token | Dark Mode | Light Mode | Purpose |
| :--- | :--- | :--- | :--- |
| `text-primary` | `#F1F5F9` (95% brightness) | `#0F172A` (Slate 900) | Headings, user chat messages, active code |
| `text-secondary`| `#94A3B8` (Slate 400) | `#475569` (Slate 600) | Subheadings, agent metadata, timestamps |
| `text-muted` | `#64748B` (Slate 500) | `#94A3B8` (Slate 400) | Inactive tabs, placeholder text, hints |

### 2.3 Semantic & Agent Accent Colors
Accents are used with restraint to communicate state and agent identity:
- **Agent 1 (Doc Review / Specs)**: Emerald (`#10B981`) — precision, architecture, verification.
- **Agent 2 (Mock Vendor API)**: Amber (`#F59E0B`) — vendor simulation, sandboxed service.
- **Agent 3 (Main Coding Agent)**: Cyan (`#06B6D4`) — core application logic, code implementation.
- **Agent 4 (Independent QA)**: Blue (`#3B82F6`) — test runs, verification gates.
- **Agent 5 (Security Reviewer)**: Violet (`#8B5CF6`) — read-only audit, threat modeling.
- **Status Accents**:
  - `Success`: Emerald (`#10B981`)
  - `Warning / Pending Approval`: Amber (`#F59E0B`)
  - `Error / Defect / Blocker`: Rose / Red (`#EF4444`)

---

## 3. Typography Scale & Hierarchy

We use a disciplined, readable dual-font system:
1. **Primary Interface Font**: Inter, Geist, or system sans-serif (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`).
2. **Code & Metrics Font**: JetBrains Mono, Geist Mono, or system monospace (`ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`).

### Typography Scale
| Level | Font Size | Line Height | Weight | Usage |
| :--- | :--- | :--- | :--- | :--- |
| `Display` | 24px (`1.5rem`) | 32px | 600 (Semi-Bold) | Project Titles, Major Screen Headers |
| `Heading` | 18px (`1.125rem`) | 26px | 600 (Semi-Bold) | Section Headers, Modal Titles |
| `Subheading`| 14px (`0.875rem`) | 20px | 600 (Semi-Bold) | Panel Titles, Agent Card Headers |
| `Body` | 14px (`0.875rem`) | 22px | 400 (Regular) | Chat messages, description paragraphs |
| `Body-Small`| 12px (`0.75rem`) | 18px | 400 (Regular) | Metadata, timestamps, status labels |
| `Code` | 13px (`0.8125rem`)| 20px | 400 (Regular) | Code snippets, file tree items, log lines |

---

## 4. Spacing Rhythm & Layout Geometry

The interface adheres to a strict **4px/8px baseline grid**:
- **Padding & Margins**: Use standard multiples: `4px` (`p-1`), `8px` (`p-2`), `12px` (`p-3`), `16px` (`p-4`), `24px` (`p-6`).
- **Corner Radii**:
  - Small elements (badges, buttons, chips): `rounded-md` (`4px` to `6px`).
  - Containers (chat bubbles, cards, modals): `rounded-lg` (`8px`).
  - Never use full pills (`rounded-full`) except for status dot indicators or user avatars.
- **Borders & Dividers**: Prefer 1px solid dividers (`border border-subtle`) instead of heavy shadows to separate panels.

---

## 5. Interaction & Motion Design Principles

AAISE motion is functional, responsive, and grounded in physical realism. It adheres to **Emil Kowalski's motion design principles**:

1. **Duration Budget**:
   - Micro-interactions (hover, button clicks, tab switch): **100ms – 150ms**.
   - Panel transitions & modal entrances: **180ms – 220ms**.
   - Maximum allowable UI transition duration: **250ms**. Anything slower feels sluggish to engineers.
2. **Easing Curves**:
   - Never use standard browser `ease` or linear transitions for UI elements.
   - Use custom cubic-bezier curves:
     - Entrance / Open: `cubic-bezier(0.16, 1, 0.3, 1)` (snappy ease-out).
     - Exit / Close: `cubic-bezier(0.4, 0, 1, 1)` (clean ease-in).
3. **Properties to Animate**:
   - Strictly animate **composite-only properties**: `transform` and `opacity`.
   - Never animate `height`, `width`, `top`, `left`, or `margin` directly (causes browser reflow and frame drops).
4. **Reduced Motion**:
   - Always honor `prefers-reduced-motion: reduce` by zeroing transition durations and preserving instant state swaps.

---

## 6. Component Guidelines for Key Workspace Views

### 6.1 Conversational Chat Stream
- **Agent Identity Header**: Each message displays the specific agent badge (e.g., `Agent 1: Documentation Reviewer`) with its accent color dot, model identifier (`gemini-3.8-flash`), and timestamp.
- **Streaming State**: Real-time tokens stream with subtle opacity without layout shifts.
- **Collapsible Reasoning & Tool Execution**: Agent internal reasoning, tool calls, and Docker execution outputs are rendered inside clean collapsible blocks (`<details>` / accordion) with subtle borders.

### 6.2 Code & Artifact Previews
- Syntax-highlighted code blocks with line numbers and one-click copy buttons.
- Diff viewers for file modifications with clear green (`+`) and red (`-`) background highlights.

### 6.3 Human Approval Cards
- Prominent, high-contrast modal or inline card demanding user attention when LangGraph hits an interrupt gate (Specification Gate or Release Promotion Gate).
- Clear action buttons: `Approve` (Emerald solid), `Request Changes` (Amber outline), `Cancel` (Slate outline).

### 6.4 Metrics & Monitoring Dashboards
- Token usage and execution latency visualized via **Recharts** using minimalist stroke charts and area graphs.
- Clear breakdown of prompt vs. completion tokens and cost attribution per agent.
