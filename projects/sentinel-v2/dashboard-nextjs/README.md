# Sentinel Dashboard - Next.js Professional

Real-time dashboard for Sentinel V2 AI agent workflow visualization.

## Stack
- Next.js 14 (App Router)
- TypeScript (strict mode)
- Tailwind CSS
- Lucide React icons
- Socket.IO client (WebSocket)
- shadcn/ui components (optional)

## Setup
```bash
npm install
npm run dev
```

Open http://localhost:3000

## Architecture
```
Frontend (Next.js)
    ↕ WebSocket (Socket.IO)
Backend API (Flask + SocketIO)
    ↕ Reads/writes state files
Sentinel V2 Flow (CrewAI)
```

## Features
- Live phase tracker (Research → Match → Build → Approve → Deploy)
- Agent conversation chat (Lucide icons per agent role)
- Flow state summary dashboard
- Approval center with action buttons
- Real-time WebSocket updates (no polling)

## Configuration
Backend URL: http://localhost:5173 (Flask server)

To change, update `src/lib/config.ts`:
```typescript
export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5173';
```
