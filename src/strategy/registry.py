"""전략 레지스트리.

@register("my_strategy") 데코레이터로 등록, get()/list_names() 로 조회.
"""
from src.strategy.base import Strategy

_registry: dict[str, type[Strategy]] = {}


def register(name: str):
    """전략 클래스에 붙이는 등록 데코레이터."""
    def decorator(cls: type[Strategy]) -> type[Strategy]:
        _registry[name] = cls
        return cls
    return decorator


def get(name: str) -> type[Strategy]:
    if name not in _registry:
        raise KeyError(f"전략 '{name}' 미등록. 등록된 전략: {list_names()}")
    return _registry[name]


def list_names() -> list[str]:
    return sorted(_registry)
