"""tests/test_semantic.py — Semantic analyser tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.orchestrator import Orchestrator
from compiler.models import DiagnosticCategory, Severity


def analyze(src):
    return Orchestrator().analyze(src)


def sem_errors(result):
    return [d for d in result.diagnostics
            if d.category == DiagnosticCategory.SEMANTIC and d.severity == Severity.ERROR]


# ---- Valid programs (no semantic errors expected) ----

def test_valid_simple():
    r = analyze("int main() { int x = 5; return x; }")
    assert not sem_errors(r)


def test_valid_function_call():
    r = analyze("int add(int a, int b) { return a + b; }\nint main() { int r = add(1, 2); return r; }")
    assert not sem_errors(r)


def test_valid_float_widening():
    r = analyze("int main() { float f = 5; return 0; }")
    # int → float widening is allowed
    errs = sem_errors(r)
    assert not errs


def test_valid_char_int_assignment():
    r = analyze("int main() { char c = 'A'; int x = c; return x; }")
    errs = sem_errors(r)
    assert not errs


def test_valid_if_else():
    r = analyze("int main() { int x = 5; if (x > 0) { x = 1; } else { x = 0; } return x; }")
    assert not sem_errors(r)


# ---- Error cases ----

def test_undeclared_identifier():
    r = analyze("int main() { return y; }")
    errs = sem_errors(r)
    assert any(e.code == "SEM001" for e in errs)


def test_undeclared_in_assignment():
    r = analyze("int main() { z = 5; return 0; }")
    errs = sem_errors(r)
    assert any(e.code == "SEM001" for e in errs)


def test_duplicate_declaration():
    r = analyze("int main() { int x = 1; int x = 2; return x; }")
    errs = sem_errors(r)
    assert any(e.code == "SEM002" for e in errs)


def test_type_mismatch_int_string():
    r = analyze('int main() { int x = "hello"; return x; }')
    errs = sem_errors(r)
    assert any(e.code == "SEM003" for e in errs)


def test_type_mismatch_float_string():
    r = analyze('int main() { float x = "hello"; return x; }')
    errs = sem_errors(r)
    assert any(e.code == "SEM003" for e in errs)


def test_incompatible_char_float_assignment_reports_type_error():
    source = """
    int main() {
        char c;
        float f;
        c = f;
        return 0;
    }
    """
    r = analyze(source)
    errs = sem_errors(r)

    assert any(
        e.code == "SEM003"
        for e in errs
    ), "Assigning a float to a char should report a type error"


def test_void_variable():
    r = analyze("int main() { void x; return 0; }")
    errs = sem_errors(r)
    assert any(e.code == "SEM006" for e in errs)


def test_void_function_returns_value():
    r = analyze("void foo() { return 42; }\nint main() { foo(); return 0; }")
    errs = sem_errors(r)
    assert any(e.code == "SEM007" for e in errs)


def test_undeclared_function():
    r = analyze("int main() { int r = foo(1); return r; }")
    errs = sem_errors(r)
    assert any(e.code == "SEM001" for e in errs)


def test_wrong_arg_count():
    r = analyze("int add(int a, int b) { return a + b; }\nint main() { int r = add(1, 2, 3); return r; }")
    errs = sem_errors(r)
    assert any(e.code == "SEM010" for e in errs)


def test_duplicate_function():
    r = analyze("int foo() { return 1; }\nint foo() { return 2; }\nint main() { return foo(); }")
    errs = sem_errors(r)
    assert any(e.code == "SEM002" for e in errs)


def test_scoping_inner_shadows_outer():
    # Inner variable with same name as outer — allowed in separate scopes
    r = analyze("""
    int main() {
        int x = 1;
        {
            int x = 2;
        }
        return x;
    }
    """)
    # Shadowing in inner block is not an error — different scope
    errs = sem_errors(r)
    # Should NOT report SEM002 for the inner x (different scope)
    dup_errs = [e for e in errs if e.code == "SEM002"]
    assert not dup_errs

def test_arithmetic_with_string_reports_type_error():
    r = analyze('int main() { int x = 5 + "hello"; return 0; }')
    errs = sem_errors(r)
    assert errs, "Incompatible arithmetic operands should report a semantic error"


def test_valid_numeric_arithmetic_has_no_type_error():
    r = analyze("int main() { float x = 5 + 3.5; return 0; }")
    errs = sem_errors(r)
    assert not errs


def test_non_void_function_returning_nothing_reports_error():
    r = analyze("int calculate() { return; }\nint main() { return 0; }")
    errs = sem_errors(r)

    assert any(
        e.code == "SEM008"
        for e in errs
    ), "A non-void function returning nothing should report a semantic error"


def test_division_by_zero_reports_semantic_error():
    r = analyze("int main() { int x = 10 / 0; return x; }")
    errs = sem_errors(r)

    assert any(
        e.code == "SEM012"
        for e in errs
    ), "Division by a literal zero should report a semantic error"


def test_modulo_with_float_operand_reports_type_error():
    r = analyze("int main() { float x = 5.5 % 2; return 0; }")
    errs = sem_errors(r)

    assert any(
        e.code == "SEM011"
        for e in errs
    ), "Modulo with a floating-point operand should report a semantic error"


def test_unary_minus_with_string_reports_type_error():
    r = analyze('int main() { int x = -"hello"; return 0; }')
    errs = sem_errors(r)

    assert any(
        e.code == "SEM011"
        for e in errs
    ), "Unary minus with a string operand should report a semantic error"


def test_valid_logical_not_on_integer():
    r = analyze("int main() { int x = 5; int y = !x; return y; }")
    assert not sem_errors(r)


def test_logical_not_on_void_expression_reports_type_error():
    source = """
    void greet() {
        return;
    }
    int main() {
        int x = !greet();
        return 0;
    }
    """
    r = analyze(source)
    errs = sem_errors(r)

    assert any(
        e.code == "SEM011"
        for e in errs
    ), "Logical NOT on a void expression should report a semantic error"

def test_logical_and_on_void_expression_reports_type_error():
    source = """
    void greet() {
        return;
    }
    int main() {
        int x = greet() && 1;
        return 0;
    }
    """
    r = analyze(source)
    errs = sem_errors(r)

    assert any(
        e.code == "SEM011"
        for e in errs
    ), "Logical AND with a void operand should report a semantic error"

def test_logical_or_on_void_expression_reports_type_error():
    source = """
    void greet() {
        return;
    }
    int main() {
        int x = greet() || 1;
        return 0;
    }
    """
    r = analyze(source)
    errs = sem_errors(r)

    assert any(
        e.code == "SEM011"
        for e in errs
    ), "Logical OR with a void operand should report a semantic error"

def test_valid_logical_and_or_on_integers():
    source = """
    int main() {
        int a = 1;
        int b = 0;
        int x = a && b;
        int y = a || b;
        return x + y;
    }
    """
    r = analyze(source)
    assert not sem_errors(r), "Valid logical AND and OR should not report semantic errors"

def test_valid_logical_and_or_on_pointer():
    source = """
    int main() {
        int *ptr;
        int x = ptr && 1;
        int y = ptr || 0;
        return x + y;
    }
    """
    r = analyze(source)
    assert not sem_errors(r), "Logical AND and OR should accept pointer operands"

def test_valid_logical_and_or_on_float_and_char():
    source = """
    int main() {
        float f = 2.5;
        char c = 'A';
        int x = f && c;
        int y = f || c;
        return x + y;
    }
    """
    r = analyze(source)
    assert not sem_errors(r), "Logical operators should accept float and char operands"

def test_valid_logical_and_or_on_string():
    source = """
    int main() {
        int x = "hello" && 1;
        int y = "world" || 0;
        return x + y;
    }
    """
    r = analyze(source)
    assert not sem_errors(r), "Logical operators should accept string pointer operands"

def test_relational_comparison_with_string_reports_type_error():
    r = analyze('int main() { int x = 5 < "hello"; return x; }')
    errs = sem_errors(r)

    assert any(
        e.code == "SEM011"
        for e in errs
    ), "Comparing an integer with a string pointer should report a semantic error"


def test_equality_comparison_between_string_pointers_is_valid():
    r = analyze('int main() { int x = "hello" == "world"; return x; }')
    assert not sem_errors(r)


def test_ordering_comparison_between_string_pointers_reports_type_error():
    r = analyze('int main() { int x = "hello" < "world"; return x; }')
    errs = sem_errors(r)

    assert any(
        e.code == "SEM011"
        for e in errs
    ), "Ordering comparison between string pointers should report a semantic error"


def test_inequality_comparison_between_string_pointers_is_valid():
    r = analyze('int main() { int x = "hello" != "world"; return x; }')
    assert not sem_errors(r)



def test_return_type_mismatch_reports_semantic_error():
    r = analyze('float calculate() { return "hello"; }\nint main() { return 0; }')
    errs = sem_errors(r)

    assert any(
        e.code == "SEM007"
        for e in errs
    ), "Returning a string from a float function should report a type mismatch"



def test_function_argument_type_mismatch_reports_error():
    r = analyze('int square(int x) { return x * x; }\nint main() { return square("hello"); }')
    errs = sem_errors(r)

    assert any(
        e.code == "SEM003"
        for e in errs
    ), "Passing a string to a function expecting an int should report a type error"



def test_function_call_allows_int_argument_for_float_parameter():
    r = analyze(
        "float double_value(float x) { return x * 2; }\n"
        "int main() { return double_value(5); }"
    )
    errs = sem_errors(r)

    assert not any(
        e.code == "SEM003"
        for e in errs
    ), "An int argument should be compatible with a float parameter"



def test_calling_variable_as_function_reports_error():
    r = analyze("int main() { int value = 5; value(); return 0; }")
    errs = sem_errors(r)

    assert any(
        e.code == "SEM009"
        for e in errs
    ), "Calling a variable as a function should report a semantic error"



def test_nested_function_call_argument_types_are_checked():
    r = analyze(
        "int get_value() { return 5; }\n"
        "int square(int x) { return x * x; }\n"
        "int main() { return square(get_value()); }"
    )
    errs = sem_errors(r)

    assert not any(
        e.code in ("SEM003", "SEM010")
        for e in errs
    ), "A nested function call with a compatible argument should not report a type or count error"
