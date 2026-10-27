"""
compiler/symbol_table.py
Scoped symbol table with push/pop scope semantics.
Supports global scope, function scope, and nested block scopes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from compiler.models import SourceSpan


@dataclass
class Symbol:
    name: str
    type_name: str
    kind: str                    # "variable" | "function" | "parameter"
    span: SourceSpan = field(default_factory=SourceSpan.unknown)
    # For functions
    param_types: List[str] = field(default_factory=list)
    return_type: Optional[str] = None

    def __repr__(self) -> str:
        return f"Symbol({self.name!r}: {self.type_name}, {self.kind})"


@dataclass
class Scope:
    name: str                                   # "global" | "function:<name>" | "block"
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    parent: Optional["Scope"] = None

    def define(self, sym: Symbol) -> bool:
        """Return False if already defined in THIS scope."""
        if sym.name in self.symbols:
            return False
        self.symbols[sym.name] = sym
        return True

    def lookup_local(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

    def lookup(self, name: str) -> Optional[Symbol]:
        """Walk up the scope chain."""
        scope: Optional[Scope] = self
        while scope is not None:
            sym = scope.symbols.get(name)
            if sym is not None:
                return sym
            scope = scope.parent
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "symbols": {n: {"type": s.type_name, "kind": s.kind} for n, s in self.symbols.items()},
        }


class SymbolTable:
    """
    Hierarchical symbol table using a scope stack.
    Usage:
        st = SymbolTable()
        st.push_scope("global")
        st.define(Symbol(...))
        st.push_scope("function:main")
        ...
        st.pop_scope()
    """

    def __init__(self) -> None:
        self._stack: List[Scope] = []
        self._global: Optional[Scope] = None
        self._all_scopes: List[Scope] = []

    # ---------------------------------------------------------------- scopes

    def push_scope(self, name: str) -> Scope:
        parent = self._stack[-1] if self._stack else None
        scope = Scope(name=name, parent=parent)

        if not self._stack:
            self._global = scope

        self._stack.append(scope)
        self._all_scopes.append(scope)
        return scope

    def pop_scope(self) -> Optional[Scope]:
        if self._stack:
            return self._stack.pop()
        return None

    @property
    def current_scope(self) -> Optional[Scope]:
        return self._stack[-1] if self._stack else None

    @property
    def depth(self) -> int:
        return len(self._stack)

    def in_global_scope(self) -> bool:
        return len(self._stack) == 1

    # ---------------------------------------------------------------- define / lookup

    def define(self, sym: Symbol) -> bool:
        """Define in current scope. Returns False if duplicate."""
        if not self._stack:
            raise RuntimeError("No active scope")
        return self._stack[-1].define(sym)

    def lookup(self, name: str) -> Optional[Symbol]:
        """Lookup name walking from current scope to global."""
        if not self._stack:
            return None
        return self._stack[-1].lookup(name)

    def lookup_local(self, name: str) -> Optional[Symbol]:
        """Lookup only in the current scope."""
        if not self._stack:
            return None
        return self._stack[-1].lookup_local(name)

    # ---------------------------------------------------------------- snapshot

    def snapshot(self) -> List[dict]:
        """Return a serializable representation of all scopes (for UI)."""
        return [s.to_dict() for s in self._stack]

    def full_snapshot(self) -> dict:
        """Build a snapshot containing every scope visited during analysis."""

        def _scope_dict(scope: Scope, depth: int) -> dict:
            return {
                "name": scope.name,
                "parent": scope.parent.name if scope.parent else None,
                "depth": depth,
                "symbols": {
                    name: {
                        "type": sym.type_name,
                        "kind": sym.kind,
                        "line": sym.span.start.line,
                    }
                    for name, sym in scope.symbols.items()
                },
            }

        return {
            "scopes": [
                _scope_dict(scope, self._scope_depth(scope))
                for scope in self._all_scopes
            ],
            "depth": len(self._stack),
        }

    def _scope_depth(self, scope: Scope) -> int:
        """Return the nesting depth of a scope. The global scope is depth 0."""
        depth = 0
        parent = scope.parent

        while parent is not None:
            depth += 1
            parent = parent.parent

        return depth
