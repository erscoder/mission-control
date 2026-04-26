#!/usr/bin/env python3
"""
lint_wiki.py — Weekly wiki linting
Detecta duplicados entre artículos y sugiere reorganizaciones.
Run: python scripts/lint_wiki.py
"""

import re
from collections import defaultdict
from pathlib import Path

WIKI_DIR = Path("wiki")


def get_article_words(article_path: Path) -> set[str]:
    """Extract meaningful words from an article (excluding common stopwords)."""
    content = article_path.read_text()
    # Remove markdown syntax
    content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
    content = re.sub(r'[#*`>\-|]', ' ', content)
    content = re.sub(r'\d+', '', content)
    words = content.lower().split()
    stopwords = {
        'el', 'la', 'los', 'las', 'de', 'en', 'y', 'a', 'es', 'un', 'una',
        'para', 'con', 'por', 'que', 'se', 'del', 'al', 'lo', 'como',
        'más', 'pero', 'son', 'tiene', 'este', 'esta', 'ser', 'estar',
        '生成', 'automaticamente', 'harvis', 'brain', 'última', 'actualización',
        'fuentes', 'procesadas', 'resumen', 'ejecutivo', 'conceptos', 'clave',
        'recursos', 'destacados', 'último', 'ingressado', 'ideas', 'contenido',
        'conexiones', 'otros', 'artículos', 'markdown',
    }
    return {w for w in words if len(w) > 3 and w not in stopwords}


def lint_articles() -> dict:
    """Lint all wiki articles for issues."""

    articles = list(WIKI_DIR.glob("*.md"))
    results = {
        "duplicates": [],
        "suggestions": [],
        "orphan_concepts": defaultdict(list),
        "stats": {}
    }

    # Check for duplicates between articles
    article_words = {}
    for article in articles:
        words = get_article_words(article)
        article_words[article.name] = words

    for i, (name_a, words_a) in enumerate(article_words.items()):
        for name_b, words_b in list(article_words.items())[i+1:]:
            overlap = words_a & words_b
            if len(overlap) > 20:  # Threshold for significant overlap
                results["duplicates"].append({
                    "article_a": name_a,
                    "article_b": name_b,
                    "overlapping_words": sorted(overlap)[:15],
                    "overlap_count": len(overlap)
                })

    # Check each article for structural issues
    for article in articles:
        content = article.read_text()

        # Check for missing sections
        has_resumen = bool(re.search(r'##?\s*Resumen', content))
        has_conceptos = bool(re.search(r'##?\s*Conceptos', content))
        has_recursos = bool(re.search(r'##?\s*Recursos', content))

        if not has_resumen or not has_conceptos:
            results["suggestions"].append({
                "article": article.name,
                "issue": "Missing standard sections",
                "fix": "Add ## Resumen ejecutivo and ## Conceptos clave"
            })

        # Check for orphaned mentions (topics in other articles but no own article)
        mentioned_topics = re.findall(r'\[\[([^\]]+)\]\]', content)
        for mention in mentioned_topics:
            target = f"{mention}.md" if not mention.endswith('.md') else mention
            target_path = WIKI_DIR / target
            if not target_path.exists():
                results["orphan_concepts"][article.name].append(mention)

    # Stats
    results["stats"] = {
        "total_articles": len(articles),
        "total_lines": sum(1 for a in articles for _ in a.read_text().splitlines()),
        "articles_with_resumen": sum(1 for a in articles if re.search(r'##?\s*Resumen', a.read_text())),
    }

    return results


def main():
    print("[*] Running wiki lint...")

    results = lint_articles()

    print(f"\n[*] Stats: {results['stats']['total_articles']} artículos, "
          f"{results['stats']['total_lines']} líneas")

    if results["duplicates"]:
        print(f"\n[!] {len(results['duplicates'])} pares con posible duplicado:")
        for d in results["duplicates"]:
            print(f"  - {d['article_a']} ↔ {d['article_b']} "
                  f"({d['overlap_count']} palabras en común)")

    if results["suggestions"]:
        print(f"\n[!] {len(results['suggestions'])} sugerencias:")
        for s in results["suggestions"]:
            print(f"  - {s['article']}: {s['fix']}")

    if results["orphan_concepts"]:
        print(f"\n[!] Temas mencionados sin artículo propio:")
        for article, concepts in results["orphan_concepts"].items():
            print(f"  - {article} menciona: {', '.join(concepts)}")

    if not any([results["duplicates"], results["suggestions"], results["orphan_concepts"]]):
        print("\n[+] Wiki clean. No issues found.")

    # Save report
    from datetime import datetime
    import json

    report_file = Path(f"outputs/lint-{datetime.now().strftime('%Y-%m-%d')}.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(results, indent=2))
    print(f"\n[+] Report saved: {report_file}")


if __name__ == "__main__":
    main()
