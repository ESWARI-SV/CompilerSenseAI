"""tests/test_parser.py — Unit tests for the parser and AST construction."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.lexer import CSubsetLexer
from compiler.parser import CSubsetParser
from compiler.ast_nodes import (
    Program, FuncDecl, VarDecl, Block, ReturnStmt,
    IfStmt, WhileStmt, ForStmt, BinaryExpr, IntLiteral,
)
from compiler.models import DiagnosticCategory, Severity


def parse(source):
    lexer = CSubsetLexer()
    tokens, lex_diags = lexer.tokenize(source)
    parser = CSubsetParser()
    ast, diags = parser.parse(source, tokens, lex_diags)
    return ast, diags


# ---- Valid programs ----

def test_parse_empty_main():
    src = "int main() { return 0; }"
    ast, diags = parse(src)
    assert ast is not None
    syntax_errors = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert not syntax_errors


def test_parse_var_decl():
    src = "int main() { int x = 5; return x; }"
    ast, diags = parse(src)
    assert ast is not None
    assert isinstance(ast, Program)
    assert len(ast.declarations) == 1
    func = ast.declarations[0]
    assert isinstance(func, FuncDecl)
    assert func.name == "main"


def test_parse_if_else():
    src = """
    int main() {
        int x = 10;
        if (x > 5) { x = 1; } else { x = 0; }
        return x;
    }
    """
    ast, diags = parse(src)
    assert ast is not None
    syntax_errs = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert not syntax_errs


def test_parse_while():
    src = """
    int main() {
        int i = 0;
        while (i < 10) { i = i + 1; }
        return i;
    }
    """
    ast, diags = parse(src)
    assert ast is not None
    syntax_errs = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert not syntax_errs


def test_parse_for():
    src = """
    int main() {
        int i;
        for (i = 0; i < 5; i = i + 1) { }
        return i;
    }
    """
    ast, diags = parse(src)
    assert ast is not None


def test_parse_function_call():
    src = """
    int add(int a, int b) { return a + b; }
    int main() { int r = add(1, 2); return r; }
    """
    ast, diags = parse(src)
    assert ast is not None
    syntax_errs = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert not syntax_errs


def test_parse_binary_expressions():
    src = "int main() { int x = 3 + 4 * 2 - 1; return x; }"
    ast, diags = parse(src)
    assert ast is not None
    syntax_errs = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert not syntax_errs


def test_parse_logical_expr():
    src = "int main() { int x = 1; int y = (x > 0) && (x < 10); return y; }"
    ast, diags = parse(src)
    assert ast is not None


def test_parse_multiple_functions():
    src = """
    int foo() { return 1; }
    int bar() { return 2; }
    int main() { return foo() + bar(); }
    """
    ast, diags = parse(src)
    assert ast is not None
    assert len(ast.declarations) == 3


# ---- Error cases ----

def test_missing_semicolon():
    src = "int main() { int x = 10\n return x; }"
    ast, diags = parse(src)
    syntax_errs = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert len(syntax_errs) >= 1


def test_missing_closing_brace():
    src = "int main() { int x = 5; return x;"
    ast, diags = parse(src)
    syntax_errs = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert len(syntax_errs) >= 1


def test_unexpected_token():
    src = "int main() { return; return; }"
    # This should parse; two returns are syntactically valid
    ast, diags = parse(src)
    syntax_errs = [d for d in diags if d.category == DiagnosticCategory.SYNTAX]
    assert len(syntax_errs) == 0


def test_lex_errors_preserved_in_parser():
    src = "int main() { int x = 10 @; return x; }"
    ast, diags = parse(src)
    lex_errs = [d for d in diags if d.category == DiagnosticCategory.LEXICAL]
    assert len(lex_errs) >= 1
