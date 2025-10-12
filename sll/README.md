# 📖 SLL (Simple Lazy Language) — модельный язык

Этот каталог содержит лингвистический фронтенд суперкомпилятора:
- лексер и парсер (LL(1)/рекурсивный спуск),
- AST и pretty-printer,
- семантические проверки (идентификаторы, арности, покрытие и т.п.),
- нормализатор в «core»-представление для этапа суперкомпиляции.

---

## ✨ Особенности языка
- **Функции** определяются через `fun`, с сигнатурой и набором уравнений.
- **Типы данных** определяются через `type`.
- **Вызовы функций** записываются в круглых скобках: `(fun arg1 arg2 ...)`.
- **Конструкторы** данных — в квадратных скобках: `[Cons x xs]`.
- **Сопоставление с образцом** разрешено только по первому аргументу функции.
- **Без целых чисел**: без реализации арифметики чисел.
- Переменные — идентификаторы (`x`, `xs`).

---

## 🔤 Грамматика (EBNF)

```ebnf
Module      ::= { TypeDecl | FunDecl }

TypeDecl    ::= "type" TypeHead ":" AltList "."
TypeHead    ::= "[" ConstrName { TypeVar } "]"                 // [List x], [Pair x y]
AltList     ::= Alt { "|" Alt }
Alt         ::= ConstrName { TypeAtom }                        // Cons x [List x] | Nil

FunDecl     ::= "fun" FunSig ":" ClauseList "."
FunSig      ::= "(" FunName { TypeAtom } ")" "->" TypeAtom
ClauseList  ::= Clause { "|" Clause }
Clause      ::= "(" Pattern ")" "->" Expr

Pattern     ::= FunName { PatAtom }                            // (append [Cons x xs] ys)
PatAtom     ::= Var | "[" ConstrName { PatAtom } "]"           // чисел в паттернах нет

Expr        ::= Var
             | "(" FunName { Expr } ")"                        // вызов функции
             | "[" ConstrName { Expr } "]"                     // значение-конструктор
             | IntLit                                          // числовой литерал: 0, 1, 42

TypeAtom    ::= "[" TypeExpr "]"                               // типы всегда в []
TypeExpr    ::= TypeVar
             | ConstrName { TypeExpr }                         // параметризуемый тип-конструктор
             | "[" TypeExpr "]"                                // вложенность: [List [List x]]

Var         ::= lcIdent
FunName     ::= lcIdent
ConstrName  ::= ucIdent
TypeVar     ::= lcIdent

IntLit      ::= Digit {Digit}
Digit       ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
