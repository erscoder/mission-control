# Synapse Network — Plan de Proyecto
> Análisis completo + roadmap detallado
> Generado por Harvis (Opus 4.6) · 2026-03-10

---

## 🏷️ Nombre del Producto

**"agents-layer"** como carpeta está bien, pero como producto es genérico.

**Propuesta: `Synapse`**
- Token: **$SYN** (Solana)
- Tagline: *"The compute layer for autonomous agents"*
- Por qué: conexión neuronal, señal entre nodos, veloz, memorable, técnico sin ser críptico

Alternativas:
- **Axon** — conducción de señal, corto, sci-fi
- **Pulsar** — "compute pulses", distributed feel
- **Lattice** — red descentralizada, clean

---

## 🔍 ¿Qué construimos?

Una **red P2P de compute para agentes IA** con token Solana:

- Cualquier persona con GPU/CPU contribuye compute → **gana $SYN**
- Agentes IA (como los nuestros) ejecutan inference en la red → **pagan $SYN**
- Verificación descentralizada (nadie puede hacer trampa)
- **Diferenciador vs Hyperspace**: valor económico real desde día 1 (token Solana, no puntos internos)

---

## 📊 Análisis de Complejidad Honesto

### Los 7 componentes clave

```
COMPONENTE                    DIFICULTAD    TIEMPO      NOTAS
──────────────────────────────────────────────────────────────────
1. P2P networking (libp2p)    🔴 MUY ALTA   6-10 sem    El mayor cuello de botella
2. Verification protocol       🟠 ALTA       4-6 sem     Merkle trees, commit-reveal
3. Solana smart contracts      🟠 ALTA       4-6 sem     SPL token + staking + escrow
4. Node software (inference)   🟡 MEDIA      3-4 sem     Wraps Ollama, ya existe
5. Dashboard / Frontend        🟡 MEDIA      3-4 sem     React, mucho es UI
6. Inference routing           🟡 MEDIA      2-3 sem     Versión simple sin ML
7. Research system (DiLoCo)    🔴 MUY ALTA   8-12 sem    ML distribuido → FASE 3
──────────────────────────────────────────────────────────────────
TOTAL MVP (sin DiLoCo)                       ~6 meses    1-2 devs a tiempo completo
```

### ¿Somos capaces?

**Sí. Con estas condiciones:**

1. **No replicamos Hyperspace completo** — construimos un MVP estratégico en fases
2. **Usamos libp2p-js** (open source, misma librería que Hyperspace) — no reinventamos la P2P layer
3. **Simplificamos la verificación en v1**: challenge-response antes de Merkle proofs completos
4. **DiLoCo en Fase 3** — el valor core es el compute marketplace, no el research
5. **Solana es nuestro diferenciador** — token real desde día 1 vs puntos internos de Hyperspace

**Lo que tenemos a favor:**
- Stack NestJS/TypeScript dominado (bots como base de referencia)
- Experiencia con WebSockets, APIs externas, sistemas distribuidos
- Conocimiento de Solana (via Polymarket/Hyperliquid)
- Genesis como plataforma de orquestación de agentes ya en desarrollo
- Los agentes actuales (Matías, Diego, Marcus) como primeros clientes de la red
---

## 🗺️ Roadmap por Fases

### FASE 1 — Foundation (Semanas 1-8) — MVP Compute Marketplace

**Objetivo:** Red funcional con nodos reales, token real, pagos reales.

#### Sprint 1-2: Solana Token + Smart Contracts
```
- SPL Token: $SYN (mint, supply, decimals)
- Escrow contract: agente deposita $SYN → nodo recibe al completar trabajo
- Staking contract: nodos stakean $SYN como garantía (penaliza mal comportamiento)
- Settlement: pago automático on-chain tras verificación
- Stack: Anchor (Rust), Solana Devnet → Mainnet
```

#### Sprint 3-4: Node Software
```
- CLI: synapse start --inference / --embedding / --cpu
- Wrapper sobre Ollama (auto-detecta modelos disponibles)
- Registro en la red (keypair Ed25519, capabilities, hardware tier)
- Heartbeat / presence reporting
- Stack: TypeScript / Node.js, node-llama-cpp, Ollama SDK
```

#### Sprint 5-6: Coordinación (versión simplificada, sin P2P full)
```
- Coordinador central ligero (irá a P2P en Fase 2, no antes)
  → Registro de nodos (pubkey, capabilities, tier, uptime)
  → Matchmaking: agente pide inference → asigna mejor nodo disponible
  → Work receipts: agente + nodo firman el trabajo completado
- Verificación v1: challenge simple (nodo responde prompt de verificación)
- Stack: NestJS + PostgreSQL (temporal, reemplazado por P2P en Fase 2)
```

#### Sprint 7-8: Dashboard + Launch
```
- Dashboard: nodos activos, earnings, leaderboard, tu nodo
- Feed de actividad (como el de Hyperspace)
- Documentación: cómo instalar, cómo ganar
- Devnet launch con early adopters
```

**Entregable Fase 1:** Red funcional en Solana Devnet, 10-50 nodos beta, token circulando.

---

### FASE 2 — Decentralization (Semanas 9-18)

**Objetivo:** Eliminar el coordinador central. Red verdaderamente P2P.

#### Sprint 9-12: P2P Layer (libp2p)
```
- Migrar coordinador a libp2p-js
  → GossipSub para broadcast de resultados y descubrimiento
  → DHT para registro de nodos (sin servidor central)
  → Circuit Relay para NAT traversal (nodos detrás de firewall)
- Bootstrap nodes: 3 nodos geográficos (US, EU, Asia)
- Peer discovery: nodo nuevo encuentra red via bootstrap
```

#### Sprint 13-15: Verification Protocol (Commit-Reveal completo)
```
- Pulse rounds: cada ~90s
  1. ELECT → líder determinístico por hash(peerIDs + seed)
  2. SEED → broadcast via GossipSub
  3. COMPUTE → matriz 2048×512 desde seed
  4. COMMIT → publica Merkle root
  5. CHALLENGE → índices aleatorios de filas
  6. PROVE → pruebas Merkle de esas filas
  7. VERIFY → validación 3-tier + Ed25519
- Strike system: nodos que fallan pierden puntos + staking penalizado
- WASM acceleration para pruebas (misma que Hyperspace)
```

#### Sprint 16-18: Liveness Multiplier + Staking Economics
```
- LM formula: igual que Hyperspace pero parametrizable via governance
- Staking tiers: más stake = mayor tier = mayor LM ceiling
- Slashing: nodos maliciosos pierden % del stake on-chain
- Mainnet launch: token listing, primera liquidez
```

**Entregable Fase 2:** Red P2P real, sin coordinador central, Mainnet live.

---

### FASE 3 — Intelligence (Semanas 19-30)

**Objetivo:** Añadir el research system distribuido (nuestro DiLoCo).

```
- Distributed ML research: nodos corren experimentos y comparten via GossipSub
- No solo astrophysics: el corpus puede ser cualquier dominio (crypto, finanzas, código)
- Hipótesis: nuestros agentes (Matías, Diego) podrían mejorar sus propias estrategias
  automáticamente via esta red
- Peer review system: nodos evalúan outputs de otros nodos
- CRDT leaderboard: sin servidor, conflicto-free
- Token incentive para research: mejores descubrimientos = mayor $SYN reward
```

---

## 🏗️ Arquitectura Técnica

```
┌─────────────────────────────────────────────────────────────┐
│                     APLICACIONES                            │
│  Web Dashboard · CLI Node · Browser Node · Agent SDK        │
├─────────────────────────────────────────────────────────────┤
│                      SERVICIOS                              │
│  InferenceRouter · PulseCoordinator · WorkVerifier          │
│  StakingManager · RewardCalculator · NodeRegistry           │
├─────────────────────────────────────────────────────────────┤
│                       RED P2P                               │
│  libp2p · GossipSub · DHT · Circuit Relay                   │
│  Bootstrap Nodes (US/EU/Asia)                               │
├─────────────────────────────────────────────────────────────┤
│                     BLOCKCHAIN                              │
│  Solana Mainnet · Anchor Programs                           │
│  $SYN SPL Token · Escrow · Staking · Settlement             │
├─────────────────────────────────────────────────────────────┤
│                      COMPUTE                                │
│  Ollama · node-llama-cpp · ONNX (embeddings)                │
│  WASM Pulse (proof-of-work)                                 │
└─────────────────────────────────────────────────────────────┘
```

### Solana Programs (Smart Contracts)

```rust
// 1. Token Program (SPL)
// $SYN mint, decimals, supply inicial

// 2. Staking Program
struct StakeAccount {
    owner: Pubkey,
    amount: u64,        // $SYN stakeados
    tier: u8,           // 0-5 según VRAM declarada
    lm: f64,            // Liveness Multiplier actual
    strikes: u8,        // en ventana 24h
    locked_until: i64,  // no se puede unstakear antes
}

// 3. Work Escrow Program
struct WorkOrder {
    requester: Pubkey,
    provider: Pubkey,
    amount: u64,        // $SYN en escrow
    model: String,      // modelo solicitado
    deadline: i64,      // timestamp límite
    status: WorkStatus, // pending | completed | failed | disputed
}

// 4. Reward Program
// Distribución automática de presence points → $SYN
// cada epoch (~90s), proporcional a LM × C × uptime
```

---

## 💰 Tokenomics $SYN

```
Supply total: 1,000,000,000 $SYN (1B)

Distribución:
  40% → Node rewards (liberación gradual 4 años)
  20% → Equipo (vesting 2 años, cliff 6 meses)
  15% → Inversores semilla (vesting 18 meses)
  15% → Ecosistema / grants / partnerships
  10% → Liquidez inicial (DEX en Solana: Raydium / Orca)

Earning model (nodo típico 24h, 16GB VRAM, día 30):
  Presence: ~800 $SYN/día
  Work (inference): variable, ~200-500 $SYN/día según carga
  Total: ~1,000-1,300 $SYN/día

Demand sinks (por qué el token tiene valor):
  - Agentes pagan $SYN por inference
  - Staking obligatorio para ser nodo (lock $SYN)
  - Governance: $SYN vota parámetros de red
  - Burn: % de cada work order se quema
```

---

## ⚡ Stack Tecnológico

```
Backend / Node Software:
  - TypeScript / Node.js (ya dominamos)
  - NestJS para coordinador Fase 1
  - libp2p-js para P2P Fase 2
  - Ollama SDK + node-llama-cpp

Blockchain:
  - Solana + Anchor (Rust)
  - @solana/web3.js para integraciones
  - SPL Token standard

Frontend / Dashboard:
  - Next.js + TypeScript
  - Tailwind CSS
  - Recharts para métricas
  - WalletConnect (Phantom, Solflare)

Infraestructura:
  - Bootstrap nodes: 3 VPS mínimo (Hetzner / Fly.io)
  - Supabase para sync inicial (como hace Hyperspace)
  - GitHub para experiment results (Fase 3)

Verificación / Crypto:
  - WASM para Merkle proof computation
  - Ed25519 (libp2p nativo)
  - SHA-256 domain separation
```

---

## 🎯 Ventajas Competitivas vs Hyperspace

| Factor | Hyperspace | Synapse |
|--------|-----------|---------|
| **Token** | Puntos internos (promesa futura) | $SYN en Solana desde día 1 |
| **Settlement** | Centralizado (Hyperspace decide) | On-chain automático |
| **Governance** | Ninguna | $SYN holders votan |
| **Vertical** | Astrophysics ML research | Compute para agentes IA (más amplio) |
| **Integración** | Standalone | Integrado con Genesis/AgentForge |
| **Transparencia** | Puntos en base de datos propia | Todo on-chain, auditable |

---

## ⚠️ Riesgos y Mitigaciones

```
RIESGO                          PROBABILIDAD  IMPACTO   MITIGACIÓN
────────────────────────────────────────────────────────────────────
P2P networking más duro de lo   Alta          Alto      Fase 1 con coordinador central
esperado                                                 (técnicamente "trampa" pero
                                                         viable para MVP)

Solana congestion / fees        Media         Medio     Batching de settlements,
                                                         off-chain accounting + settle weekly

Sybil attacks (nodos falsos)    Alta          Alto      Staking obligatorio + Merkle
                                                         proof-of-work hace el sybil caro

Regulación (es un token)        Media         Alto      Legal opinion antes de TGE,
                                                         utilidad clara (no especulativa)

Hyperspace nos copia la idea    Baja          Medio     Ellos ya tienen mucho camino
de Solana                                               hecho con Ethereum/Base

Poca demanda inicial            Media         Alto      Nuestros propios bots como
                                                         primeros clientes (Matías/Diego)
```

---

## 📅 Timeline Resumido

```
Mes 1-2:  Solana contracts + CLI node básico + dashboard
Mes 3-4:  Devnet launch + early adopters + verification simple
Mes 5-6:  P2P migration (libp2p) + Mainnet
Mes 7-9:  Staking economics + TGE ($SYN listing)
Mes 10+:  Research system (DiLoCo), governance, scaling
```

---

## 🚀 Primeros Pasos (esta semana)

1. **Nombre final**: ¿Synapse, Axon, Lattice? → registrar dominio
2. **Repositorio**: `synapse-network` (monorepo)
   - `/packages/contracts` — Anchor programs
   - `/packages/node` — CLI node software
   - `/packages/dashboard` — Next.js frontend
   - `/packages/sdk` — SDK para agentes que usan la red
3. **Prototipo Solana**: SPL token $SYN en Devnet (1 día)
4. **CLI node v0.1**: `synapse start` que conecta a un coordinador simple (1 semana)

---

## 💡 Insight Clave

> Hyperspace tiene 2.3M agentes pero **cero valor económico real** para los operadores hoy.
> Los puntos son promesas. $SYN en Solana desde día 1 es la propuesta diferencial.
> Si llegamos antes de que conviertan sus puntos a token, ganamos la narrativa.

---

*Plan generado por Harvis con modelo Opus 4.6 · agents-layer project · 2026-03-10*
