from app.card.schemas import CardDraft


# Символ | в значении вроде «±(1+0,003·|t|)» иначе разобьёт строку таблицы на лишние колонки.
def _table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(card: CardDraft) -> str:
    rows = "\n".join(
        f"| {_table_cell(row.name)} | {_table_cell(row.value)} |"
        for row in card.key_characteristics
    )
    queries = "\n".join(f"- {query}" for query in card.search_queries)
    tasks = "\n".join(f"- {task}" for task in card.commercial_block.tasks)
    sections = [
        f"# {card.seo_title}",
        f"## SEO-описание\n\n{card.seo_description}",
        f"## Ключевые характеристики\n\n| Характеристика | Значение |\n|---|---|\n{rows}",
        f"## Поисковые запросы\n\n{queries}",
        f"## Для менеджера\n\n**Кому подходит:** {card.commercial_block.target_audience}\n\n"
        f"**Какие задачи решает:**\n\n{tasks}",
    ]
    if card.clarifications:
        clarifications = "\n".join(f"- {item}" for item in card.clarifications)
        sections.append(f"## Требует уточнения\n\n{clarifications}")
    return "\n\n".join(sections) + "\n"
