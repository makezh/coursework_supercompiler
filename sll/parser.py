from sll.ast_nodes import Var, Ctr, FCall, Pattern, Rule, Program


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
        """Парсим аргумент внутри паттерна (переменная или конструктор)"""
        token = self.current()
        if token == '[':
            self.eat('[')
            ctr_name = self.tokens[self.pos]
            self.pos += 1
            args = []
            while self.current() != ']':
                args.append(self.parse_pat_atom())
            self.eat(']')
            return Ctr(ctr_name, args)
        else:
            # Переменная
            name = self.tokens[self.pos]
            self.pos += 1
            return Var(name)

    # --- Парсинг Программы ---
    def parse_program(self):
        rules = []
        # Мы ожидаем структуру: fun name args : rule | rule .

        while self.current() is not None:
            if self.current() == 'fun':
                self.eat('fun')
                # Пропускаем имя функции и аргументы до двоеточия
                while self.current() != ':':
                    self.pos += 1
                self.eat(':')

                # Читаем правила
                while True:
                    # Парсим одно правило
                    pat = self.parse_pattern()
                    self.eat('->')
                    body = self.parse_expr()
                    rules.append(Rule(pat, body))

                    # Смотрим разделитель
                    if self.current() == '|':
                        self.eat('|')
                        continue
                    elif self.current() == '.':
                        self.eat('.')
                        break
                    else:
                        raise ValueError(f"Ожидался '|' или '.', получено '{self.current()}'")

            # Если встретили type, пока пропускаем его определение
            elif self.current() == 'type':
                self.eat('type')
                while self.current() != '.':
                    self.pos += 1
                self.eat('.')

            else:
                break

        return Program(rules)


def parse(text):
    tokens = tokenize(text)
    parser = Parser(tokens)
    return parser.parse_program()
