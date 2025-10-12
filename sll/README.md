# 📖 SLL (Simple Lazy Language) — модельный язык

Этот каталог содержит реализацию **лингвистического фронтенда** суперкомпилятора:
- AST для языка,
- лексер и парсер,
- pretty-printer (обратная печать),
- проверки корректности (арности функций, использование конструкторов и т.п.).

---

## ✨ Особенности языка
- **Функции** определяются через `fun`, с сигнатурой и набором уравнений.
- **Типы данных** определяются через `type`.
- **Вызовы функций** записываются в круглых скобках: `(f arg1 arg2 ...)`.
- **Конструкторы** данных — в квадратных скобках: `[Cons x xs]`.
- **Сопоставление с образцом** разрешено только по первому аргументу функции.
- **Без целых чисел**: числовые литералы (`0`, `1` и т.п.) не поддерживаются в этом проекте.
- Переменные — идентификаторы (`x`, `xs`).

---

## 🔤 Грамматика (EBNF)

```ebnf
Module      ::= { TypeDecl | FunDecl }

TypeDecl    ::= "type" TypeHead ":" AltList "."
TypeHead    ::= "[" ConstrName { TypeVar } "]"      // напр. [List x], [Pair x y]
AltList     ::= Alt { "|" Alt }
Alt         ::= ConstrName { TypeAtom }             // Cons x [List x] | Nil

FunDecl     ::= "fun" FunSig ":" ClauseList "."
FunSig      ::= "(" FunName { TypeAtom } ")" "->" TypeAtom
ClauseList  ::= Clause { "|" Clause }
Clause      ::= "(" Pattern ")" "->" Expr

Pattern     ::= FunName { PatAtom }                 // напр. (append [Cons x xs] ys)
PatAtom     ::= Var | "[" ConstrName { PatAtom } "]"

Expr        ::= Var
             | "(" FunName { Expr } ")"             // вызов функции
             | "[" ConstrName { Expr } "]"          // значение-конструктор

TypeAtom    ::= "[" TypeExpr "]"                    // скобки обязательны по синтаксису языка
TypeExpr    ::= TypeVar
             | ConstrName { TypeExpr }              // параметризуемый тип-конструктор
             | "[" TypeExpr "]"                     // вложенность; удобна для [List [List x]]

Var         ::= lcIdent                             // a..z вначале
FunName     ::= lcIdent
ConstrName  ::= ucIdent                             // A..Z вначале
TypeVar     ::= lcIdent
