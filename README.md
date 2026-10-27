# CompilerSense AI

**AI-Assisted Syntax Error Detection and Correction Using Lexical, Syntactic and Semantic Analysis**

A complete, polished Compiler Design project demonstrating a hybrid compiler-assistance system for a defined C subset. Combines real compiler front-end construction (PLY Lex/Yacc) with deterministic error-repair rules, optional AI-assisted suggestions, and an interactive Streamlit UI.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Problem Statement](#problem-statement)
3. [Objectives](#objectives)
4. [Proposed Contributions](#proposed-contributions)
5. [Architecture](#architecture)
6. [Data Flow](#data-flow)
7. [Supported C Grammar and Limitations](#supported-c-grammar)
8. [Module Descriptions](#module-descriptions)
9. [Installation](#installation)
10. [Environment Configuration](#environment-configuration)
11. [Running the Application](#running-the-application)
12. [Running Tests](#running-tests)
13. [Running the Evaluation Script](#running-the-evaluation-script)
14. [Example Programs](#example-programs)
15. [Expected Behaviour](#expected-behaviour)
16. [AI Failure and Fallback](#ai-failure-and-fallback)
17. [Security Considerations](#security-considerations)
18. [Known Limitations](#known-limitations)
19. [Evaluation Results](#evaluation-results)
20. [Future Improvements](#future-improvements)

---

## Project Overview

CompilerSense AI is a 30-mark undergraduate Compiler Design project that:

- Implements a real lexer (PLY Lex) and parser (PLY Yacc) for a C subset
- Builds a custom AST with visitor pattern
- Implements scoped symbol table and semantic analysis
- Groups related diagnostics by likely root cause
- Proposes deterministic repair candidates (missing semicolons, braces, keyword typos)
- Optionally calls an LLM API for contextual repair suggestions
- Verifies every proposed repair by re-running the full compiler pipeline
- Displays all results in a polished 5-tab Streamlit interface

---

## Problem Statement

Compiler error messages are often cryptic, terse, and cascading — one mistake can produce dozens of misleading follow-up errors. Students and developers spend significant time interpreting these messages and locating the actual root cause. Existing tools (language servers, linters) rely on full C standards and are impractical to study as teaching artifacts.

---

## Objectives

1. Implement a real compiler front-end for a teachable C subset
2. Detect and classify lexical, syntactic, and semantic errors with source locations
3. Group cascading errors and identify likely root causes
4. Generate and verify repair candidates using deterministic rules and optional AI
5. Provide an interactive, explainable academic demonstration tool

---

## Proposed Contributions

| Contribution | Description |
|---|---|
| Root-cause-aware diagnostics | Heuristic cascade grouping with uncertainty labels |
| Evidence-guided hybrid repair | Deterministic rules + optional LLM, ranked by compiler feedback |
| Explainable verified corrections | Patch preview, diff, re-analysis result, remaining errors |
| Measurable comparison | Rules-only vs. hybrid evaluated on a labelled corpus |

---

## Architecture

```
CompilerSenseAI/
├── app.py                  # Streamlit entry point
├── compiler/
│   ├── models.py           # Shared dataclasses (Token, Diagnostic, AnalysisResult, ...)
│   ├── lexer.py            # PLY Lex tokenizer
│   ├── parser.py           # PLY Yacc parser
│   ├── ast_nodes.py        # Custom AST node classes + visitor + printer
│   ├── symbol_table.py     # Scoped symbol table
│   ├── semantic.py         # Semantic analyzer (visitor)
│   ├── diagnostics.py      # Root-cause grouping pipeline
│   └── orchestrator.py     # Coordinates all compiler stages
├── repair/
│   ├── rules.py            # Deterministic repair rules
│   ├── patcher.py          # Safe patch application + diff
│   ├── ranking.py          # Multi-criteria candidate ranking
│   ├── verifier.py         # Re-analysis verification loop
│   ├── ai_provider.py      # Optional LLM abstraction
│   └── prompts.py          # Prompt templates
├── storage/
│   ├── schema.sql          # SQLite schema
│   └── history.py          # Session persistence
├── evaluation/
│   ├── test_cases.json     # 40 labelled test programs
│   ├── run_tests.py        # Evaluation runner
│   └── metrics.py          # Precision/Recall/F1/repair metrics
└── tests/
    ├── test_lexer.py
    ├── test_parser.py
    ├── test_semantic.py
    ├── test_rules.py
    ├── test_patcher.py
    ├── test_verifier.py
    └── test_integration.py
```

---

## Data Flow

```
Source Code
    │
    ▼
┌─────────────┐     Tokens + Diagnostics
│  CSubsetLexer│ ──────────────────────────────►┐
└─────────────┘                                 │
                                                ▼
┌─────────────┐     AST + Diagnostics    ┌─────────────────────┐
│ CSubsetParser│ ─────────────────────►  │   Orchestrator      │
└─────────────┘                          │ (coordinator)        │
                                         └──────────┬──────────┘
┌──────────────────┐  Semantic Diags              │
│ SemanticAnalyzer │ ─────────────────────────────►│
└──────────────────┘                              │
                                                  ▼
┌────────────────────┐     Grouped Diags   ┌──────────────────┐
│ DiagnosticPipeline │ ───────────────────►│  AnalysisResult  │
└────────────────────┘                     └────────┬─────────┘
                                                    │
                    ┌───────────────────────────────┘
                    ▼
┌──────────────────────────┐
│  Deterministic Rules      │ ──── RepairCandidates
└──────────────────────────┘
┌──────────────────────────┐
│  AI Provider (optional)  │ ──── RepairCandidates
└──────────────────────────┘
                    │
                    ▼
┌──────────────────────────┐
│  Patcher + Verifier       │ Apply patch → Rerun compiler
└──────────────────────────┘
                    │
                    ▼
┌──────────────────────────┐
│  Ranking                  │ Score by verification result
└──────────────────────────┘
                    │
                    ▼
         Streamlit UI (5 tabs)
```

---

## Supported C Grammar

```
program         → declaration+
declaration     → var_decl | fun_decl
var_decl        → type_spec ID ('=' expr)? ';'
fun_decl        → type_spec ID '(' params ')' compound_stmt
type_spec       → 'int' | 'float' | 'char' | 'void'
params          → 'void' | param (',' param)* | ε
param           → type_spec ID
compound_stmt   → '{' statement* '}'
statement       → expr_stmt | compound_stmt | if_stmt | while_stmt
                | for_stmt | return_stmt | var_decl
expr_stmt       → expr ';' | ';'
if_stmt         → 'if' '(' expr ')' statement ('else' statement)?
while_stmt      → 'while' '(' expr ')' statement
for_stmt        → 'for' '(' expr_stmt expr_stmt expr? ')' statement
return_stmt     → 'return' expr? ';'
expr            → ID '=' expr | simple_expr
simple_expr     → add_expr (relop add_expr)? (('&&'|'||') add_expr)*
relop           → '<' | '<=' | '>' | '>=' | '==' | '!='
add_expr        → term (('+' | '-') term)*
term            → factor (('*' | '/' | '%') factor)*
factor          → '(' expr ')' | ID ('(' args ')')? | INT_LITERAL
                | FLOAT_LITERAL | CHAR_LITERAL | STRING_LITERAL
                | '-' factor | '!' factor
args            → expr (',' expr)* | ε
```

### Type Rules

| Assignment | Allowed |
|---|---|
| int ← int | ✅ |
| float ← int | ✅ (widening) |
| float ← float | ✅ |
| char ← char | ✅ |
| char ← int | ✅ (C convention) |
| int ← float | ❌ (narrowing error) |
| any ← string | ❌ |

### Explicit Exclusions

- Pointers (`*`, `&`, `->`), arrays, structs, unions
- `#include`, `#define`, macros, preprocessor
- `switch`/`case`, `break`, `continue`, `goto`, `do-while`
- Variadic functions, implicit function declarations
- Full C89/C99/C11 standard compliance

---

## Module Descriptions

| Module | Responsibility |
|---|---|
| `compiler/models.py` | Shared dataclasses: Token, Diagnostic, AnalysisResult, SourceEdit, RepairCandidate |
| `compiler/lexer.py` | PLY Lex tokenizer with line/column/offset tracking and diagnostic emission |
| `compiler/parser.py` | PLY Yacc parser building a real AST with error recovery |
| `compiler/ast_nodes.py` | Custom AST node classes with visitor pattern and pretty-printer |
| `compiler/symbol_table.py` | Hierarchical scope stack with define/lookup |
| `compiler/semantic.py` | Type checking, undeclared identifiers, duplicate declarations, void misuse |
| `compiler/diagnostics.py` | Root-cause grouping with cascade detection and uncertainty labels |
| `compiler/orchestrator.py` | Coordinates all compiler stages; returns AnalysisResult |
| `repair/rules.py` | Deterministic rules: semicolon, brace, paren, keyword typos |
| `repair/patcher.py` | Offset-validated patch application with conflict detection |
| `repair/ranking.py` | Multi-criteria ranking: verification × minimality × method |
| `repair/verifier.py` | Re-runs compiler on patched source; updates VerificationStatus |
| `repair/ai_provider.py` | OpenAI abstraction with schema validation and fallback |
| `repair/prompts.py` | System prompt and context-builder for AI requests |
| `storage/history.py` | SQLite persistence for analysis sessions |
| `evaluation/run_tests.py` | Repeatable evaluation on 40-case labelled corpus |
| `evaluation/metrics.py` | Precision, recall, F1, repair coverage, regression rate |
| `app.py` | 5-tab Streamlit UI with session state management |

---

## Installation

### Prerequisites

- Python 3.11+ (tested on 3.13)
- pip

### Steps

```powershell
# 1. Navigate to project directory
cd CompilerSenseAI

# 2. (Recommended) Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# or: source venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Environment Configuration

Copy `.env.example` to `.env` and edit:

```
AI_PROVIDER=none          # Set to "openai" to enable AI suggestions
OPENAI_API_KEY=sk-...    # Your OpenAI API key (required if AI_PROVIDER=openai)
OPENAI_MODEL=gpt-4o-mini  # Model to use
AI_TIMEOUT_SECONDS=30     # Timeout for AI requests
```

**Never commit `.env` to version control.** The `.gitignore` excludes it.

The application works fully without an AI key — only deterministic suggestions are shown.

---

## Running the Application

```powershell
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Running Tests

```powershell
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=compiler --cov=repair --cov-report=term-missing
```

Expected result: **76 passed**

---

## Running the Evaluation Script

```powershell
# Full run with JSON output
python evaluation/run_tests.py --output evaluation/results_latest.json

# Quick summary only
python evaluation/run_tests.py --quick
```

---

## Example Programs

### Valid (Demo A)
```c
int main() {
    int x = 10;
    int y = x + 5;
    return y;
}
```

### Missing Semicolon (Demo B)
```c
int main() {
    int x = 10    // ← missing semicolon
    return x;
}
```

### Undeclared Identifier (Demo C)
```c
int main() {
    int x = 10;
    return y;  // y not declared
}
```

### Type Mismatch (Demo D)
```c
int main() {
    int x = "hello";  // string → int: error
    return x;
}
```

---

## Expected Behaviour

| Program | Expected Result |
|---|---|
| Valid code | No errors; AST shown; symbol table populated |
| Missing semicolon | SYN001 at the error location; semicolon repair candidate offered |
| Undeclared identifier | SEM001 with location; no deterministic fix (correct behaviour) |
| Type mismatch | SEM003 with both types shown in message |
| Keyword typo (`retrun`) | SYN001 + RULE004 replacement candidate |
| Unmatched brace | SYN001; RULE002 candidate if exactly 1 unmatched |

---

## AI Failure and Fallback

If the AI is unavailable (no key, network error, timeout, rate limit, invalid response):

1. `ai_provider.py` logs the failure at WARNING level
2. Returns an empty list (no AI candidates)
3. The UI shows: "⚠️ AI provider not configured — Deterministic suggestions only"
4. Deterministic candidates are shown normally
5. No exception propagates to the user

---

## Security Considerations

- API keys loaded from environment variables only; never logged or displayed
- AI is never given file-system or code-execution permissions
- Patch application validates source offsets and original text before any edit
- Source code is never executed — only statically analysed
- SQLite history is local; no data leaves the machine unless AI is configured
- `AI_TIMEOUT_SECONDS` caps AI request duration

---

## Known Limitations

1. **No full C compliance** — pointers, arrays, structs, macros, preprocessor not supported
2. **Parser error recovery** is basic — a syntax error may prevent semantic analysis of later code
3. **Root-cause grouping** is heuristic (line-proximity based) and may misattribute cascades
4. **AI suggestions** are not verified against source offsets before validation (line-based matching used)
5. **String literals** are accepted in expressions but type inference is simplified (`char*`)
6. **No implicit int promotion** across all arithmetic contexts
7. **`do-while`, `switch`, `break`, `continue`** not supported

---

## Evaluation Results

Results from the 40-case labelled corpus (deterministic-only configuration):

| Metric | Value |
|---|---|
| Total tests | 40 |
| Passed | 40 (100%) |
| Precision | 1.000 |
| Recall | 1.000 |
| F1 | 1.000 |
| Repair coverage | 100% |
| Verified rate | 100% |
| Regression rate | 0% |
| Avg latency | 23.4ms |

Full results: `evaluation/results_latest.json`

---

## Future Improvements

1. **Extended grammar**: arrays, basic structs, `switch`/`case`, `break`/`continue`
2. **Better error recovery**: synchronisation on type keywords and block boundaries
3. **Runtime verification**: optional sandbox execution (isolated, opt-in)
4. **Type inference improvements**: full C integer promotion rules
5. **Multiple AI providers**: Anthropic, Google Gemini fallback chain
6. **IDE integration**: Language Server Protocol adapter
7. **Pointer support**: teach a subset of pointer semantics
8. **Broader evaluation corpus**: 100+ programs across more error categories
9. **Calibrated confidence scores**: empirically calibrated from corpus data
10. **Web deployment**: Docker container with Streamlit Cloud or similar
