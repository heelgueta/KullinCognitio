"""
FiluSententia — LLM-based corpus analysis.

filu (snake, mapudungun) + sententia (opinion/judgement/sentence, latin)

Reads CSVs from ÑarkiMundatio (fallback: CulpemCorpus), runs
sentiment analysis, content analysis, or custom yes/no questions
through a local Ollama model, and exports an enriched CSV.
"""

import csv
import datetime
import json
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file
from flask import stream_with_context

import llm
import prompts

app = Flask(__name__)
HERE          = Path(__file__).parent.resolve()
OUTPUT_DIR    = HERE / "output"
QUESTIONS_DIR = HERE / "questions"
OUTPUT_DIR.mkdir(exist_ok=True)
QUESTIONS_DIR.mkdir(exist_ok=True)


# ── path helpers ──────────────────────────────────────────────────────────────

def find_input_dir():
    narki = [
        HERE.parent / "ÑarkiMundatio" / "output",
        HERE.parent.parent / "ÑarkiMundatio" / "output",
    ]
    for c in narki:
        if c.exists() and any(c.glob("narki_*.csv")):
            return c, "narki"

    culpem = [
        HERE.parent / "CulpemCorpus" / "output",
        HERE.parent.parent / "CulpemCorpus" / "output",
    ]
    for c in culpem:
        if c.exists() and any(c.glob("culpem_*.csv")):
            return c, "culpem"

    return None, None


def read_meta(path: Path) -> dict:
    mp = path.with_suffix(".json")
    if mp.exists():
        with open(mp, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── routes: data ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ollama_status")
def ollama_status():
    ok     = llm.available()
    models = llm.list_models() if ok else []
    return jsonify({"available": ok, "models": models,
                    "default": llm.DEFAULT_MODEL})


@app.route("/files")
def files():
    out_dir, kind = find_input_dir()
    result = []
    if out_dir:
        pattern = "narki_*.csv" if kind == "narki" else "culpem_*.csv"
        for f in sorted(out_dir.glob(pattern),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            meta = read_meta(f)
            result.append({"name": f.name, "size": f.stat().st_size,
                            "mtime": f.stat().st_mtime, "meta": meta})
    return jsonify({"files": result, "source": kind})


@app.route("/filu_files")
def filu_files():
    result = []
    for f in sorted(OUTPUT_DIR.glob("filu_*.csv"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        meta = read_meta(f)
        result.append({"name": f.name, "size": f.stat().st_size,
                        "mtime": f.stat().st_mtime, "meta": meta})
    return jsonify({"files": result})


# ── routes: question sets ─────────────────────────────────────────────────────

@app.route("/question_sets", methods=["GET"])
def list_question_sets():
    sets = []
    for f in sorted(QUESTIONS_DIR.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        sets.append(data)
    return jsonify(sets)


@app.route("/question_sets", methods=["POST"])
def save_question_set():
    data = request.get_json()
    if not data or not data.get("id") or not data.get("questions"):
        return jsonify({"error": "id and questions required"}), 400
    safe_id = "".join(c for c in data["id"] if c.isalnum() or c in "_-")[:50]
    if not safe_id:
        return jsonify({"error": "invalid id"}), 400
    data["id"] = safe_id
    with open(QUESTIONS_DIR / f"{safe_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "id": safe_id})


@app.route("/question_sets/<qs_id>", methods=["DELETE"])
def delete_question_set(qs_id):
    safe_id = "".join(c for c in qs_id if c.isalnum() or c in "_-")[:50]
    path = QUESTIONS_DIR / f"{safe_id}.json"
    if path.exists():
        path.unlink()
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


# ── route: analyse (SSE stream) ───────────────────────────────────────────────

@app.route("/analyse")
def analyse():
    filename     = request.args.get("file", "").strip()
    analysis     = request.args.get("analysis", "sentiment")   # sentiment|content|questions
    qs_id        = request.args.get("question_set", "").strip()
    model        = request.args.get("model", llm.DEFAULT_MODEL).strip()
    limit        = int(request.args.get("limit", "0"))          # 0 = all rows

    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400

    out_dir, _ = find_input_dir()
    if not out_dir:
        return jsonify({"error": "No input directory found"}), 404

    filepath = out_dir / filename
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404

    # load question set if needed
    qs_data = None
    if analysis == "questions":
        qs_path = QUESTIONS_DIR / f"{qs_id}.json"
        if not qs_path.exists():
            return jsonify({"error": f"Question set '{qs_id}' not found"}), 404
        with open(qs_path, encoding="utf-8") as f:
            qs_data = json.load(f)

    def generate():
        yield _sse({"type": "log", "level": "info",
                    "msg": f"Leyendo {filename}…"})

        try:
            with open(filepath, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        except Exception as e:
            yield _sse({"type": "log", "level": "error",
                        "msg": f"Error al leer: {e}"})
            yield _sse({"type": "done", "count": 0, "file": None})
            return

        if limit > 0:
            rows = rows[:limit]

        total = len(rows)
        yield _sse({"type": "log", "level": "info",
                    "msg": f"{total} filas · modelo: {model} · análisis: {analysis}"})

        if not llm.available():
            yield _sse({"type": "log", "level": "error",
                        "msg": "Ollama no disponible en localhost:11434. ¿Está corriendo?"})
            yield _sse({"type": "done", "count": 0, "file": None})
            return

        # build extra columns
        if analysis == "sentiment":
            extra_cols = ["title_sentiment_label", "title_sentiment_score",
                          "title_sentiment_reason",
                          "body_sentiment_label",  "body_sentiment_score",
                          "body_sentiment_reason"]
        elif analysis == "content":
            extra_cols = ["content_topic", "content_subtopics",
                          "content_entities", "content_summary"]
        else:  # questions
            extra_cols = prompts.questions_columns(qs_data["questions"])

        out_rows  = []
        error_n   = 0

        for i, row in enumerate(rows):
            title = (row.get("title") or "").strip()
            body  = (row.get("body_text") or "").strip()

            # ── run LLM ──────────────────────────────────────────────────────
            extra = {}
            if analysis == "sentiment":
                sys_p, usr_p = prompts.sentiment_prompt(title, body)
                result_t = llm.generate(model, sys_p, f"TÍTULO: {title[:600]}")
                result_b = llm.generate(model, sys_p, f"TEXTO: {body[:1200]}")
                extra.update(prompts.sentiment_extract(result_t, prefix="title"))
                extra.update(prompts.sentiment_extract(result_b, prefix="body"))

            elif analysis == "content":
                sys_p, usr_p = prompts.content_prompt(title, body)
                result = llm.generate(model, sys_p, usr_p)
                extra.update(prompts.content_extract(result))

            else:  # questions
                qs_sys = prompts.questions_system(qs_data["questions"])
                usr_p  = prompts.questions_prompt(title, body, qs_sys)[1]
                result = llm.generate(model, qs_sys, usr_p)
                extra.update(prompts.questions_extract(result, qs_data["questions"]))

            if any("error" in str(v).lower() for v in extra.values()):
                error_n += 1

            out_row = dict(row)
            out_row.update(extra)
            out_rows.append(out_row)

            # build a short result summary for the log
            if analysis == "sentiment":
                summary = (f"título: {extra.get('title_sentiment_label','')} "
                           f"({extra.get('title_sentiment_score','')}) | "
                           f"cuerpo: {extra.get('body_sentiment_label','')} "
                           f"({extra.get('body_sentiment_score','')})")
            elif analysis == "content":
                summary = extra.get("content_topic", "")
            else:
                answers = " | ".join(
                    f"{q['id']}:{extra.get(q['id']+'_answer','?')}"
                    for q in qs_data["questions"]
                )
                summary = answers

            yield _sse({
                "type":    "progress",
                "row":     i + 1,
                "total":   total,
                "title":   title[:70],
                "summary": summary,
            })

        # ── write output ──────────────────────────────────────────────────────
        job_id    = uuid.uuid4().hex[:8]
        stem      = filename.rsplit(".", 1)[0]
        out_name  = f"filu_{analysis}_{stem}_{job_id}.csv"
        out_path  = OUTPUT_DIR / out_name

        all_fields = list(rows[0].keys()) + extra_cols if rows else extra_cols
        # deduplicate preserving order
        seen = set()
        fields = [f for f in all_fields if not (f in seen or seen.add(f))]

        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(out_rows)

        meta = {
            "created_at":    datetime.datetime.utcnow().isoformat() + "Z",
            "source_file":   filename,
            "analysis":      analysis,
            "question_set":  qs_data["name"] if qs_data else None,
            "model":         model,
            "n_rows":        total,
            "n_errors":      error_n,
            "extra_columns": extra_cols,
            "file":          out_name,
        }
        with open(OUTPUT_DIR / out_name.replace(".csv", ".json"),
                  "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        yield _sse({"type": "log", "level": "ok",
                    "msg": f"✓ Listo — {total} filas, {error_n} errores → {out_name}"})
        yield _sse({"type": "done", "count": total, "errors": error_n,
                    "file": out_name})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── download ──────────────────────────────────────────────────────────────────

@app.route("/download/<filename>")
def download(filename):
    if not filename.startswith("filu_") or ".." in filename or "/" in filename:
        return "Not found", 404
    if not filename.endswith((".csv", ".json")):
        return "Not found", 404
    fp = OUTPUT_DIR / filename
    if not fp.exists():
        return "Not found", 404
    return send_file(str(fp), as_attachment=True)


def _sse(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


if __name__ == "__main__":
    app.run(debug=True, port=5006, threaded=True)
