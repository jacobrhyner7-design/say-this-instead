"""Emotional opening line for practical posts (translator and swap), shown big on the first card and spoken first.
Blueprint rule: every post opens with emotion, then gives the practical help."""

FEEL_HOOKS = {}


def feel_hook(p):
    return p.get("feel_hook") or FEEL_HOOKS.get(p.get("says") or p.get("title", ""))
