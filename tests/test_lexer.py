"""tests/test_lexer.py — Unit tests for the lexer."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.lexer import CSubsetLexer
from compiler.models import DiagnosticCategory


def lex(source):
    l = CSubsetLexer()
    return l.tokenize(source)


# ---- Valid inputs ----

def test_keywords_recognized():
    tokens, diags = lex("int float char void if else while for return")
    types = [t.type for t in tokens]
    assert "INT" in types
    assert "FLOAT_TYPE" in types
    assert "CHAR_TYPE" in types
    assert "VOID" in types
    assert "IF" in types
    assert "ELSE" in types
    assert "WHILE" in types
    assert "FOR" in types
    assert "RETURN" in types
    assert not diags


def test_integer_literal():
    tokens, diags = lex("42")
    assert len(tokens) == 1
    assert tokens[0].type == "INT_LITERAL"
    assert tokens[0].lexeme == "42"
    assert not diags


def test_float_literal():
    tokens, diags = lex("3.14")
    assert tokens[0].type == "FLOAT_LITERAL"
    assert not diags


def test_float_exponent():
    tokens, diags = lex("1.5e2")
    assert tokens[0].type == "FLOAT_LITERAL"
    assert not diags


def test_char_literal():
    tokens, diags = lex("'a'")
    assert tokens[0].type == "CHAR_LITERAL"
    assert tokens[0].lexeme == "'a'"
    assert not diags


def test_string_literal():
    tokens, diags = lex('"hello world"')
    assert tokens[0].type == "STRING_LITERAL"
    assert not diags


def test_identifier():
    tokens, diags = lex("myVar")
    assert tokens[0].type == "ID"
    assert tokens[0].lexeme == "myVar"
    assert not diags


def test_operators():
    tokens, diags = lex("+ - * / % == != < <= > >= && ||")
    types = [t.type for t in tokens]
    assert "PLUS" in types
    assert "MINUS" in types
    assert "TIMES" in types
    assert "DIVIDE" in types
    assert "MODULO" in types
    assert "EQ" in types
    assert "NEQ" in types
    assert "AND" in types
    assert "OR" in types
    assert not diags


def test_delimiters():
    tokens, diags = lex("( ) { } ; ,")
    types = [t.type for t in tokens]
    assert "LPAREN" in types
    assert "RPAREN" in types
    assert "LBRACE" in types
    assert "RBRACE" in types
    assert "SEMICOLON" in types
    assert "COMMA" in types
    assert not diags


def test_line_comment_ignored():
    tokens, diags = lex("int x; // this is a comment\nint y;")
    assert not any(t.lexeme.startswith("//") for t in tokens)
    assert not diags


def test_block_comment_ignored():
    tokens, diags = lex("int /* mid */ x;")
    assert not any("/*" in t.lexeme for t in tokens)
    assert not diags


def test_line_tracking():
    tokens, diags = lex("int\nx\n=\n5;")
    int_tok = next(t for t in tokens if t.type == "INT")
    x_tok = next(t for t in tokens if t.type == "ID")
    assert int_tok.span.start.line == 1
    assert x_tok.span.start.line == 2


# ---- Invalid inputs ----

def test_illegal_character():
    tokens, diags = lex("int x = 10 @ 5;")
    assert len(diags) == 1
    assert diags[0].category == DiagnosticCategory.LEXICAL
    assert diags[0].code == "LEX001"
    assert "@" in diags[0].message


def test_multiple_illegal_chars():
    tokens, diags = lex("@ # $")
    assert len(diags) >= 3
    for d in diags:
        assert d.category == DiagnosticCategory.LEXICAL


def test_unterminated_string():
    tokens, diags = lex('int x = "unterminated;')
    assert any(d.code == "LEX003" for d in diags)


def test_full_program_tokenized():
    src = """
    int main() {
        int x = 10;
        return x;
    }
    """
    tokens, diags = lex(src)
    assert len(tokens) > 0
    assert not diags
