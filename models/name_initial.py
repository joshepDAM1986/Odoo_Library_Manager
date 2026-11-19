import unicodedata

# Valores del campo "Initial": una letra por cada A-Z y '#' para el resto
# (números, símbolos o alfabetos no latinos).
OTHER_INITIAL = '#'
INITIAL_SELECTION = [(letter, letter) for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] + [
    (OTHER_INITIAL, OTHER_INITIAL),
]


# Letras latinas que la normalización Unicode no descompone en letra + acento
SPECIAL_LETTERS = {'Ł': 'L', 'Ø': 'O', 'Đ': 'D', 'Æ': 'A', 'Œ': 'O'}


def name_initial(name):
    """Letra inicial de un nombre, sin acentos y en mayúscula.

    Se ignoran los espacios y signos de puntuación iniciales («Anónimo»,
    "(Ed.) Smith"). Devuelve '#' si el primer carácter útil no es una letra A-Z
    una vez quitados los acentos (números, cirílico, etc.) o si no hay ninguno.
    """
    for char in unicodedata.normalize('NFKD', name or ''):
        if unicodedata.combining(char) or not char.isalnum():
            continue
        # [0]: algunas mayúsculas ocupan dos caracteres ('ß'.upper() == 'SS')
        letter = char.upper()[0]
        letter = SPECIAL_LETTERS.get(letter, letter)
        return letter if 'A' <= letter <= 'Z' else OTHER_INITIAL
    return OTHER_INITIAL
