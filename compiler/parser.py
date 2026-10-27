"""
compiler/parser.py

PLY Yacc parser for the supported C subset.

Builds AST nodes and produces Diagnostic objects for syntax errors.
"""

from __future__ import annotations

import importlib
import logging
from typing import List, Optional, Tuple

try:
    yacc = importlib.import_module("ply.yacc")
except ModuleNotFoundError as exc:
    if exc.name not in {"ply", "ply.yacc"}:
        raise
    yacc = None

from compiler.ast_nodes import (
    Assign,
    BinaryExpr,
    Block,
    CharLiteral,
    ExprStmt,
    FloatLiteral,
    ForStmt,
    FuncCall,
    FuncDecl,
    Identifier,
    IfStmt,
    IntLiteral,
    Param,
    Program,
    ReturnStmt,
    StringLiteral,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)
from compiler.lexer import CSubsetLexer
from compiler.models import (
    Diagnostic,
    DiagnosticCategory,
    Severity,
    SourcePosition,
    SourceSpan,
    Token,
)

log = logging.getLogger(__name__)


def _span_from_p(p, idx: int = 1) -> SourceSpan:
    """Build a SourceSpan from a PLY production rule at position idx."""
    try:
        line = p.lineno(idx)
        col = p.lexpos(idx)
        return SourceSpan(
            SourcePosition(col, line, 1),
            SourcePosition(col + 1, line, 2),
        )
    except Exception:
        return SourceSpan.unknown()


class CSubsetParser:
    """
    Stateful wrapper around PLY Yacc.
    Instantiate a fresh parser for each analysis.
    """

    # PLY requires tokens to be available at class level.
    from compiler.lexer import tokens  # noqa: F401

    precedence = (
        ("right", "ASSIGN"),
        ("left", "OR"),
        ("left", "AND"),
        ("left", "EQ", "NEQ"),
        ("left", "LT", "LE", "GT", "GE"),
        ("left", "PLUS", "MINUS"),
        ("left", "TIMES", "DIVIDE", "MODULO"),
        ("right", "UMINUS", "NOT"),
    )

    # ------------------------------------------------------------------
    # Grammar rules
    # ------------------------------------------------------------------

    def p_program(self, p):
        """program : declaration_list"""
        p[0] = Program(declarations=p[1], span=_span_from_p(p))

    def p_declaration_list(self, p):
        """declaration_list : declaration_list declaration
                            | declaration"""
        if len(p) == 3:
            p[0] = p[1] + [p[2]]
        else:
            p[0] = [p[1]] if p[1] is not None else []

    def p_declaration_var(self, p):
        """declaration : var_decl"""
        p[0] = p[1]

    def p_declaration_fun(self, p):
        """declaration : fun_decl"""
        p[0] = p[1]

    # Variable declarations

    def p_var_decl_plain(self, p):
        """var_decl : type_spec ID SEMICOLON"""
        p[0] = VarDecl(
            type_name=p[1],
            name=p[2],
            initializer=None,
            span=_span_from_p(p),
        )

    def p_var_decl_init(self, p):
        """var_decl : type_spec ID ASSIGN expr SEMICOLON"""
        p[0] = VarDecl(
            type_name=p[1],
            name=p[2],
            initializer=p[4],
            span=_span_from_p(p),
        )

    def p_var_decl_init_missing_semicolon(self, p):
        """var_decl : type_spec ID ASSIGN expr error"""
        p[0] = VarDecl(
            type_name=p[1],
            name=p[2],
            initializer=p[4],
            span=_span_from_p(p),
        )

    # Function declarations

    def p_fun_decl(self, p):
        """fun_decl : type_spec ID LPAREN params RPAREN compound_stmt"""
        p[0] = FuncDecl(
            return_type=p[1],
            name=p[2],
            params=p[4] if p[4] else [],
            body=p[6],
            span=_span_from_p(p),
        )

    def p_params_void(self, p):
        """params : VOID"""
        p[0] = []

    def p_params_list(self, p):
        """params : param_list"""
        p[0] = p[1]

    def p_params_empty(self, p):
        """params : empty"""
        p[0] = []

    def p_param_list(self, p):
        """param_list : param_list COMMA param
                      | param"""
        if len(p) == 4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]

    def p_param(self, p):
        """param : type_spec ID"""
        p[0] = Param(type_name=p[1], name=p[2], span=_span_from_p(p))

    # Type specifiers

    def p_type_spec_int(self, p):
        """type_spec : INT"""
        p[0] = "int"

    def p_type_spec_float(self, p):
        """type_spec : FLOAT_TYPE"""
        p[0] = "float"

    def p_type_spec_char(self, p):
        """type_spec : CHAR_TYPE"""
        p[0] = "char"

    def p_type_spec_void(self, p):
        """type_spec : VOID"""
        p[0] = "void"

    # Compound statements

    def p_compound_stmt(self, p):
        """compound_stmt : LBRACE statement_list RBRACE"""
        p[0] = Block(statements=p[2], span=_span_from_p(p))

    def p_statement_list_many(self, p):
        """statement_list : statement_list statement"""
        p[0] = p[1] + [p[2]]

    def p_statement_list_empty(self, p):
        """statement_list : empty"""
        p[0] = []

    # Statements

    def p_stmt_expr(self, p):
        """statement : expr_stmt"""
        p[0] = p[1]

    def p_stmt_compound(self, p):
        """statement : compound_stmt"""
        p[0] = p[1]

    def p_stmt_if(self, p):
        """statement : if_stmt"""
        p[0] = p[1]

    def p_stmt_while(self, p):
        """statement : while_stmt"""
        p[0] = p[1]

    def p_stmt_for(self, p):
        """statement : for_stmt"""
        p[0] = p[1]

    def p_stmt_return(self, p):
        """statement : return_stmt"""
        p[0] = p[1]

    def p_stmt_var_decl(self, p):
        """statement : var_decl"""
        p[0] = p[1]

    # Specific statements

    def p_expr_stmt_expr(self, p):
        """expr_stmt : expr SEMICOLON"""
        p[0] = ExprStmt(expr=p[1], span=_span_from_p(p))

    def p_expr_stmt_empty(self, p):
        """expr_stmt : SEMICOLON"""
        p[0] = ExprStmt(expr=None, span=_span_from_p(p))

    def p_if_stmt(self, p):
        """if_stmt : IF LPAREN expr RPAREN statement"""
        p[0] = IfStmt(
            condition=p[3],
            then_branch=p[5],
            else_branch=None,
            span=_span_from_p(p),
        )

    def p_if_else_stmt(self, p):
        """if_stmt : IF LPAREN expr RPAREN statement ELSE statement"""
        p[0] = IfStmt(
            condition=p[3],
            then_branch=p[5],
            else_branch=p[7],
            span=_span_from_p(p),
        )

    def p_while_stmt(self, p):
        """while_stmt : WHILE LPAREN expr RPAREN statement"""
        p[0] = WhileStmt(
            condition=p[3],
            body=p[5],
            span=_span_from_p(p),
        )

    def p_while_stmt_missing_condition(self, p):
        """while_stmt : WHILE LPAREN error RPAREN statement"""
        p[0] = WhileStmt(
            condition=IntLiteral(value=0, span=_span_from_p(p)),
            body=p[5],
            span=_span_from_p(p),
        )

    def p_for_stmt(self, p):
        """for_stmt : FOR LPAREN expr_stmt expr_stmt RPAREN statement"""
        p[0] = ForStmt(
            init=p[3],
            condition=p[4],
            update=None,
            body=p[6],
            span=_span_from_p(p),
        )

    def p_for_stmt_update(self, p):
        """for_stmt : FOR LPAREN expr_stmt expr_stmt expr RPAREN statement"""
        p[0] = ForStmt(
            init=p[3],
            condition=p[4],
            update=p[5],
            body=p[7],
            span=_span_from_p(p),
        )

    def p_for_stmt_decl(self, p):
        """for_stmt : FOR LPAREN var_decl expr_stmt RPAREN statement"""
        p[0] = ForStmt(
            init=p[3],
            condition=p[4],
            update=None,
            body=p[6],
            span=_span_from_p(p),
        )

    def p_for_stmt_decl_update(self, p):
        """for_stmt : FOR LPAREN var_decl expr_stmt expr RPAREN statement"""
        p[0] = ForStmt(
            init=p[3],
            condition=p[4],
            update=p[5],
            body=p[7],
            span=_span_from_p(p),
        )

    def p_return_stmt(self, p):
        """return_stmt : RETURN expr SEMICOLON"""
        p[0] = ReturnStmt(value=p[2], span=_span_from_p(p))

    def p_return_stmt_void(self, p):
        """return_stmt : RETURN SEMICOLON"""
        p[0] = ReturnStmt(value=None, span=_span_from_p(p))

    # Expressions

    def p_expr_assign(self, p):
        """expr : ID ASSIGN expr"""
        p[0] = Assign(name=p[1], value=p[3], span=_span_from_p(p))

    def p_expr_simple(self, p):
        """expr : simple_expr"""
        p[0] = p[1]

    def p_simple_expr_rel(self, p):
        """simple_expr : add_expr relop add_expr"""
        p[0] = BinaryExpr(
            op=p[2],
            left=p[1],
            right=p[3],
            span=_span_from_p(p),
        )

    def p_simple_expr_add(self, p):
        """simple_expr : add_expr"""
        p[0] = p[1]

    def p_relop(self, p):
        """relop : LT
                 | LE
                 | GT
                 | GE
                 | EQ
                 | NEQ"""
        p[0] = p[1]

    def p_add_expr(self, p):
        """add_expr : add_expr PLUS term
                    | add_expr MINUS term"""
        p[0] = BinaryExpr(
            op=p[2],
            left=p[1],
            right=p[3],
            span=_span_from_p(p),
        )

    def p_add_expr_term(self, p):
        """add_expr : term"""
        p[0] = p[1]

    def p_term_mul(self, p):
        """term : term TIMES factor
                | term DIVIDE factor
                | term MODULO factor"""
        p[0] = BinaryExpr(
            op=p[2],
            left=p[1],
            right=p[3],
            span=_span_from_p(p),
        )

    def p_term_factor(self, p):
        """term : factor"""
        p[0] = p[1]

    def p_factor_paren(self, p):
        """factor : LPAREN expr RPAREN"""
        p[0] = p[2]

    def p_factor_id(self, p):
        """factor : ID"""
        p[0] = Identifier(name=p[1], span=_span_from_p(p))

    def p_factor_call(self, p):
        """factor : ID LPAREN args RPAREN"""
        p[0] = FuncCall(
            name=p[1],
            arguments=p[3],
            span=_span_from_p(p),
        )

    def p_factor_int(self, p):
        """factor : INT_LITERAL"""
        p[0] = IntLiteral(value=p[1], span=_span_from_p(p))

    def p_factor_float(self, p):
        """factor : FLOAT_LITERAL"""
        p[0] = FloatLiteral(value=p[1], span=_span_from_p(p))

    def p_factor_char(self, p):
        """factor : CHAR_LITERAL"""
        p[0] = CharLiteral(value=p[1], span=_span_from_p(p))

    def p_factor_string(self, p):
        """factor : STRING_LITERAL"""
        p[0] = StringLiteral(value=p[1], span=_span_from_p(p))

    def p_factor_uminus(self, p):
        """factor : MINUS factor %prec UMINUS"""
        p[0] = UnaryExpr(op="-", operand=p[2], span=_span_from_p(p))

    def p_factor_not(self, p):
        """factor : NOT factor"""
        p[0] = UnaryExpr(op="!", operand=p[2], span=_span_from_p(p))

    def p_and_expr(self, p):
        """simple_expr : simple_expr AND add_expr"""
        p[0] = BinaryExpr(
            op="&&",
            left=p[1],
            right=p[3],
            span=_span_from_p(p),
        )

    def p_or_expr(self, p):
        """simple_expr : simple_expr OR add_expr"""
        p[0] = BinaryExpr(
            op="||",
            left=p[1],
            right=p[3],
            span=_span_from_p(p),
        )

    def p_args_list(self, p):
        """args : arg_list"""
        p[0] = p[1]

    def p_args_empty(self, p):
        """args : empty"""
        p[0] = []

    def p_arg_list(self, p):
        """arg_list : arg_list COMMA expr
                    | expr"""
        if len(p) == 4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]

    def p_empty(self, p):
        """empty :"""
        p[0] = None

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def p_error(self, p):
        """Report a syntax error and recover at a statement boundary."""
        if p is None:
            self._add_diag(
                "SYN001",
                "Unexpected end of file",
                SourceSpan.unknown(),
            )
            return

        last_nl = self._source.rfind("\n", 0, p.lexpos)
        col = p.lexpos - last_nl

        token_text = str(p.value)
        span = SourceSpan(
            SourcePosition(p.lexpos, p.lineno, col),
            SourcePosition(
                p.lexpos + len(token_text),
                p.lineno,
                col + max(len(token_text), 1),
            ),
        )

        self._add_diag(
            "SYN001",
            f"Syntax error at '{p.value}' (token type: {p.type})",
            span,
        )

        # Preserve the project's existing recovery behavior for now.
        # More advanced recovery should be implemented with grammar-level
        # error productions and tested against the full parser test suite.
        

    def _add_diag(
        self,
        code: str,
        msg: str,
        span: SourceSpan,
    ) -> None:
        self._diagnostics.append(
            Diagnostic(
                code=code,
                category=DiagnosticCategory.SYNTAX,
                message=msg,
                severity=Severity.ERROR,
                span=span,
                source="parser",
            )
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        if yacc is None:
            raise ImportError(
                "PLY is required to parse source code. Install it with 'pip install ply'."
            )

        self._diagnostics: List[Diagnostic] = []
        self._source = ""
        self._lexer_wrapper = CSubsetLexer()
        self._parser = yacc.yacc(
            module=self,
            debug=False,
            errorlog=yacc.NullLogger(),
            outputdir="/tmp",
            write_tables=False,
        )

    def parse(
        self,
        source: str,
        lex_tokens: List[Token],
        lex_diags: List[Diagnostic],
    ) -> Tuple[Optional[Program], List[Diagnostic]]:
        """
        Parse source and return (AST, diagnostics).

        lex_diags are preserved and combined with parser diagnostics.
        lex_tokens is accepted for API compatibility; the parser creates
        its own fresh lexer instance from the source text.
        """
        self._source = source
        self._diagnostics = list(lex_diags)

        ply_lexer = self._lexer_wrapper._lexer.clone()
        ply_lexer.input(source)
        ply_lexer.lineno = 1

        try:
            result = self._parser.parse(
                input=source,
                lexer=ply_lexer,
                debug=False,
                tracking=True,
            )
        except Exception as exc:
            log.warning("Parser exception: %s", exc)
            result = None
            self._add_diag(
                "SYN999",
                f"Internal parser error: {exc}",
                SourceSpan.unknown(),
            )

        return result, self._diagnostics
