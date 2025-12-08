from sll.ast_nodes import Var, Ctr, FCall, Pattern, Rule, Program, IntLit, TypeDef, TypeExpr, ConstrDef, FunSig


def tokenize(text):
    """
    Разбивает текст на токены.
    Возвращает список кортежей: (type, value, lineno).
    Комментарии вида << ... >>.
    """
    tokens = []
    lineno = 1
    i = 0
    n = len(text)

    while i < n:
        char = text[i]

        # 1. Пропуск пробелов и подсчет строк
        if char.isspace():
            if char == '\n':
                lineno += 1
            i += 1
            continue

        # 2. Комментарии << ... >> (Блочные)
        if char == '<' and i + 1 < n and text[i+1] == '<':
            i += 2 # Пропускаем <<
            # Идем пока не встретим >> или конец файла
            while i + 1 < n and not (text[i] == '>' and text[i+1] == '>'):
                if text[i] == '\n':
                    lineno += 1
                i += 1
            i += 2 # Пропускаем >>
            continue

        # 3. Стрелочка ->
        if char == '-' and i + 1 < n and text[i+1] == '>':
            tokens.append(('->', '->', lineno))
            i += 2
            continue

        # 4. Спецсимволы
        if char in '()[]:|.=':
            tokens.append((char, char, lineno))
            i += 1
            continue

        # 5. Числа (положительные и отрицательные)
        if char.isdigit() or (char == '-' and i+1 < n and text[i+1].isdigit()):
            start = i
            i += 1
            while i < n and text[i].isdigit():
                i += 1
            val = text[start:i]
            tokens.append(('INT', int(val), lineno))
            continue

        # 6. Идентификаторы (слова)
        if char.isalnum() or char == '_':
            start = i
            while i < n and (text[i].isalnum() or text[i] == '_'):
                i += 1
            word = text[start:i]
            tokens.append(('NAME', word, lineno))
            continue

        raise ValueError(f"Неизвестный символ '{char}' на строке {lineno}")

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

    def eat(self, expected_val=None, expected_type=None):
        """
        Съедает токен. Проверяет значение (если передано) или тип (если передан).
        Возвращает (значение, номер_строки).
        """
        token = self.current()
        if token is None:
            raise ValueError(f"Неожиданный конец файла, ожидалось {expected_val or expected_type}")

        typ, val, line = token

        if expected_val and val != expected_val:
            raise ValueError(f"Строка {line}: Ожидалось '{expected_val}', получено '{val}'")

        if expected_type and typ != expected_type:
             raise ValueError(f"Строка {line}: Ожидался тип {expected_type}, получен {typ}")

        self.pos += 1
        return val, line

    # --- Парсинг выражений типов ---
    def parse_type_expr(self):
        token = self.current()
        if not token:
            raise ValueError("Неожиданный конец файла при разборе типа")

        _, val, line = token

        match val:
            # Конструктор типа: [List a]
            case '[':
                self.eat('[')
                name, _ = self.eat(expected_type='NAME')
                args = []
                while self.current()[1] != ']':
                    args.append(self.parse_type_expr())
                self.eat(']')
                return TypeExpr(name, args, lineno=line)

            # Переменная типа или простое имя: a, Int
            case _:
                name, line = self.eat(expected_type='NAME')
                return TypeExpr(name, [], lineno=line)

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
        if not token:
             raise ValueError("Неожиданный конец файла при разборе выражения")

        typ, val, line = token

        match val:
            # Конструктор: [Cons x xs]
            case '[':
                self.eat('[')
                name, _ = self.eat(expected_type='NAME')
                args = []
                while self.current()[1] != ']':
                    args.append(self.parse_expr())
                self.eat(']')
                return Ctr(name, args, lineno=line)

            # Вызов функции: (f x)
            case '(':
                self.eat('(')
                name, _ = self.eat(expected_type='NAME')
                args = []
                while self.current()[1] != ')':
                    args.append(self.parse_expr())
                self.eat(')')
                return FCall(name, args, lineno=line)

            # Число
            case _ if typ == 'INT':
                self.eat(expected_type='INT')
                return IntLit(val, lineno=line)

            # Имя (Переменная или Конструктор без скобок)
            case _ if typ == 'NAME':
                self.eat(expected_type='NAME')
                if val[0].isupper():
                    return Ctr(val, [], lineno=line)
                return Var(val, lineno=line)

            case _:
                raise ValueError(f"Строка {line}: Неожиданное начало выражения '{val}'")

    # --- Парсинг Паттернов или Левой части ---
    def parse_pattern(self):
        _, line = self.eat('(')
        name, _ = self.eat(expected_type='NAME')
        params = []
        while self.current()[1] != ')':
            params.append(self.parse_pat_atom())
        self.eat(')')
        return Pattern(name, params, lineno=line)

    def parse_pat_atom(self):
        token = self.current()
        typ, val, line = token

        match val:
            case '[':
                self.eat('[')
                name, _ = self.eat(expected_type='NAME')
                args = []
                while self.current()[1] != ']':
                    args.append(self.parse_pat_atom())
                self.eat(']')
                return Ctr(name, args, lineno=line)
            case _ if typ == 'INT':
                self.eat(expected_type='INT')
                return IntLit(val, lineno=line)
            case _ if typ == 'NAME':
                self.eat(expected_type='NAME')
                return Var(val, lineno=line)
            case _:
                raise ValueError(f"Строка {line}: Ошибка в паттерне, неожиданный токен '{val}'")

    # --- Парсинг Программы ---
    def parse_program(self):
        rules = [] # Список правил
        types = [] # Список определений типов
        sigs = []  # Список сигнатур функций

        while self.current() is not None:
            val = self.current()[1]

            match val:
                # Объявление типа
                case 'type':
                    _, line = self.eat('type')
                    self.eat('[')
                    t_name, _ = self.eat(expected_type='NAME')
                    t_params = []
                    while self.current()[1] != ']':
                        p, _ = self.eat(expected_type='NAME')
                        t_params.append(p)
                    self.eat(']')
                    self.eat(':')

                    constrs = []

                    # ИСПРАВЛЕНИЕ: Проверяем, не пустой ли тип (сразу точка)
                    if self.current()[1] == '.':
                         self.eat('.')
                         types.append(TypeDef(t_name, t_params, [], lineno=line))
                         continue # Идем к следующему объявлению

                    while True:
                        c_name, c_line = self.eat(expected_type='NAME')
                        c_args = []
                        # Читаем типы аргументов конструктора
                        while self.current()[1] not in ['|', '.']:
                            c_args.append(self.parse_type_expr())
                        constrs.append(ConstrDef(c_name, c_args, lineno=c_line))

                        if self.current()[1] == '|':
                            self.eat('|')
                            continue
                        break
                    self.eat('.')
                    types.append(TypeDef(t_name, t_params, constrs, lineno=line))

                # Объявление функции
                case 'fun':
                    _, line = self.eat('fun')

                    # Сигнатура
                    self.eat('(')
                    f_name, _ = self.eat(expected_type='NAME')
                    arg_types = []
                    while self.current()[1] != ')':
                        arg_types.append(self.parse_type_expr())
                    self.eat(')')

                    self.eat('->')
                    ret_type = self.parse_type_expr()
                    self.eat(':')

                    sigs.append(FunSig(f_name, arg_types, ret_type, lineno=line))

                    # Правила
                    while True:
                        pat = self.parse_pattern()
                        self.eat('->')
                        body = self.parse_expr()
                        rules.append(Rule(pat, body, lineno=pat.lineno))

                        sep = self.current()[1]
                        if sep == '|':
                            self.eat('|')
                            continue
                        elif sep == '.':
                            self.eat('.')
                            break
                        else:
                            raise ValueError(f"Строка {self.current()[2]}: Ожидался separator (| или .), получено {sep}")

                case _:
                    raise ValueError(f"Строка {self.current()[2]}: Неожиданный токен верхнего уровня: '{val}'")

        return Program(rules, types, sigs)



def parse(text):
    tokens = tokenize(text)
    parser = Parser(tokens)
    return parser.parse_program()
