# 🚀 SLL Supercompiler

Реализация классического суперкомпилятора для модельного языка **SLL (Simple Lazy Language)**.

Поддерживаются:

- 🧠 Whistle: **HE** и **TAG**
- 🔁 Generalization: **TOP** и **BOTTOM (Abramov)**
- 🌲 Hypercycle
- 🔗 Folding (back-links)
- 🧩 Let-based context generalization
- 📦 Генерация остаточной программы

---

# 📌 Общая архитектура

Суперкомпиляция проходит следующие этапы:

```
Parsing
→ Type checking
→ Driving
→ Whistle (HE / TAG)
→ Generalization (TOP / BOTTOM)
→ Hypercycle
→ Residualization
```

---

# 🧠 Стратегии свистка

## HE (Homeomorphic Embedding)

Классический критерий Турчина.

Свистим, если предок гомеоморфно вложен в текущую конфигурацию:

```
alpha ⊑ beta
```

---

## TAG (Bag-of-Tags)

Реализация по мотивам Bolingbroke & Peyton Jones.

Свистим, если:

- множество тегов не расширилось,
- но их суммарное количество увеличилось.

Если теги неинформативны, используется fallback на HE.

---

# 🔁 Стратегии обобщения

## TOP

Обобщается **предок**:

```
alpha := MSG(alpha, beta)
```

Поддерево alpha перестраивается.

---

## BOTTOM (Абрамов)

Обобщается **текущий узел**:

```
beta := MSG(alpha, beta)
```

Если MSG вырождается в переменную обобщения, строится контекстное обобщение:

```
let h1 = e1; ...; hn = en in C[h1,...,hn]
```

---

# 🧩 Let-узлы

Let используется только во внутреннем графе процессов.

- создаётся при BOTTOM-обобщении,
- декомпозируется драйвером,
- не появляется в остаточной программе,
- разворачивается в вспомогательные функции при residualization.

---

# 🌲 Гиперцикл (Abramov Hypercycle)

Алгоритм:

1. Строим дерево для стартовой конфигурации.
2. Собираем цели back-links (базисные конфигурации).
3. Для каждой новой конфигурации строим отдельное дерево.
4. Формируем `PROGRAM_FOREST`.

Особенности реализации:

- используется `processed_configs`
- конфигурации идентифицируются по каноническому корню
- entry выбирается по стартовой конфигурации

---

# 🔗 Базисные конфигурации

Базисная конфигурация — это:

- стартовая конфигурация,
- или узел, на который есть back-link.

Каждая базисная конфигурация превращается в функцию остаточной программы.

---

# 📦 Residualization

Алгоритм:

1. Каждой базисной конфигурации сопоставляется функция.
2. Back-links превращаются в вызовы соответствующих функций.
3. Let раскрывается.
4. Entry соответствует стартовой конфигурации.

---

# 🧪 Пример

Для:

```
(add3 x y z) = add (add x y) z
```

BOTTOM + Hypercycle даёт:

```
(main x1 x2 x3) -> (g1 x1 x2 x3);
(g1 (Z) x2 x3) -> (g2 x2 x3);
(g1 (S v1) x2 x3) -> [S (g1 v1 x2 x3)];
(g2 (Z) x3) -> x3;
(g2 (S v) x3) -> [S (g2 v x3)];
```

---

# ⚙ CLI

```
python main.py file.sll function_name \
    -s HE|TAG \
    -g TOP|BOTTOM \
    -o output_dir
```

Примеры:

```
python main.py test_3.sll add3 -g BOTTOM
python main.py commute.sll main -s TAG -g BOTTOM
```

---

# 📂 Структура проекта

```
sll/
 ├── ast_nodes.py
 ├── bag_of_tags.py
 ├── driver.py
 ├── exporter.py
 ├── he.py
 ├── interpreter.py
 ├── matching.py
 ├── msg.py
 ├── parser.py
 ├── preprocessor.py
 ├── process_tree.py
 ├── residualizer.py
 ├── supercompiler.py
 ├── tagging.py
 └── type_checker.py
```

---

# 📘 Теоретическая база

- Turchin V. F. The concept of a supercompiler //ACM Transactions on Programming Languages and Systems (TOPLAS). – 1986. – Т. 8. – №. 3. – С. 292-325.
- Климов А.В., Романенко С.А. **Суперкомпиляция: основные принципы и базовые понятия** // Препринты ИПМ им. М.В.Келдыша.2018. № 111. 36 с. doi:10.20948/prepr-2018-111
URL: http://library.keldysh.ru/preprint.asp?id=2018-111
- Романенко С.А. **Суперкомпиляция:
гомеоморфное вложение, вызов по имени, частичные вычисления** // Препринты ИПМ им. М.В.Келдыша. 2018. № 209. 32 с. doi:10.20948/prepr-2018-209
URL: http://library.keldysh.ru/preprint.asp?id=2018-209
- Soerensen M. H., Glück R., Jones N. D. A positive supercompiler //Journal of functional programming. – 1996. – Т. 6. – №. 6. – С. 811-838.
- Bolingbroke M., Jones S. P. Improving supercompilation: tag-bags, rollback, speculation, normalisation, and generalisation //ICFP. – 2011.

---