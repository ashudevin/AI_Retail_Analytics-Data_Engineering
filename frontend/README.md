# AI Retail Analytics Dashboard

Static Next.js dashboard for the AI-Powered Retail Analytics platform. Loads pre-exported JSON from the Gold Layer — no backend, no database, no cold starts on Vercel.

## Architecture

```
PySpark (Gold Layer) → export_json.py → public/data/*.json → Next.js (static) → Vercel
```

## Prerequisites

1. Gold layer Parquet files in `data/processed/gold/`
2. AI insights in `data/ai_insights/` (optional but recommended)
3. Node.js 18+

## Setup

### 1. Export JSON from Gold Layer

From the project root:

```bash
python -m src.dashboard.export_json
```

Or on Windows:

```powershell
.\scripts\export_json.ps1
```

This writes JSON files to `frontend/public/data/`.

### 2. Install & Run Dashboard

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Build for Production

```bash
npm run build
npm run start   # optional local preview
```

Pages are pre-rendered at build time and served as static HTML on Vercel (CDN).

## Deploy to Vercel

| Setting | Value |
|---------|-------|
| **Root Directory** | `frontend` |
| **Framework Preset** | Next.js |
| **Build Command** | `npm run build` (default) |
| **Output Directory** | *(leave empty — use default)* |
| **Install Command** | `npm install` (default) |

> **Important:** Do **not** set Output Directory to `out`. That is only for
> `output: "export"` static exports. This project uses standard Next.js SSG,
> which outputs to `.next/` and requires `routes-manifest.json` for Vercel.

No environment variables required for the dashboard itself.

### Refreshing data on Vercel

Re-run the export script locally (or in CI), commit the updated `public/data/*.json` files, and redeploy.

## Pages

| Route | Description |
|-------|-------------|
| `/` | Overview KPIs and charts |
| `/products/` | Top products, reorder rates, search & sort |
| `/departments/` | Department rankings and distribution |
| `/customers/` | Segmentation and order frequency |
| `/basket/` | Basket size analysis |
| `/insights/` | Gemini AI executive summary |

## Tech Stack

- Next.js 15 (App Router, static export)
- TypeScript
- Tailwind CSS
- Recharts
- shadcn/ui-style components
- next-themes (dark mode)
