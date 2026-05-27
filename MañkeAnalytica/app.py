"""
MañkeAnalytica — statistical analysis of press corpora.

mañke (condor, mapudungun) + analytica (analysis, latin)

Reads cleaned CSVs from ÑarkiMundatio (fallback: CulpemCorpus),
returns statistical summaries: temporal volume, word frequency,
source distribution, and article length stats.
"""

import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
HERE = Path(__file__).parent.resolve()

STOPWORDS_ES = {
    "de","la","el","en","y","a","los","las","del","se","que","un","una","con",
    "por","es","su","al","lo","mas","pero","o","este","esta","si","fue","ha",
    "para","son","como","no","le","sus","muy","entre","tambien","ser","ya","han",
    "hay","me","te","nos","les","era","ni","todo","todos","cuando","sobre","desde",
    "hasta","donde","tanto","sin","ante","tras","cada","estos","estas","aqui","asi",
    "bien","vez","dos","tres","anos","ano","dia","dias","parte","mismo","misma",
    "bajo","dentro","cual","cuales","quien","quienes","segun","ante","sin","sobre",
    "durante","mediante","hacia","contra","entre","sobre","bajo","tras","seran",
    "sera","sido","este","esta","esto","esos","esas","ese","esa","nuestro","nuestra",
    "veces","solo","solo","all","more","than","with","the","for","are","was",
}


def find_input_dir():
    narki_candidates = [
        HERE.parent / "ÑarkiMundatio" / "output",
        HERE.parent.parent / "ÑarkiMundatio" / "output",
    ]
    for c in narki_candidates:
        if c.exists() and any(c.glob("narki_*.csv")):
            return c, "narki"

    culpem_candidates = [
        HERE.parent / "CulpemCorpus" / "output",
        HERE.parent.parent / "CulpemCorpus" / "output",
    ]
    for c in culpem_candidates:
        if c.exists() and any(c.glob("culpem_*.csv")):
            return c, "culpem"

    return None, None


def read_meta(csv_path: Path) -> dict:
    mp = csv_path.with_suffix(".json")
    if mp.exists():
        with open(mp, encoding="utf-8") as f:
            return json.load(f)
    return {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/files")
def files():
    out_dir, kind = find_input_dir()
    result = []
    if out_dir:
        pattern = "narki_*.csv" if kind == "narki" else "culpem_*.csv"
        for f in sorted(out_dir.glob(pattern),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            meta = read_meta(f)
            result.append({
                "name":  f.name,
                "size":  f.stat().st_size,
                "mtime": f.stat().st_mtime,
                "meta":  meta,
            })
    return jsonify({"files": result, "source": kind})


@app.route("/analyse")
def analyse():
    filename = request.args.get("file", "").strip()
    top_n    = min(int(request.args.get("top_n", "40")), 200)

    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400

    out_dir, kind = find_input_dir()
    if not out_dir:
        return jsonify({"error": "No input directory found"}), 404

    filepath = out_dir / filename
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404

    try:
        with open(filepath, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not rows:
        return jsonify({"error": "Empty file"}), 400

    # ── temporal ──────────────────────────────────────────────────────────────
    date_counts  = Counter()
    month_counts = Counter()
    year_counts  = Counter()
    for row in rows:
        d = (row.get("date") or row.get("fecha") or "")[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}", d):
            date_counts[d]   += 1
            month_counts[d[:7]] += 1
            year_counts[d[:4]]  += 1

    # ── sources ───────────────────────────────────────────────────────────────
    source_counts = Counter(
        (row.get("source") or row.get("fuente") or "desconocido").strip()
        for row in rows
    )

    # ── article lengths (word count) ──────────────────────────────────────────
    lengths = [len((row.get("body_text") or "").split()) for row in rows]
    avg_len = round(sum(lengths) / len(lengths), 1) if lengths else 0
    buckets = {"0–50": 0, "51–150": 0, "151–300": 0, "301–500": 0, "500+": 0}
    for ln in lengths:
        if   ln <=  50: buckets["0–50"]    += 1
        elif ln <= 150: buckets["51–150"]  += 1
        elif ln <= 300: buckets["151–300"] += 1
        elif ln <= 500: buckets["301–500"] += 1
        else:           buckets["500+"]    += 1

    # ── word frequency ────────────────────────────────────────────────────────
    word_counter = Counter()
    for row in rows:
        body = (row.get("body_text") or "").lower()
        # strip accents for uniform counting
        body = "".join(
            c for c in unicodedata.normalize("NFD", body)
            if unicodedata.category(c) != "Mn"
        )
        for w in re.findall(r"\b[a-z]{3,}\b", body):
            if w not in STOPWORDS_ES:
                word_counter[w] += 1

    return jsonify({
        "n": len(rows),
        "temporal": {
            "by_date":  sorted(date_counts.items()),
            "by_month": sorted(month_counts.items()),
            "by_year":  sorted(year_counts.items()),
        },
        "sources": sorted(source_counts.items(), key=lambda x: -x[1]),
        "lengths": {
            "avg":     avg_len,
            "min":     min(lengths) if lengths else 0,
            "max":     max(lengths) if lengths else 0,
            "buckets": list(buckets.items()),
        },
        "top_words": word_counter.most_common(top_n),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5005, threaded=True)
