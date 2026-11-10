# Technical Design Document - BCFC Mini SME Back-Office Banking Portal

## 1. Architecture Overview
The application is built as a Next.js 14 App Router (React 18, TypeScript, Tailwind CSS, Recharts) single-page application and modular portal. It features a built-in Server-Side API Gateway acting as a secure proxy to the BankSmart Core Platform Sandbox, an internal state and operational middle-office store with an SLA engine, and three segregated workstations (RM View, Operations Command Center, Credit Risk View).

## 2. Module Boundaries & Directory Structure
- `src/app/api/banksmart/`: Server-side route handlers proxying BankSmart core endpoints.
- `src/app/api/operations/state/`: Operational state endpoints (GET/POST) for maker-checker queue and metrics.
- `src/lib/state/operational-store.ts`: In-memory and persisted operational storage for transactions and audit trails.
- `src/lib/sla/engine.ts`: SLA TAT computation engine (24-hour threshold).
- `src/components/workstations/`: RM View, Operations Command Center, and Credit Risk View.
- `src/components/modals/`: 4-Gate Murabaha Wizard, Client 360, Repayment Schedule, Transaction Review.
- `src/components/auth/`: LoginView and TopBar.

## 3. Server-Side API Gateway Specifications
Proxies all requests to `http://api-apacsbx.dbgsonline.com:8003` with:
- Headers: `User-Agent: PostmanRuntime/7.39.0`, `Accept: */*`, `Authorization: Basic VmVuZG9yNTpQQHNzdzByZDU=`
- Request Envelope: `SignOnRq` (or lowercase `signOnRq` for Outward Payment) containing `LogId` (UUID v4), `DateTime` (ISO 8601 without 'Z'), `ChannelId` ("0"), `OurBranchId` ("01").
- Commodity Booking Calendar Sync: `invoiceDate: "2031-08-01T00:00:00+08:00"`.

## 4. Data Entities & State Management
- **Customer / CIF**: CIF 50000248 (Sample Customer A), CIF 50000231 (Sample Customer B).
- **Facilities & Loans**: Multi-loan support, sub-loans, DPD tracking, IFRS 9 ECL stages (Stage 1, Stage 2, Stage 3).
- **Operations State**: Maker-Checker queues, SLA tracking (`ON_TRACK`, `WARNING`, `BREACHED`).