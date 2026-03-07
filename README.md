# Mission Control

Dashboard for Agent Software Company - Centralized management of AI agents, projects, documentation, and operations.

## Features

- 🏢 **Company Dashboard** - Revenue metrics, growth tracking, agent performance
- 🤖 **Agents Panel** - Manage AI agents, view status, edit SOUL/MEMORY/PROGRESS
- 📊 **Usage Dashboard** - Token consumption, cost analysis by model and agent
- ⏰ **Cron Management** - View, run manually, and delete scheduled jobs
- 📋 **Documentation Browser** - Navigate project docs, company docs, agent configs
- 🔌 **WebSocket Integration** - Real-time connection to OpenClaw Gateway

## Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Dark theme UI
- **Lucide React** - Icon library
- **Recharts** - Data visualization
- **TanStack Query** - Data fetching and caching

## Getting Started

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

The app will be available at `http://localhost:3000`

## OpenClaw Integration

The dashboard connects to OpenClaw Gateway via WebSocket:

```
ws://localhost:18789/ws?token=<YOUR_TOKEN>
```

Make sure OpenClaw Gateway is running before starting the dashboard.

## Project Structure

```
mission-control/
├── src/
│   ├── app/                    # Next.js app directory
│   │   ├── layout.tsx         # Root layout
│   │   ├── page.tsx           # Main app (ContentRouter)
│   │   └── globals.css        # Global styles
│   ├── components/
│   │   ├── panels/            # Feature panels
│   │   │   ├── company-panel.tsx
│   │   │   ├── agents-panel.tsx
│   │   │   ├── usage-panel.tsx
│   │   │   ├── cron-panel.tsx
│   │   │   └── docs-panel.tsx
│   │   ├── modals/            # Modal components
│   │   │   └── agent-modal.tsx
│   │   └── layout/            # Layout components
│   │       └── nav-rail.tsx
│   └── lib/
│       └── websocket.ts       # WebSocket client
├── docs-site/                 # MkDocs documentation
│   ├── mkdocs.yml
│   └── docs/
│       ├── operating-model.md
│       └── 30-day-plan.md
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## Usage

### Company Dashboard
View key metrics:
- Total revenue and growth
- Active agents count
- Total projects
- Revenue trends and performance charts

### Agents Panel
- View all agents with status (active/idle/error)
- Click agent card to edit SOUL.md, MEMORY.md, PROGRESS.md
- Start/Pause agents
- Delete agents

### Usage Dashboard
- Track token consumption by model
- View costs per agent
- Analyze usage trends over time

### Cron Management
- View all scheduled jobs
- Run jobs manually
- Delete jobs
- Create new jobs (form coming soon)

### Documentation Browser
- Navigate file tree
- View and markdown files
- Edit files with save button
- Organized by: Company, Projects, Agents

## License

MIT
