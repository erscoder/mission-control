# memory/roadmap.md

> Last updated: 2026-04-07
> **Sirve a:** Harvis + Sentinel/Henry (HIM — Henry Intelligent Machines)

## 🎯 Objetivos Financieros (2026)

| Métrica | Valor |
|---------|-------|
| **Ingreso actual** | Bots (Poly-weather-bot dry-run, Marcus, Diego) |
| **Necesidad mensual** | 3.000 € |
| **Meta 2026** | 100.000 € |
| **Estado actual** | 🟢 CON FUNDING — construir HIM |

**Runway:** Con pre-seed funding. Construir HIM hasta product-market fit.

## 🏠 Objetivo Final

**Comprar casa** — salir del alquiler (que es "tirar dinero").

**Qué significa "tranquilo":** 3.000 €/mes sostenibles + ingresos extra para acelerar.

## 📋 Roadmap Priorizado

### 1. Synapseia — 🟡 GRAN APUESTA
- **Status:** En desarrollo
- **Cómo genera dinero:** Token SYN (red P2P de agentes)
- **Potencial:** Si funciona = dinero para la casa directamente
- **Riesgo:** No está funcionando aún, queda camino
- **Nota:** Hay que seguir buscando ingresos paralelos mientras madura

### 2. Diego — 🟢ESPERANZA CORTA PLAZO
- **Status:** Operativo
- **Winrate:** 95% (verificando esta semana)
- **Potencial:** Si mantiene el ritmo = tranquilidad mensual
- **Riesgo:** 1 semana de datos, muestra pequeña

### 3. Marcus — 🟡 LARGO PLAZO
- **Status:** Operativo
- **Estrategia:** Esperar zonas de entrada clave (no hace trades constantemente)
- **Genera:** Poco ahora mismo (by design)
- **Potencial:** Zona de entrada clave = impacto grande

### 4. Poly-weather-bot
- **Status:** 🟡 Pruebas
- **Cómo genera dinero:** Signals Polymarket
- **Bloqueador:** Fase test, sin salir a producción

## ⚡ Inquietudes

- [ ] Construir Henry Loop: RESEARCH → MATCH → BUILD → APPROVE → DEPLOY
- [ ] Definir modelo de monetización de HIM
- [ ] Poly-weather-bot llevar a producción
- [ ] Synapseia: gran apuesta, token SYN podría dar para la casa

## 📊 Métricas de Éxito

| Nivel | Criterio |
|-------|----------|
| **Win diario** | Ganar dinero cada día |
| **Win mensual** | 3.000 € netos (sostenidos) |
| **Win 2026** | 100.000 € acumulados |
| **Win vitalicio** | Casa propia (sin alquiler) |

**Regla:** No basta ganar — hay que **conseguirlo sin perderlo luego**. Ganancias sostenidas > spikes.

---

## 🔗 HIM / Henry — Arquitectura (2026-04-07)

```
Henry (Sentinel)
  ├── RESEARCH agents — scouting 24/7, building opportunity DB
  ├── KNOWLEDGE engine — user profile (interests, skills, assets)
  ├── MATCH system — RAG over opportunities + user profile
  ├── BUILD agents — create micro-business drafts
  └── APPROVAL layer — user controls everything

Stack:
  LangGraph + LangChain + MemPalace (AAAK) + ChromaDB + Telegram
```

**Docs:**
- `~/clawd/projects/sentinel/SOUL.md` — Henry identity
- `~/clawd/projects/sentinel/docs/HIM.md` — full product vision
- `~/clawd/projects/sentinel/memory/roadmap.md` — technical roadmap

**Para arrancar:**
```bash
cd ~/clawd/projects/sentinel && make run
```

---

## 🎯 Henry Loop — Criterios de aceptación

**Antes de construir cualquier cosa:**
1. ¿Genera valor económico real para alguien?
2. ¿Henry puede hacerlo sin intervención constante?
3. ¿El usuario approve todo antes de ejecutar?
4. ¿Es genuino — no slop?

**Qué NO construir:**
- AI slop que daña la marca Henry
- Cosas que no se pueden validar rápido
- Productos para usuarios que no pueden approve

---

## 🧠 Análisis Harvis

**Problema core:** Sin flujo predecible de 3k/mes.

**Lo que hay:**
- 🟢 **Diego** — 95% WR, esta semana decide
- 🟡 **Marcus** — lento por diseño, espera zonas clave
- 🟡 **Poly-weather** — en test
- 🟡 **Synapseia** — gran apuesta, el token SYN podría dar para la casa

**La situación:** HIM tiene funding. Objetivo: hacer que Henry funcione como product. Synapseia es la carta winners a largo plazo. Diego y Marcus dan estabilidad corta.
