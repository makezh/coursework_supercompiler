import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from webdemo.runner import compile_all_levels, auto_detect_entry, summarize_effect


HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"


def _env():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=False, lstrip_blocks=False,
    )
    return env


def _inline_css() -> str:
    return (STATIC / "styles.css").read_text(encoding="utf-8")


def render_report(src: str, entry: str, strategy: str, gen_type: str,
                   source_label: str = "") -> str:
    results = compile_all_levels(src, entry, strategy, gen_type, with_svg=True)
    effect = summarize_effect(results)
    env = _env()
    tpl = env.get_template("report.html")
    title = source_label or "Программа"
    return tpl.render(
        title=title,
        entry=entry,
        strategy=strategy,
        gen_type=gen_type,
        src=src,
        results=results,
        effect=effect,
        source_label=source_label,
        inline_css=_inline_css(),
    )


def _build_one(input_path: Path, out_path: Path, entry: str | None,
               strategy: str, gen_type: str) -> str:
    src = input_path.read_text(encoding="utf-8")
    chosen_entry = entry or auto_detect_entry(src) or "main"
    html = render_report(src, chosen_entry, strategy, gen_type,
                          source_label=input_path.name)
    out_path.write_text(html, encoding="utf-8")
    return chosen_entry


def main():
    p = argparse.ArgumentParser(
        description="Сборка HTML-отчёта по SLL-программе (все 4 уровня формата)."
    )
    p.add_argument("input", nargs="?", help="Путь к .sll файлу")
    p.add_argument("--entry", help="Имя точки входа (если не указано — автоопределение)")
    p.add_argument("-s", "--strategy", choices=["HE", "TAG"], default="HE")
    p.add_argument("-g", "--gen", choices=["TOP", "BOTTOM"], default="BOTTOM")
    p.add_argument("-o", "--out", help="Путь к выходному HTML")
    p.add_argument("--all", action="store_true",
                    help="Прогнать все samples/*.sll")
    p.add_argument("--out-dir", help="Папка для пакетной генерации (--all)")
    args = p.parse_args()

    if args.all:
        out_dir = Path(args.out_dir or "output/reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        samples_dir = PROJECT_ROOT / "samples"
        files = sorted(samples_dir.glob("*.sll"))
        for f in files:
            out = out_dir / (f.stem + ".html")
            try:
                e = _build_one(f, out, args.entry, args.strategy, args.gen)
                print(f"  {f.name:32}  entry={e:10}  → {out}")
            except Exception as exc:
                print(f"  {f.name:32}  FAILED: {type(exc).__name__}: {exc}")
        print(f"\nГотово. Отчёты в {out_dir.resolve()}")
        return

    if not args.input:
        p.error("input или --all обязательны")

    inp = Path(args.input)
    if not inp.exists():
        alt = PROJECT_ROOT / "samples" / args.input
        if alt.exists():
            inp = alt
        else:
            p.error(f"Файл не найден: {args.input}")

    out = Path(args.out) if args.out else inp.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    entry = _build_one(inp, out, args.entry, args.strategy, args.gen)
    print(f"Отчёт сохранён: {out.resolve()}")
    print(f"  entry = {entry}, strategy = {args.strategy}, gen = {args.gen}")


if __name__ == "__main__":
    main()
