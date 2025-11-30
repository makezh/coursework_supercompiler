import unittest
from sll.parser import parse
from sll.type_checker import check_program, TypeCheckerError


class TestSemantics(unittest.TestCase):

    def test_valid_program(self):
        """Тест 1: Идеальная программа должна проходить проверку без ошибок"""
        code = """
        type [Nat] : Z | S [Nat] .
        type [Bool] : True | False .

        fun (isZero [Nat]) -> [Bool] :
            (isZero [Z]) -> [True]
          | (isZero [S x]) -> [False] .
          
        fun (inc [Nat]) -> [Nat] :
            (inc x) -> [S x] .
        """
        prog = parse(code)
        try:
            check_program(prog)
        except TypeCheckerError as e:
            self.fail(f"Валидная программа вызвала ошибку: {e}")

    def test_return_type_error(self):
        """Тест 2: Ошибка возвращаемого значения (ждали Bool, вернули Nat)"""
        code = """
        type [Nat] : Z | S [Nat] .
        type [Bool] : True | False .

        fun (bad [Nat]) -> [Bool] :
            (bad [Z]) -> [Z] . 
        """
        prog = parse(code)

        # assertRaises проверяет, что код внутри 'with' действительно падает с нужной ошибкой
        with self.assertRaises(TypeCheckerError) as cm:
            check_program(prog)

        # Можно дополнительно проверить текст ошибки
        self.assertIn("возвращает Nat", str(cm.exception))
        print(f"\nCaught expected error in test 2: {cm.exception}")

    def test_argument_type_error(self):
        """Тест 3: Ошибка типа аргумента (функция ждет Nat, передали Bool)"""
        code = """
        type [Nat] : Z | S [Nat] .
        type [Bool] : True | False .

        fun (f [Nat]) -> [Bool] : (f x) -> [True].

        fun (caller [Bool]) -> [Bool] :
            (caller b) -> (f b) . 
        """
        prog = parse(code)

        with self.assertRaises(TypeCheckerError) as cm:
            check_program(prog)

        # Проверим, что ошибка связана с аргументами или типами
        # (текст может отличаться в зависимости от твоей реализации type_checker,
        # главное, что исключение поймано)
        print(f"\nCaught expected error in test 3: {cm.exception}")

    def test_unknown_variable(self):
        """Тест 4: Использование неизвестной переменной"""
        code = """
        type [Nat] : Z .
        fun (test [Nat]) -> [Nat] :
            (test x) -> y . 
        """
        prog = parse(code)

        with self.assertRaises(TypeCheckerError) as cm:
            check_program(prog)

        self.assertIn("Неизвестная переменная", str(cm.exception))
        print(f"\nCaught expected error in test 4: {cm.exception}")

    def test_unknown_function(self):
        """Тест 5: Вызов несуществующей функции"""
        code = """
        type [Nat] : Z .
        fun (main [Nat]) -> [Nat] :
            (main x) -> (ghost x) . 
        """
        prog = parse(code)
        with self.assertRaises(TypeCheckerError):
            check_program(prog)

        print("\nCaught expected error in test 5: Unknown function called.")


if __name__ == '__main__':
    unittest.main()
