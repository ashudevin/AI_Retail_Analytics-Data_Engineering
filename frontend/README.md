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
```

Static files are output to `frontend/out/` (compatible with Vercel static hosting).

## Deploy to Vercel

1. Push the repo to GitHub.
2. Import the project in [Vercel](https://vercel.com/new).
3. Set **Root Directory** to `frontend`.
4. Framework Preset: **Next.js** (auto-detected).
5. Build Command: `npm run build`
6. Output Directory: `out` (static export)

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
