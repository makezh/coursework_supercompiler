from sll.ast_nodes import Var, Ctr, FCall, Pattern, Rule, Program, IntLit, TypeDef, TypeExpr, ConstrDef, FunSig


def tokenize(text):
    # 1. Удаляем комментарии (начинаются с --)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if '--' in line:
            line = line.split('--')[0]
        cleaned_lines.append(line)
    text = ' '.join(cleaned_lines)

    # 2. Расставляем пробелы вокруг спецсимволов, кроме '->'
    text = text.replace('->', ' ARROW_TOKEN ')

    specials = ['(', ')', '[', ']', ':', '|', '.', '=']
    for char in specials:
        text = text.replace(char, f' {char} ')

    # 3. Разбиваем по пробелам
    tokens = text.split()

    # 4. Возвращаем '->' на место
    tokens = [t if t != 'ARROW_TOKEN' else '->' for t in tokens]
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        """Возвращает текущий токен или None, если конец."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def eat(self, expected):
        """
        Съедает ожидаемый токен. \n
        Если там что-то другое — ошибка.
        """
        token = self.current()
        if token != expected:
            raise ValueError(f"Ожидалось '{expected}', но получено '{token}' на позиции {self.pos}")
        self.pos += 1

    # --- Парсинг выражений типов ---
    def parse_type_expr(self):
        """
        Парсит выражение типа. \n
        Примеры: 'a', '[Nat]', '[List [Nat]]'
        """
        token = self.current()

        # Если начинается с [, это конструктор типа: [List ...]
        if token == '[':
            self.eat('[')
            type_name = self.tokens[self.pos]
            self.pos += 1

            args = []
            while self.current() != ']':
                args.append(self.parse_type_expr())
            self.eat(']')
            return TypeExpr(type_name, args)

        else:
            # Это просто имя (переменная типа 'a' или имя типа без скобок)
            name = self.tokens[self.pos]
            self.pos += 1
            return TypeExpr(name, [])

    def parse_var_or_ctr(self):
        """
        Разбирает имя. \n
        Если с Большой буквы — конструктор без аргументов, иначе переменная.
        """
        token = self.tokens[self.pos]
        self.pos += 1
        # Конструкторы с большой буквы, переменные - с маленькой
        if token[0].isupper():
            return Ctr(token, [])  # Конструктор без полей, например Nil
        else:
            return Var(token)

    # --- Парсинг Выражений или Правой часть ---
    def parse_expr(self):
        token = self.current()

        # 0. Число (IntLit)
        if token.isdigit() or (token.startswith('-') and token[1:].isdigit()):
            self.pos += 1
            return IntLit(int(token))

        # 1. Конструктор [Name arg1 arg2]
        if token == '[':
            self.eat('[')
            ctr_name = self.tokens[self.pos]
            self.pos += 1
            args = []
            while self.current() != ']':
                args.append(self.parse_expr())
            self.eat(']')
            return Ctr(ctr_name, args)

        # 2. Вызов функции (fun arg1 arg2)
        elif token == '(':
            self.eat('(')
            fun_name = self.tokens[self.pos]
            self.pos += 1
            args = []
            while self.current() != ')':
                args.append(self.parse_expr())
            self.eat(')')
            return FCall(fun_name, args)

        # 3. Просто переменная или конструктор-константа
        else:
            return self.parse_var_or_ctr()

    # --- Парсинг Паттернов или Левой части ---
    def parse_pattern(self):
        # Паттерн всегда в скобках: (funcname arg1 ...)
        self.eat('(')
        fun_name = self.tokens[self.pos]
        self.pos += 1

        params = []
        while self.current() != ')':
            params.append(self.parse_pat_atom())
        self.eat(')')

        return Pattern(fun_name, params)

    def parse_pat_atom(self):
        """Парсим аргумент внутри паттерна (переменная, конструктор или число)"""
        token = self.current()

        # Конструктор
        if token == '[':
            self.eat('[')
            ctr_name = self.tokens[self.pos]
            self.pos += 1
            args = []
            while self.current() != ']':
                args.append(self.parse_pat_atom())
            self.eat(']')
            return Ctr(ctr_name, args)

        # Число в паттерне
        elif token.isdigit():
            self.pos += 1
            return IntLit(int(token))

        # Переменная
        else:
            name = self.tokens[self.pos]
            self.pos += 1
            return Var(name)

    # --- Парсинг Программы ---
    def parse_program(self):
        rules = [] # Список правил
        types = [] # Список определений типов
        sigs = []  # Список сигнатур функций

        while self.current() is not None:

            # 1. Определение ТИПА
            if self.current() == 'type':
                self.eat('type')

                # Читаем голову: [List a]
                self.eat('[')
                type_name = self.tokens[self.pos]
                self.pos += 1
                type_params = []
                while self.current() != ']':
                    type_params.append(self.tokens[self.pos]) # переменные типа 'a'
                    self.pos += 1
                self.eat(']')

                self.eat(':')

                constrs = []
                # Читаем конструкторы: Nil | Cons a [List a]
                while True:
                    c_name = self.tokens[self.pos]
                    self.pos += 1
                    c_args = []
                    # Пока не встретим | или . читаем типы аргументов
                    while self.current() not in ['|', '.']:
                        c_args.append(self.parse_type_expr())

                    constrs.append(ConstrDef(c_name, c_args))

                    if self.current() == '|':
                        self.eat('|')
                        continue
                    break

                self.eat('.')
                types.append(TypeDef(type_name, type_params, constrs))

            # 2. Определение ФУНКЦИИ
            elif self.current() == 'fun':
                self.eat('fun')

                # Парсинг сигнатуры: (name arg_types) -> ret_type
                self.eat('(')
                fun_name = self.tokens[self.pos]
                self.pos += 1

                arg_types = []
                while self.current() != ')':
                    arg_types.append(self.parse_type_expr())
                self.eat(')')

                self.eat('->')
                ret_type = self.parse_type_expr()

                self.eat(':')

                # Сохраняем сигнатуру
                sigs.append(FunSig(fun_name, arg_types, ret_type))

                # --- Читаем правила ---
                while True:
                    pat = self.parse_pattern()

                    if pat.name != fun_name:
                        pass

                    self.eat('->')
                    body = self.parse_expr()
                    rules.append(Rule(pat, body))

                    if self.current() == '|':
                        self.eat('|')
                        continue
                    elif self.current() == '.':
                        self.eat('.')
                        break
                    else:
                        raise ValueError(f"Ожидался '|' или '.', получено '{self.current()}'")

            else:
                # Если встретили что-то странное
                break

        # Возвращаем программу со всеми данными
        return Program(rules, types, sigs)


def parse(text):
    tokens = tokenize(text)
    parser = Parser(tokens)
    return parser.parse_program()
