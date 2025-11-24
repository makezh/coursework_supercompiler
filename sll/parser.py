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