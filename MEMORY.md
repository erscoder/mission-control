# MEMORY.md - Harvis Long-Term Memory

*Last updated: 2026-03-17*

## About Kike

**Mission:** "Construir una organización autónoma de agentes IA que trabaja 24/7 — agentes que aprenden, generan ingresos, y crean otros agentes — hasta que mi único trabajo sea decidir qué construir."

**Company:**
- Twitter: @erscoder41567
- Email: erscoder@gmail.com

**Tech Stack:**
- Next.js, TypeScript, Tailwind
- NestJS for backends
- PostgreSQL with Prisma
- Hyperliquid for trading

---

## Preferencias (Preferences)

- **SIEMPRE hablar en español** — todos los mensajes, notificaciones, reportes, standups, nightly builds. Sin excepción. No mezclar inglés.
- Dark mode always
- **NO crear CLIs en el nightly** — Kike no los usa. Solo hacer cosas que pida explícitamente.
- Toasts over alerts
- Clean, modern UI
- README.md siempre en inglés
- UI/Dashboard siempre en inglés
- **ALL communications with companies/investors in English** (2026-02-09)

---

## 🔴 Regla Absoluta — Edición de Ficheros (2026-03-17)
**SIEMPRE usar Write y Edit para escribir/modificar ficheros. NUNCA exec para esto.**
- `Write` → crear o sobreescribir fichero completo (no hay escaping, funciona con TS/JSON/cualquier cosa)
- `Edit` → reemplazar fragmento exacto dentro de un fichero
- **NUNCA usar exec + heredoc/node/python para escribir ficheros** — rompe con comillas de TypeScript
- **NO delegar a Claude Code** si la tarea es escribir ficheros. Kike prefiere que lo haga yo directamente.

---

## 🏗️ NestJS DDD Structure — ESTÁNDAR OBLIGATORIO (2026-03-18)

**SIEMPRE usar esta estructura para todos los proyectos NestJS:**

```
src/
├── main.ts
├── app.module.ts
├── common/           # decorators, dto, exceptions, filters, interceptors
├── config/           # ConfigModule → configuration.ts
├── modules/          # Bounded contexts (cada módulo = dominio)
│   └── <domain>/
│       ├── application/
│       │   ├── services/       # Orquesta use-cases + repos
│       │   ├── use-cases/      # Comandos y queries (opcional)
│       │   └── dtos/           # DTOs entrada/salida
│       ├── domain/
│       │   ├── entities/       # Entidades ricas (con comportamiento)
│       │   ├── value-objects/  # VOs inmutables
│       │   ├── repositories/   # Interfaces (puertos) para DI
│       │   ├── events/         # Domain events
│       │   └── exceptions/
│       ├── infrastructure/
│       │   ├── persistence/    # Implementaciones de repos (TypeORM/Prisma)
│       │   └── external/       # Integraciones externas
│       ├── interfaces/
│       │   └── http/           # Controllers
│       └── <domain>.module.ts  # DI wiring
└── shared/           # Módulos reutilizables (database, logger, auth)
```

**Reglas:**
- `domain/` = puro negocio, sin dependencias externas
- `domain/repositories/` = interfaces (puertos) — implementación en `infrastructure/`
- DI: inyectar por interface token, implementar en infrastructure
- NO mezclar lógica de negocio en controllers ni en infrastructure

## How I Work

### 🧪 Tests Obligatorios (2026-02-19) — REGLA ABSOLUTA
**SIEMPRE hacer tests. Cobertura mínima 90%. Sin excepción.**

---

## Índice de Temas Detallados

Cada tema importante tiene su propio archivo en `memory/topics/`:

1. **projects.md** — Proyectos activos y su estado
2. **polymarket.md** — Reglas específicas de trading en Polymarket
3. **testing.md** — Reglas de testing y cobertura
4. **github.md** — Operaciones con GitHub
5. **linkedin.md** — Guía de posts en LinkedIn

Para acceder a un tema específico, usa `read memory/topics/<archivo>.md`

---

## Nexus Project — Current Status (2026-03-24)

**Sprint 8 — Dashboard: ✅ COMPLETE**
- Next.js 15 + TypeScript + HeroUI v3 (full component library)
- Real-time WebSocket dashboard with Socket.IO
- Components:
  - P&L chart with Recharts (portfolio history)
  - Positions table (OPEN/CLOSED with PnL %)
  - Alerts list with severity filtering (INFO/WARNING/CRITICAL)
  - Status card with Orchestrator control buttons
- Backend:
  - DashboardGateway WebSocket (positions/alerts/portfolio updates)
  - PortfolioService + PortfolioHistory entity
  - PositionService + Position entity
  - AlertService + Alert entity
  - New API endpoints for dashboard data
- All deps installed, migration ready
- SETUP.md documentation complete
- Ready for S10: Paper Trading Live (30-day validation)

**Tech Stack:**
- Frontend: Next.js 15, HeroUI v3, Recharts, Zustand, Socket.IO
- Backend: NestJS, TypeORM, PostgreSQL, Redis, BullMQ
- Tests: Mocha, Chai, 97%+ coverage

**Next: S10 — Paper Trading Live (30 days validation with Alpaca)**

---

## Docker — Regla (2026-03-21)
**SIEMPRE usar `docker compose up -d` para levantar proyectos dockerizados.**
- Nunca usar `docker run` directo — no monta ports, volumes ni env correctamente
- Para parar: `docker compose down`
- Para rebuild: `docker compose build` luego `docker compose up -d`
- Para override de env en live: editar `.env` antes de `docker compose up -d`

## Twitter Style Rules (2026-03-10)
- **Sin em dash (`—`)** — suena a IA. Usar punto y frase nueva.
  ❌ `Don't trade — holding cash is a position`
  ✅ `Don't trade. Holding cash is a position.`
- **Frases acabadas en punto**
- Delays entre posts: mínimo 2-3 minutos para parecer orgánico
