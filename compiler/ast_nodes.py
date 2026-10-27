"""
compiler/ast_nodes.py
Custom AST node classes for the supported C subset.
Every node carries a SourceSpan so that diagnostics can pinpoint locations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional
from compiler.models import SourceSpan


# ---------------------------------------------------------------------------
# Base node
# ---------------------------------------------------------------------------

@dataclass
class ASTNode:
    span: SourceSpan = field(default_factory=SourceSpan.unknown)

    def accept(self, visitor: "ASTVisitor") -> Any:
        raise NotImplementedError(f"{type(self).__name__}.accept not implemented")

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

@dataclass
class Program(ASTNode):
    declarations: List[ASTNode] = field(default_factory=list)

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_program(self)


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------

@dataclass
class VarDecl(ASTNode):
    type_name: str = ""
    name: str = ""
    initializer: Optional[ASTNode] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_var_decl(self)


@dataclass
class Param(ASTNode):
    type_name: str = ""
    name: str = ""

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_param(self)


@dataclass
class FuncDecl(ASTNode):
    return_type: str = ""
    name: str = ""
    params: List[Param] = field(default_factory=list)
    body: Optional["Block"] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_func_decl(self)


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

@dataclass
class Block(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_block(self)


@dataclass
class ExprStmt(ASTNode):
    expr: Optional[ASTNode] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_expr_stmt(self)


@dataclass
class IfStmt(ASTNode):
    condition: Optional[ASTNode] = None
    then_branch: Optional[ASTNode] = None
    else_branch: Optional[ASTNode] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_if_stmt(self)


@dataclass
class WhileStmt(ASTNode):
    condition: Optional[ASTNode] = None
    body: Optional[ASTNode] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_while_stmt(self)


@dataclass
class ForStmt(ASTNode):
    init: Optional[ASTNode] = None      # ExprStmt or VarDecl
    condition: Optional[ASTNode] = None
    update: Optional[ASTNode] = None
    body: Optional[ASTNode] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_for_stmt(self)


@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_return_stmt(self)


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

@dataclass
class Assign(ASTNode):
    name: str = ""
    value: Optional[ASTNode] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_assign(self)


@dataclass
class BinaryExpr(ASTNode):
    op: str = ""
    left: Optional[ASTNode] = None
    right: Optional[ASTNode] = None
    inferred_type: Optional[str] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_binary_expr(self)


@dataclass
class UnaryExpr(ASTNode):
    op: str = ""
    operand: Optional[ASTNode] = None
    inferred_type: Optional[str] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_unary_expr(self)


@dataclass
class Identifier(ASTNode):
    name: str = ""
    inferred_type: Optional[str] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_identifier(self)


@dataclass
class IntLiteral(ASTNode):
    value: int = 0

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_int_literal(self)


@dataclass
class FloatLiteral(ASTNode):
    value: float = 0.0

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_float_literal(self)


@dataclass
class CharLiteral(ASTNode):
    value: str = ""

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_char_literal(self)


@dataclass
class StringLiteral(ASTNode):
    value: str = ""

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_string_literal(self)


@dataclass
class FuncCall(ASTNode):
    name: str = ""
    arguments: List[ASTNode] = field(default_factory=list)
    inferred_type: Optional[str] = None

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_func_call(self)


# ---------------------------------------------------------------------------
# Visitor base
# ---------------------------------------------------------------------------

class ASTVisitor:
    """Base visitor — subclass and override methods as needed."""

    def visit_program(self, node: Program) -> Any:
        for decl in node.declarations:
            decl.accept(self)

    def visit_var_decl(self, node: VarDecl) -> Any:
        if node.initializer:
            node.initializer.accept(self)

    def visit_param(self, node: Param) -> Any:
        pass

    def visit_func_decl(self, node: FuncDecl) -> Any:
        for p in node.params:
            p.accept(self)
        if node.body:
            node.body.accept(self)

    def visit_block(self, node: Block) -> Any:
        for stmt in node.statements:
            stmt.accept(self)

    def visit_expr_stmt(self, node: ExprStmt) -> Any:
        if node.expr:
            node.expr.accept(self)

    def visit_if_stmt(self, node: IfStmt) -> Any:
        if node.condition:
            node.condition.accept(self)
        if node.then_branch:
            node.then_branch.accept(self)
        if node.else_branch:
            node.else_branch.accept(self)

    def visit_while_stmt(self, node: WhileStmt) -> Any:
        if node.condition:
            node.condition.accept(self)
        if node.body:
            node.body.accept(self)

    def visit_for_stmt(self, node: ForStmt) -> Any:
        if node.init:
            node.init.accept(self)
        if node.condition:
            node.condition.accept(self)
        if node.update:
            node.update.accept(self)
        if node.body:
            node.body.accept(self)

    def visit_return_stmt(self, node: ReturnStmt) -> Any:
        if node.value:
            node.value.accept(self)

    def visit_assign(self, node: Assign) -> Any:
        if node.value:
            node.value.accept(self)

    def visit_binary_expr(self, node: BinaryExpr) -> Any:
        if node.left:
            node.left.accept(self)
        if node.right:
            node.right.accept(self)

    def visit_unary_expr(self, node: UnaryExpr) -> Any:
        if node.operand:
            node.operand.accept(self)

    def visit_identifier(self, node: Identifier) -> Any:
        pass

    def visit_int_literal(self, node: IntLiteral) -> Any:
        pass

    def visit_float_literal(self, node: FloatLiteral) -> Any:
        pass

    def visit_char_literal(self, node: CharLiteral) -> Any:
        pass

    def visit_string_literal(self, node: StringLiteral) -> Any:
        pass

    def visit_func_call(self, node: FuncCall) -> Any:
        for arg in node.arguments:
            arg.accept(self)


# ---------------------------------------------------------------------------
# Pretty-printer
# ---------------------------------------------------------------------------

class ASTPrinter(ASTVisitor):
    """Produces a human-readable indented tree string."""

    def __init__(self) -> None:
        self._lines: List[str] = []
        self._indent = 0

    def _emit(self, text: str) -> None:
        self._lines.append("  " * self._indent + text)

    def render(self, root: ASTNode) -> str:
        self._lines = []
        self._indent = 0
        root.accept(self)
        return "\n".join(self._lines)

    def visit_program(self, node: Program) -> None:
        self._emit("Program")
        self._indent += 1
        for d in node.declarations:
            d.accept(self)
        self._indent -= 1

    def visit_var_decl(self, node: VarDecl) -> None:
        init_str = ""
        self._emit(f"VarDecl [{node.type_name}] {node.name}{init_str}")
        if node.initializer:
            self._indent += 1
            node.initializer.accept(self)
            self._indent -= 1

    def visit_param(self, node: Param) -> None:
        self._emit(f"Param [{node.type_name}] {node.name}")

    def visit_func_decl(self, node: FuncDecl) -> None:
        self._emit(f"FuncDecl [{node.return_type}] {node.name}()")
        self._indent += 1
        for p in node.params:
            p.accept(self)
        if node.body:
            node.body.accept(self)
        self._indent -= 1

    def visit_block(self, node: Block) -> None:
        self._emit("Block")
        self._indent += 1
        for s in node.statements:
            s.accept(self)
        self._indent -= 1

    def visit_expr_stmt(self, node: ExprStmt) -> None:
        self._emit("ExprStmt")
        if node.expr:
            self._indent += 1
            node.expr.accept(self)
            self._indent -= 1

    def visit_if_stmt(self, node: IfStmt) -> None:
        self._emit("IfStmt")
        self._indent += 1
        self._emit("condition:")
        self._indent += 1
        if node.condition:
            node.condition.accept(self)
        self._indent -= 1
        self._emit("then:")
        self._indent += 1
        if node.then_branch:
            node.then_branch.accept(self)
        self._indent -= 1
        if node.else_branch:
            self._emit("else:")
            self._indent += 1
            node.else_branch.accept(self)
            self._indent -= 1
        self._indent -= 1

    def visit_while_stmt(self, node: WhileStmt) -> None:
        self._emit("WhileStmt")
        self._indent += 1
        self._emit("condition:")
        self._indent += 1
        if node.condition:
            node.condition.accept(self)
        self._indent -= 1
        self._emit("body:")
        self._indent += 1
        if node.body:
            node.body.accept(self)
        self._indent -= 1
        self._indent -= 1

    def visit_for_stmt(self, node: ForStmt) -> None:
        self._emit("ForStmt")
        self._indent += 1
        if node.init:
            self._emit("init:"); self._indent += 1; node.init.accept(self); self._indent -= 1
        if node.condition:
            self._emit("cond:"); self._indent += 1; node.condition.accept(self); self._indent -= 1
        if node.update:
            self._emit("update:"); self._indent += 1; node.update.accept(self); self._indent -= 1
        if node.body:
            self._emit("body:"); self._indent += 1; node.body.accept(self); self._indent -= 1
        self._indent -= 1

    def visit_return_stmt(self, node: ReturnStmt) -> None:
        self._emit("ReturnStmt")
        if node.value:
            self._indent += 1
            node.value.accept(self)
            self._indent -= 1

    def visit_assign(self, node: Assign) -> None:
        self._emit(f"Assign {node.name} =")
        self._indent += 1
        if node.value:
            node.value.accept(self)
        self._indent -= 1

    def visit_binary_expr(self, node: BinaryExpr) -> None:
        typ = f" :{node.inferred_type}" if node.inferred_type else ""
        self._emit(f"BinaryExpr [{node.op}]{typ}")
        self._indent += 1
        if node.left:
            node.left.accept(self)
        if node.right:
            node.right.accept(self)
        self._indent -= 1

    def visit_unary_expr(self, node: UnaryExpr) -> None:
        self._emit(f"UnaryExpr [{node.op}]")
        self._indent += 1
        if node.operand:
            node.operand.accept(self)
        self._indent -= 1

    def visit_identifier(self, node: Identifier) -> None:
        typ = f" :{node.inferred_type}" if node.inferred_type else ""
        self._emit(f"Identifier {node.name}{typ}")

    def visit_int_literal(self, node: IntLiteral) -> None:
        self._emit(f"IntLiteral {node.value}")

    def visit_float_literal(self, node: FloatLiteral) -> None:
        self._emit(f"FloatLiteral {node.value}")

    def visit_char_literal(self, node: CharLiteral) -> None:
        self._emit(f"CharLiteral {node.value!r}")

    def visit_string_literal(self, node: StringLiteral) -> None:
        self._emit(f"StringLiteral {node.value!r}")

    def visit_func_call(self, node: FuncCall) -> None:
        self._emit(f"FuncCall {node.name}()")
        self._indent += 1
        for arg in node.arguments:
            arg.accept(self)
        self._indent -= 1
