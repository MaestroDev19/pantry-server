from __future__ import annotations

import json
from typing import List

from app.models.pantry import PantryItem
from app.models.recipe import DietaryTag, Difficulty, RecipeMode


recipe_prompt = """Role: Pantry recipe engine.
Inputs: `items` [{{n:name, q:qty, s:"good"|"expiring"|"expired"}}], `prefs` [dietary filters], `max_time` (mins), `diff` (any|easy|medium|hard), `mode` (mine|household).

Rules:
1. Output EXACTLY 3 recipes prioritizing "expiring"/"expired" items. Fallback: simple staple recipes.
2. Strictly obey `prefs`.
3. Never invent owned items; flag missing ingredients via `have: false`.
4. Output ONLY a raw JSON array. No markdown, no prose, no code fences.

Schema:
[{
  "title": "str (max 5 words)",
  "time": 0,
  "diff": "easy|medium|hard",
  "servings": 0,
  "ingredients": [{ // max 6 per recipe
    "name": "str (max 4 words)",
    "qty": "str",
    "have": boolean,
    "owner": "str(name) or null(if missing)"
  }],
  "steps": ["str (max 5 steps, max 12 words/step)"],
  "note": "str(household coordination note) or null"
}]"""

def get_recipe_prompt(
    items: List[PantryItem],
    prefs: List[DietaryTag],
    max_time: int,
    diff: Difficulty,
    mode: RecipeMode,
) -> str:
    """
    Build the base recipe prompt plus a structured JSON context.

    The context encodes:
    - pantry items (name, quantity, freshness/status)
    - dietary preferences (DietaryTag values)
    - time and difficulty constraints
    - recipe mode (personal vs household)
    """
    items_payload = [
        {
            "name": item.name,
            "quantity": item.quantity,
            "status": getattr(item, "status", None),
        }
        for item in items
    ]
    context = {
        "items": items_payload,
        "prefs": [tag.value for tag in prefs],
        "max_time": max_time,
        "diff": diff.value,
        "mode": mode.value,
    }
    return f"{recipe_prompt}\n\nContext:\n{json.dumps(context, ensure_ascii=False)}"

def get_recipe_prompt_with_specific_wants(
    items: List[PantryItem],
    prefs: List[DietaryTag],
    max_time: int,
    diff: Difficulty,
    mode: RecipeMode,
    wants: str,
) -> str:
    """
    Variant of the base recipe prompt that includes a specific user request,
    for example: "turkey salad" or "pasta without dairy".
    """
    base = get_recipe_prompt(items, prefs, max_time, diff, mode)
    return f"{base}\n\nUser-specific request: {wants.strip()}"