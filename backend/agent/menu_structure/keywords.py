"""Normalized keyword sets for menu structure playbook checks."""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _normalized_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        n = _normalize(raw)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return tuple(out)


PLAYBOOK_BURGER_KEYWORDS = _normalized_tuple((
    "double burger",
    "smash burger",
    "cheeseburger",
    "hamburger",
    "beef burger",
    "burger",
))

BURGER_EXCLUDE_KEYWORDS = _normalized_tuple((
    "black bean burger",
    "veggie burger",
    "vegan burger",
    "turkey burger",
    "chicken burger",
    "fish burger",
    "plant-based burger",
    "beyond burger",
    "impossible burger",
    "plant-based",
    "plant based",
    "vegan",
    "black bean",
))

PLAYBOOK_FRIES_KEYWORDS = _normalized_tuple((
    "french fries",
    "crinkle french",
    "crinkle fries",
    "waffle fries",
    "steak fries",
    "sweet potato fries",
    "tater tots",
    "hash brown",
    "onion rings",
    "fries",
))

PLAYBOOK_VEGAN_KEYWORDS = _normalized_tuple((
    "black bean burger",
    "veggie burger",
    "vegan burger",
    "plant-based burger",
    "beyond burger",
    "impossible burger",
    "vegan",
    "plant-based",
    "plant based",
))

SIDE_OR_CONDIMENT_KEYWORDS = _normalized_tuple((
    "sliced tomato",
    "diced tomato",
    "sliced red onion",
    "sliced onion",
    "diced onion",
    "sliced mushroom",
    "chopped fresh spinach",
    "sliced mixed bell pepper",
    "bell pepper",
    "lettuce",
    "spinach",
    "american cheese",
    "shredded cheddar",
    "shredded cheese",
    "feta cheese",
    "cheese crumble",
    "dill pickle",
    "pickle slice",
    "diced ham",
    "ham cubes",
    "crumbled plant-based",
    "eggs",
    "egg",
    "trim salad",
    "ketchup",
    "mustard",
    "relish",
    "coleslaw",
    "slaw",
    "mayonnaise",
    "mayo",
))
