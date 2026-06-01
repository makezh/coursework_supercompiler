import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, render_template, request, jsonify, abort, send_from_directory

from webdemo.runner import compile_all_levels, summarize_effect, list_entries


HERE = Path(__file__).resolve().parent
SAMPLES_DIR = PROJECT_ROOT / "samples"

app = Flask(__name__,
            template_folder=str(HERE / "templates"),
            static_folder=str(HERE / "static"))


def _inline_css() -> str:
    return (HERE / "static" / "styles.css").read_text(encoding="utf-8")


def _samples_list():
    if not SAMPLES_DIR.exists():
        return []
    return sorted(f.name for f in SAMPLES_DIR.glob("*.sll"))


@app.route("/")
def index():
    return render_template("index.html",
                            samples=_samples_list(),
                            inline_css=_inline_css())


@app.route("/samples")
def samples_json():
    return jsonify(_samples_list())


@app.route("/sample/<name>")
def sample_content(name):
    if not name.endswith(".sll") or "/" in name or ".." in name:
        abort(400)
    p = SAMPLES_DIR / name
    if not p.exists():
        abort(404)
    return p.read_text(encoding="utf-8"), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/entries", methods=["POST"])
def entries_endpoint():
    src = request.form.get("src", "").strip()
    if not src:
        return jsonify({"functions": [], "recommended": None})
    try:
        return jsonify(list_entries(src))
    except Exception:
        return jsonify({"functions": [], "recommended": None})


@app.route("/compile", methods=["POST"])
def compile_endpoint():
    src = request.form.get("src", "").strip()
    entry = request.form.get("entry", "main").strip()
    strategy = request.form.get("strategy", "HE")
    gen = request.form.get("gen", "BOTTOM")

    if not src:
        return "<div class='error'>Пустой код.</div>"
    if strategy not in ("HE", "TAG"):
        return "<div class='error'>Неверная стратегия.</div>"
    if gen not in ("TOP", "BOTTOM"):
        return "<div class='error'>Неверный gen.</div>"

    try:
        results = compile_all_levels(src, entry, strategy, gen, with_svg=True)
        effect = summarize_effect(results)
    except Exception as e:
        return f"<div class='error'>Не удалось запустить: {type(e).__name__}: {e}</div>"

    return render_template("_result_fragment.html",
                            results=results, effect=effect)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    print(f"Открой http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
