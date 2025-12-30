import unittest
from sll.parser import parse, Parser, tokenize
from sll.preprocessor import add_tags
from sll.matching import substitute
from sll.ast_nodes import Var, Ctr, FCall

# Программа на твоем диалекте SLL
CODE = """
type [Nat] : Z | S [Nat] .
type [List] : Nil | Cons x [List] .

<< Простая функция для теста >>
fun (wrap [Nat]) -> [Nat] :
    (wrap x) -> [S x] .

<< Функция посложнее >>
fun (makeList [Nat]) -> [List] :
    (makeList x) -> [Cons x [Nil]] .
"""

class TestTags(unittest.TestCase):

    def setUp(self):
        self.prog = parse(CODE)
        # ВАЖНО: Запускаем препроцессор, чтобы расставить теги
        add_tags(self.prog)

    def test_1_tags_assigned(self):
        """Проверяем, что после add_tags у узлов появились уникальные ID."""
        print("\n--- Test 1: Tags Assignment ---")

        # Берем правило (wrap x) -> [S x]
        rule_wrap = self.prog.rules[0]
        body = rule_wrap.body # Это [S x]

        print(f"Body: {body}, Tag: {body.tag}")

        self.assertIsNotNone(body.tag, "У корня выражения должен быть тег")
        self.assertIsInstance(body, Ctr)

        # Проверяем аргумент x внутри [S x]
        arg_x = body.args[0]
        print(f"Arg: {arg_x}, Tag: {arg_x.tag}")
        self.assertIsNotNone(arg_x.tag, "У аргумента тоже должен быть тег")

        # Теги должны быть разными
        self.assertNotEqual(body.tag, arg_x.tag, "Теги разных узлов должны отличаться")

    def test_2_tags_preserved_on_substitution(self):
        """
        Проверяем, что при подстановке (выполнении шага) тег копируется из кода программы.
        """
        print("\n--- Test 2: Tags Preservation ---")

        # Берем шаблон: [S x]
        template = self.prog.rules[0].body
        original_tag = template.tag

        # Создаем значение для подстановки: x = [Z]
        # Допустим, это [Z] пришло из другого места и у него свой тег 999
        val_z = Ctr("Z", [], tag=999)
        bindings = {"x": val_z}

        # Выполняем подстановку: [S x] {x: [Z]} -> [S [Z]]
        result = substitute(template, bindings)

        print(f"Template Tag: {original_tag}")
        print(f"Result Tag:   {result.tag}")
        print(f"Result Child Tag: {result.args[0].tag}")

        # 1. Тег корня результата должен совпадать с тегом шаблона ([S])
        self.assertEqual(result.tag, original_tag,
                         "Ошибка! Тег конструктора S должен сохраниться из исходной программы!")

        # 2. Тег аргумента должен сохраниться от значения ([Z])
        self.assertEqual(result.args[0].tag, 999,
                         "Ошибка! Тег подставленного значения Z должен сохраниться!")

    def test_3_complex_structure_tags(self):
        """Проверяем теги в сложной структуре [Cons x [Nil]]"""
        print("\n--- Test 3: Complex Structure ---")

        # Берем правило (makeList x) -> [Cons x [Nil]]
        rule_list = self.prog.rules[1]
        body = rule_list.body

        # body = Cons (tag A)
        #   args[0] = x (tag B)
        #   args[1] = Nil (tag C)

        tag_cons = body.tag
        tag_x = body.args[0].tag
        tag_nil = body.args[1].tag

        # Все теги должны быть уникальны
        tags = {tag_cons, tag_x, tag_nil}
        self.assertEqual(len(tags), 3, "Все узлы должны иметь уникальные теги")

        # Подставляем x -> [Z] (tag 100)
        val_z = Ctr("Z", [], tag=100)
        res = substitute(body, {"x": val_z})

        # Проверяем, что структура сохранила свои теги
        self.assertEqual(res.tag, tag_cons)       # Cons
        self.assertEqual(res.args[1].tag, tag_nil) # Nil
        self.assertEqual(res.args[0].tag, 100)     # Z (вставленный)

if __name__ == '__main__':
    unittest.main()