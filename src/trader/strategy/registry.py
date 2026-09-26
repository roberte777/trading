"""Strategy registry with auto-discovery.

Every module in ``trader.strategies`` is imported on first lookup, so adding a
strategy is just adding a file with a ``@register``-decorated class. There is no
central list to edit, which keeps strategy branches free of merge conflicts.
"""

from __future__ import annotations

import importlib
import pkgutil

from trader.strategy.base import Strategy

_REGISTRY: dict[str, type[Strategy]] = {}
_discovered = False


def register[T: type[Strategy]](cls: T) -> T:
    if not cls.name:
        raise ValueError(f"{cls.__name__} must set a `name`")
    existing = _REGISTRY.get(cls.name)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"duplicate strategy name {cls.name!r}: {existing.__name__} and {cls.__name__}"
        )
    _REGISTRY[cls.name] = cls
    return cls


def discover() -> None:
    global _discovered
    if _discovered:
        return
    import trader.strategies as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"{pkg.__name__}.{mod.name}")
    _discovered = True


def get_strategy(name: str) -> type[Strategy]:
    discover()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"unknown strategy {name!r}; available: {', '.join(sorted(_REGISTRY))}"
        ) from None


def all_strategies() -> dict[str, type[Strategy]]:
    discover()
    return dict(sorted(_REGISTRY.items()))
