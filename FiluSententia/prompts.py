"""
Prompt templates for FiluSententia analysis types.

Each builder returns (system_prompt, user_prompt) for a given text input.
The system prompt enforces a strict JSON schema so the LLM output is
directly parseable without post-processing.
"""

import json


# ── Sentiment ─────────────────────────────────────────────────────────────────

SENTIMENT_SYSTEM = """\
Eres un analista experto en medios de comunicación hispanohablantes.
Analiza el sentimiento del texto periodístico que se te proporciona.

Responde ÚNICAMENTE con un objeto JSON válido con exactamente estas claves:
{
  "label": "<muy_negativo | negativo | neutro | positivo | muy_positivo>",
  "score": <entero del 1 al 5>,
  "reason": "<una sola oración explicando el sentimiento>"
}

Escala de score: 1=muy negativo, 2=negativo, 3=neutro, 4=positivo, 5=muy positivo.
No incluyas texto fuera del JSON."""


def sentiment_prompt(title: str, body: str) -> tuple[str, str]:
    user = f"TÍTULO: {title}\n\nCUERPO: {body[:1200]}"
    return SENTIMENT_SYSTEM, user


def sentiment_columns() -> list[str]:
    return ["sentiment_label", "sentiment_score", "sentiment_reason"]


def sentiment_extract(result: dict, prefix: str = "") -> dict:
    p = prefix + "_" if prefix else ""
    if "_error" in result:
        return {f"{p}sentiment_label": "error", f"{p}sentiment_score": "",
                f"{p}sentiment_reason": result["_error"]}
    return {
        f"{p}sentiment_label": result.get("label", ""),
        f"{p}sentiment_score": result.get("score", ""),
        f"{p}sentiment_reason": result.get("reason", ""),
    }


# ── Content analysis ──────────────────────────────────────────────────────────

CONTENT_SYSTEM = """\
Eres un analista experto en medios de comunicación hispanohablantes.
Analiza el contenido del artículo periodístico que se te proporciona.

Responde ÚNICAMENTE con un objeto JSON válido con exactamente estas claves:
{
  "topic": "<tema principal en máximo 4 palabras>",
  "subtopics": ["<subtema1>", "<subtema2>"],
  "entities": ["<nombre1>", "<nombre2>", "<nombre3>"],
  "summary": "<resumen del artículo en una sola oración>"
}

- topic: el tema central del artículo
- subtopics: hasta 3 temas secundarios
- entities: personas, organizaciones, lugares mencionados (máximo 5)
- summary: oración completa que capture la idea principal

No incluyas texto fuera del JSON."""


def content_prompt(title: str, body: str) -> tuple[str, str]:
    user = f"TÍTULO: {title}\n\nCUERPO: {body[:1500]}"
    return CONTENT_SYSTEM, user


def content_columns() -> list[str]:
    return ["content_topic", "content_subtopics", "content_entities", "content_summary"]


def content_extract(result: dict) -> dict:
    if "_error" in result:
        return {"content_topic": "error", "content_subtopics": "",
                "content_entities": "", "content_summary": result["_error"]}
    subtopics = result.get("subtopics", [])
    entities  = result.get("entities", [])
    return {
        "content_topic":     result.get("topic", ""),
        "content_subtopics": " | ".join(subtopics) if isinstance(subtopics, list) else str(subtopics),
        "content_entities":  " | ".join(entities)  if isinstance(entities,  list) else str(entities),
        "content_summary":   result.get("summary", ""),
    }


# ── Custom questions ──────────────────────────────────────────────────────────

def questions_system(questions: list[dict]) -> str:
    schema = {
        q["id"]: {
            "answer":     "<sí | no>",
            "confidence": "<alta | media | baja>",
            "reason":     "<breve justificación>",
        }
        for q in questions
    }
    q_list = "\n".join(f"- {q['id']}: {q['text']}" for q in questions)
    return f"""\
Eres un analista experto en medios de comunicación hispanohablantes.
Responde las siguientes preguntas sobre el texto periodístico dado.

PREGUNTAS:
{q_list}

Responde ÚNICAMENTE con un objeto JSON válido con exactamente estas claves:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Para cada pregunta: answer es "sí" o "no", confidence es "alta", "media" o "baja",
reason es una frase breve que justifique la respuesta.
No incluyas texto fuera del JSON."""


def questions_prompt(title: str, body: str, qs_system: str) -> tuple[str, str]:
    user = f"TÍTULO: {title}\n\nCUERPO: {body[:1400]}"
    return qs_system, user


def questions_columns(questions: list[dict]) -> list[str]:
    cols = []
    for q in questions:
        cols += [f"{q['id']}_answer", f"{q['id']}_confidence", f"{q['id']}_reason"]
    return cols


def questions_extract(result: dict, questions: list[dict]) -> dict:
    out = {}
    for q in questions:
        qid = q["id"]
        if "_error" in result:
            out[f"{qid}_answer"]     = "error"
            out[f"{qid}_confidence"] = ""
            out[f"{qid}_reason"]     = result["_error"]
        else:
            qr = result.get(qid, {})
            out[f"{qid}_answer"]     = qr.get("answer", "")
            out[f"{qid}_confidence"] = qr.get("confidence", "")
            out[f"{qid}_reason"]     = qr.get("reason", "")
    return out
