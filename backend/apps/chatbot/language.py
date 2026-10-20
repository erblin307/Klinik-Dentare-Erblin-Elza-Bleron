"""
Language detection for Albanian (sq), English (en) and German (de).

Deterministic and dependency-free: distinctive letters and common words are
scored per language. Messages without any signal ("10:00", "2") keep the
conversation's current language.
"""

import re

LANGUAGE_NAMES = {"sq": "Albanian", "en": "English", "de": "German"}

_LETTERS = {"sq": set("ëç"), "de": set("äöüß")}

_WORDS = {
    "sq": set(
        """
        dhe një në për është jam kam keni ju unë juaj si çfarë cfare sa kur ku me nga të te që
        mund dua do doja kisha faleminderit përshëndetje pershendetje mirëdita miredita tung
        nesër neser sot pasnesër orari orar çmimi cmimi kushton kosto dhëmbë dhemb dhëmbi
        rezervoj rezervim anuloj anulo ndryshoj ndryshim takim takimin terminin mjeku mjeke
        doktori shërbime sherbime pastrim falemnderit ditë dite java javës
        """.split()
    ),
    "en": set(
        """
        the and is are what when where how much can could would i you your my me to for
        do does have has book booking appointment please hello hi hey thanks thank
        tomorrow today price cost open hours cancel reschedule dentist cleaning want need
        available slot next week of with
        """.split()
    ),
    "de": set(
        """
        der die das und ist sind ich sie ihr wie was wann wo viel kostet ein eine einen
        bitte hallo danke morgen heute haben habe möchte moechte können koennen zahnarzt
        zahnärztin termin buchen absagen stornieren verschieben öffnungszeiten preis
        reinigung nächste woche guten tag mit für fuer auf nicht
        """.split()
    ),
}

# A reply confirms/declines only if it consists solely of these words and
# contains at least one core word: "Po, konfirmoj!" confirms, "yes, but at 11" does not.
_YES_CORE = {
    "yes", "yep", "confirm", "ok", "okay", "sure",
    "po", "konfirmoj", "konfirmo", "dakord", "rregull",
    "ja", "bestätigen", "bestätige", "bestaetigen", "jawohl", "einverstanden", "gerne",
}  # fmt: skip
_YES_FILLER = {"please", "i", "do", "thanks", "faleminderit", "ne", "në", "bitte", "ich", "danke"}
_NO_CORE = {"no", "nope", "jo", "nein"}
_NO_FILLER = {"thanks", "thank", "you", "faleminderit", "danke", "not", "now"}

_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect_language(text, default):
    """The most likely of sq/en/de for ``text``, else ``default``."""
    lowered = text.lower()
    scores = {language: 0.0 for language in LANGUAGE_NAMES}
    for language, letters in _LETTERS.items():
        scores[language] += 2 * sum(lowered.count(letter) for letter in letters)
    for token in _TOKEN.findall(lowered):
        for language, words in _WORDS.items():
            if token in words:
                scores[language] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0 or list(scores.values()).count(scores[best]) > 1:
        return default
    return best


def _consists_of(text, core, filler):
    tokens = set(_TOKEN.findall(text.lower()))
    return bool(tokens & core) and tokens <= core | filler


def is_affirmative(text):
    """An explicit "yes", used to confirm pending actions."""
    return _consists_of(text, _YES_CORE, _YES_FILLER)


def is_negative(text):
    return _consists_of(text, _NO_CORE, _NO_FILLER)
