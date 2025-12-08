import unittest
from sll.parser import parse
from sll.type_checker import check_program, TypeCheckerError

class TestTypeChecker(unittest.TestCase):

    def check(self, code):
        """Вспомогательный метод: парсит и запускает чекер."""
        prog = parse(code)
        check_program(prog)

    # =========================================================================
    # БЛОК 1: Успешные тесты (Positive Tests)
    # =========================================================================

    def test_01_supervisor_complex_example(self):
        """
        Проверяет:
        1. Вложенные дженерики: [List [List x]]
        2. Работу с числами: Int
        3. Сложные сигнатуры: [List [Pair x y]]
        4. Рекурсию типов.
        """
        code = """
        << Объявления типов >>
        type [List x]: Cons x [List x] | Nil.
        type [Pair x y]: Pair x y.
        type [Letter]: A | B | C | D.
        type [Int] : . 

        << Объединение двух списков >>
        fun (zip [List x] [List y]) -> [List [Pair x y]]:
            (zip [Cons x xs] [Cons y ys]) -> [Cons [Pair x y] (zip xs ys)] |
            (zip xs ys) -> [Nil].

        << Вспомогательные функции >>
        fun (append [List x] [List x]) -> [List x]:
            (append [Cons x xs] ys) -> [Cons x (append xs ys)] |
            (append [Nil] ys) -> ys.

        fun (bind x [List y]) -> [List [Pair x y]]:
            (bind x [Cons y ys]) -> [Cons [Pair x y] (bind x ys)] |
            (bind x [Nil]) -> [Nil].

        << Декартово произведение >>
        fun (cart_prod [List x] [List y]) -> [List [Pair x y]]:
            (cart_prod [Cons x xs] ys) -> (append (bind x ys) (cart_prod xs ys)) |
            (cart_prod [Nil] ys) -> [Nil].

        << Расплющивание вложенного списка (Deep Nesting Test!) >>
        fun (flat [List [List x]]) -> [List x]:
            (flat [Cons [Cons x xs] xss]) -> [Cons x (flat [Cons xs xss])] |
            (flat [Cons [Nil] xss]) -> (flat xss) |
            (flat [Nil]) -> [Nil].

        << Арифметика и Полиномы >>
        fun (add Int Int) -> Int: (add x y) -> x.
        fun (mul Int Int) -> Int: (mul x y) -> x.

        fun (sum [List Int]) -> Int:
            (sum [Cons x xs]) -> (add x (sum xs)) |
            (sum [Nil]) -> 0.

        fun (polynom Int [List Int]) -> Int:
            (polynom x [Nil]) -> 0 |
            (polynom x [Cons coef coefs]) -> (add (mul (polynom x coefs) x) coef).
        """
        print("\n🔎 Тест 1: Пример из задания...")
        try:
            self.check(code)
            print("✅ Успех! Сложные вложенные типы работают корректно.")
        except TypeCheckerError as e:
            self.fail(f"Пример упал с ошибкой: {e}")

    def test_02_simple_arithmetic(self):
        """Проверка базовой работы с типами Nat и Bool"""
        code = """
        type [Nat] : Z | S [Nat].
        type [Bool] : True | False.
        
        fun (isZero [Nat]) -> [Bool]:
            (isZero [Z]) -> [True] |
            (isZero [S x]) -> [False].
        """
        self.check(code)

    # =========================================================================
    # БЛОК 2: Ошибки типов (Negative Tests)
    # =========================================================================

    def test_03_deep_nesting_mismatch(self):
        """
        Ошибка: Передаем [List x] туда, где ждут [List [List x]].
        Чекер должен заметить разницу в уровне вложенности.
        """
        code = """
        type [List x]: Cons x [List x] | Nil.
        
        fun (flat [List [List x]]) -> [List x]:
            (flat [Nil]) -> [Nil].
            
        fun (bad_call [List x]) -> [List x]:
            << ОШИБКА: x имеет тип 'x' (элемент), а flat ждет список списков >>
            (bad_call list) -> (flat list). 
        """
        print("\n🔎 Тест 3: Ошибка вложенности [List x] vs [List [List x]]...")
        with self.assertRaises(TypeCheckerError) as cm:
            self.check(code)

        # Проверяем, что ошибка именно про несовпадение типов
        err_msg = str(cm.exception)
        print(f"   Поймана ошибка: {err_msg}")
        self.assertTrue("имеет тип" in err_msg or "не совпадает" in err_msg)

    def test_04_generic_concrete_mismatch(self):
        """
        Ошибка: Передаем список Чисел туда, где ждут список Букв.
        [List Int] != [List Letter]
        """
        code = """
        type [List a]: Cons a [List a] | Nil.
        type [Letter]: A | B.
        type [Int]: .

        fun (process [List Letter]) -> [List Letter]:
            (process x) -> x.

        fun (bad_call [List Int]) -> [List Letter]:
            (bad_call nums) -> (process nums).
        """
        print("\n🔎 Тест 4: Несовпадение конкретных типов (Int vs Letter)...")
        with self.assertRaises(TypeCheckerError) as cm:
            self.check(code)
        print(f"   Поймана ошибка: {cm.exception}")

    def test_05_linearity_violation(self):
        """
        Ошибка: Нарушение линейности (переменная дважды в паттерне).
        """
        code = """
        type [Nat]: Z.
        fun (dup [Nat] [Nat]) -> [Nat]:
            (dup x x) -> x.
        """
        print("\n🔎 Тест 5: Нарушение линейности (x x)...")
        with self.assertRaises(TypeCheckerError) as cm:
            self.check(code)

        err_msg = str(cm.exception)
        print(f"   Поймана ошибка: {err_msg}")
        self.assertIn("уже объявлена", err_msg)

    def test_06_return_int_instead_of_type(self):
        """
        Ошибка: Функция должна вернуть Тип, а возвращает число (IntLit).
        """
        code = """
        type [Nat]: Z.
        type [Int]: .
        
        fun (f [Nat]) -> [Nat]:
            (f x) -> 42. << Ошибка, ждем [Nat], а это Int >>
        """
        print("\n🔎 Тест 6: Число вместо Конструктора...")
        with self.assertRaises(TypeCheckerError) as cm:
            self.check(code)
        print(f"   Поймана ошибка: {cm.exception}")
        self.assertIn("Ожидался", str(cm.exception))

    def test_07_constructor_arity_mismatch(self):
        """
        Ошибка: Неверное число аргументов у конструктора.
        Cons ждет 2 аргумента, даем 1.
        """
        code = """
        type [List a]: Cons a [List a] | Nil.
        
        fun (f [List a]) -> [List a]:
            (f [Cons x]) -> [Nil]. << Ошибка: Cons ждет x и xs >>
        """
        print("\n🔎 Тест 7: Арность конструктора...")
        with self.assertRaises(TypeCheckerError) as cm:
            self.check(code)
        print(f"   Поймана ошибка: {cm.exception}")
        self.assertIn("ждет 2 аргументов", str(cm.exception))

    def test_08_function_arity_mismatch(self):
        """
        Ошибка: Неверное число аргументов у функции.
        """
        code = """
        type [Nat]: Z.
        fun (add [Nat] [Nat]) -> [Nat]: (add x y) -> x.
        
        fun (main [Nat]) -> [Nat]:
            (main x) -> (add x). << Ошибка: add ждет 2 аргумента >>
        """
        print("\n🔎 Тест 8: Арность функции...")
        with self.assertRaises(TypeCheckerError) as cm:
            self.check(code)
        print(f"   Поймана ошибка: {cm.exception}")
        self.assertIn("Неверное число аргументов", str(cm.exception))

if __name__ == '__main__':
    unittest.main()