#!/usr/bin/env python3
"""
process_bookmarks.py — Process raw bookmarks with LLM and update wiki articles.
Usage: python scripts/process_bookmarks.py [--since YYYY-MM-DD]
"""

import argparse
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from anthropic import Anthropic

# LLM client
anthropic = Anthropic()
MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096

# Wiki categories mapping
WIKI_CATEGORIES = {
    "ai-llm": ["llm", "large language model", "gpt", "claude", "gemini", "openai",
               "anthropic", "prompting", "prompt engineering", "model", "embedding"],
    "ai-agents": ["agent", "autonomous", "agentic", "crewai", "langgraph", "langchain",
                 "mempalace", "swarm", "multi-agent", "agent loop"],
    "javascript-typescript": ["javascript", "typescript", "node", "npm", "deno", "bun",
                              "ecmascript", "v8", "runtime"],
    "react-nextjs": ["react", "next.js", "nextjs", "jsx", "tsx", "server components",
                     "rsc", "remix", "vite", "component"],
    "backend-databases": ["api", "rest", "graphql", "database", "postgresql", "mysql",
                          "mongodb", "redis", "prisma", "orm", "backend", "server"],
    "dev-tools": ["vscode", "cursor", "github", "git", "docker", "terminal", "cli",
                  "tool", "ide", "debugging", "testing", "playwright", "pytest"],
    "architecture": ["architecture", "clean code", "ddd", "domain driven", "microservice",
                    "monolith", "design pattern", "solid", "cqrs", "event sourcing"],
    "css-design": ["css", "tailwind", "styled-components", "design system", "ui",
                   "ux", "animation", "responsive"],
    "linux-devops": ["linux", "ubuntu", "docker", "kubernetes", "k8s", "bash",
                     "shell", "devops", "ci/cd", "nginx", "cloud", "aws", "gcp"],
    "career": ["career", "job", "interview", "productivity", "remote work",
               "freelance", "developer life", "team"],
    "business": ["business", "startup", "indie hacker", "saas", "monetize",
                 "revenue", "growth", "marketing"],
    "content-creation": ["youtube", "blog", "twitter", "linkedin", "content",
                         "creator", "post", "video", "podcast"],
}


def load_prompt(category: str, bookmarks: list[dict], existing_content: str = "") -> str:
    """Build the prompt for the LLM."""

    bookmarks_text = "\n\n".join([
        f"""### Tweet {i+1}
- Autor: {b.get('author', 'N/A')}
- Fecha: {b.get('datetime', 'N/A')}
- Texto: {b.get('text', '')}
- Links: {', '.join(b.get('links', [])[:3])}
- Stats: ❤️ {b.get('like_count', '?')} 🔁 {b.get('retweet_count', '?')}
"""
        for i, b in enumerate(bookmarks)
    ])

    return f"""Eres el editor de una wiki personal. El usuario guarda tweets sobre desarrollo de software y IA.

Tu trabajo: Procesar estos tweets y actualizar el artículo wiki de la categoría "{category}".

## Artículo wiki actual (si existe)

{existing_content or "(nuevo artículo)"}

---

## Tweets a procesar

{bookmarks_text}

---

## Instrucciones

1. Lee el artículo wiki actual y los tweets
2. Añade los insights nuevos de los tweets al artículo:
   - Nuevos conceptos → sección "Conceptos clave"
   - Recursos útiles → sección "Recursos destacados"
   - Lo más reciente → sección "Último ingressado"
3. Si un concepto ya existe, enriquece la entrada existente en vez de duplicar
4. Mantén el mismo formato y estructura del artículo
5. Devuelve el artículo wiki COMPLETO actualizado

## Formato del artículo

```markdown
# [Categoría] — Wiki

**Última actualización:** YYYY-MM-DD
**Fuentes procesadas:** N

---

## Resumen ejecutivo

<!-- 2-3 líneas con el estado actual del tema -->

---

## Conceptos clave

### [Concepto]

**Definición:** ...

**Fuente:** [autor — fecha](url)

---

## Recursos destacados

| Recurso | Descripción | Autor |
|---------|-------------|-------|
| [Nombre](url) | Descripción | @autor |

---

## Último ingressado

- YYYY-MM-DD: [descripción](url) — @autor

---

## Ideas de contenido

- [ ] Idea 1

---

## Conexiones con otros artículos

- [[ai-agents.md]]
- [[react-nextjs.md]]

---

*Generado automáticamente por Harvis Brain.*
```

# --- Output format: JUST the markdown content, nothing else ---


def classify_bookmarks(bookmarks: list[dict]) -> dict[str, list[dict]]:
    """Classify bookmarks into wiki categories using keyword matching (fast) + LLM (for ambiguous)."""

    categorized = {cat: [] for cat in WIKI_CATEGORIES}
    categorized["uncategorized"] = []

    for bookmark in bookmarks:
        text = (bookmark.get("text", "") + " " + " ".join(bookmark.get("links", []))).lower()
        matched = False

        for category, keywords in WIKI_CATEGORIES.items():
            for kw in keywords:
                if kw.lower() in text:
                    categorized[category].append(bookmark)
                    matched = True
                    break
            if matched:
                break

        if not matched:
            categorized["uncategorized"].append(bookmark)

    return categorized


def update_wiki_article(category: str, content: str) -> None:
    """Write updated content to the wiki article."""

    wiki_file = Path(f"wiki/{category}.md")
    wiki_file.parent.mkdir(parents=True, exist_ok=True)
    wiki_file.write_text(content, encoding="utf-8")
    print(f"  [+] Updated: {wiki_file}")


def process_with_llm(categorized: dict[str, list[dict]]) -> dict[str, int]:
    """Send each category's bookmarks to LLM for wiki update."""

    results = {}

    for category, bookmarks in categorized.items():
        if not bookmarks or category == "uncategorized":
            continue

        wiki_file = Path(f"wiki/{category}.md")
        existing = wiki_file.read_text() if wiki_file.exists() else ""

        print(f"\n[*] Processing {len(bookmarks)} bookmarks for [[{category}]]...")

        prompt = load_prompt(category, bookmarks[:20], existing)  # Max 20 per batch

        try:
            response = anthropic.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])

            # Extract markdown between code blocks if present
            code_blocks = re.findall(r"```(?:markdown)?\n(.*?)```", content, re.DOTALL)
            if code_blocks:
                content = code_blocks[0]

            update_wiki_article(category, content)
            results[category] = len(bookmarks)

        except Exception as e:
            print(f"  [!] LLM error for {category}: {e}")
            results[category] = 0

    return results


def main():
    parser = argparse.ArgumentParser(description="Process bookmarks and update wiki")
    parser.add_argument("--since", type=str, default=None,
                        help="Process bookmarks newer than YYYY-MM-DD")
    parser.add_argument("--category", type=str, default=None,
                        help="Process only one category")
    args = parser.parse_args()

    # Load bookmarks
    bookmarks_file = Path("raw/x-bookmarks/bookmarks.json")
    if not bookmarks_file.exists():
        print("[!] No bookmarks.json found. Run scrape_x_bookmarks.py first.")
        return

    bookmarks = json.loads(bookmarks_file.read_text())

    if args.since:
        cutoff = datetime.fromisoformat(args.since)
        bookmarks = [
            b for b in bookmarks
            if datetime.fromisoformat(b["scraped_at"].replace("Z", "+00:00")) >= cutoff
        ]

    print(f"[*] Processing {len(bookmarks)} bookmarks...")

    # Classify
    categorized = classify_bookmarks(bookmarks)

    if args.category:
        if args.category not in categorized:
            print(f"[!] Unknown category: {args.category}")
            return
        categorized = {args.category: categorized[args.category]}

    # Print summary
    for cat, items in categorized.items():
        if items:
            print(f"  {cat}: {len(items)} bookmarks")

    # Process with LLM
    results = process_with_llm(categorized)

    print("\n[*] Done!")
    total = sum(results.values())
    print(f"    Updated {total} bookmarks across {len(results)} categories")


if __name__ == "__main__":
    main()
