# webdemo — визуальное демо суперкомпилятора SLL

Дополнение к CLI (`main.py`), не модифицирует основной пакет `sll/`. Два режима:

1. **Статический генератор** — собирает самодостаточный HTML-отчёт для одного SLL-файла. Удобно для иллюстраций в ПЗ диплома и оффлайн-показа.
2. **Локальный Flask-сервер** — редактор SLL в браузере с интерактивным переключением стратегий, уровней формата и пересборкой по кнопке.

В обоих режимах отчёт показывает все 4 уровня формата (`OFF / SIMPLE / PARAM / ACTIVE`) бок о бок, с графом процесса, остаточной программой, форматами на базисных конфигурациях и сводкой эффекта декомпозиции.

## Установка

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install flask
```

Для рендера графов нужен `graphviz` в `PATH` (бинарник `dot`). На macOS: `brew install graphviz`. Без graphviz отчёт всё равно собирается, но без SVG.

## Статический режим

Один файл:
```bash
python -m webdemo.generate samples/format_sum.sll -o /tmp/sum.html
open /tmp/sum.html
```

С указанной стратегией и точкой входа:
```bash
python -m webdemo.generate samples/active_simple.sll --entry main -s HE -g BOTTOM -o /tmp/active.html
```

Пакетная генерация по всем `samples/*.sll`:
```bash
python -m webdemo.generate --all --out-dir output/reports
```

## Интерактивный режим

```bash
python -m webdemo.server
# по умолчанию http://127.0.0.1:8000
```

Опции: `--port 8080`, `--host 0.0.0.0`, `--debug`.

В браузере: выбрать пример из dropdown'а, при необходимости отредактировать код, выбрать свисток (HE/TAG) и обобщение (TOP/BOTTOM), нажать «Прогнать».

## Что снаружи

- `runner.py` — единое ядро, превращает SLL в `CompileResult` (остаточная программа, DOT/SVG, форматы, статистика). Используется обоими режимами.
- `generate.py` — CLI вокруг runner'а + Jinja2-шаблон `report.html`.
- `server.py` — Flask-обёртка вокруг runner'а + шаблоны `index.html` и `_result_fragment.html`.

`main.py` и пакет `sll/` остаются нетронутыми — все импорты идут через их публичный API.
