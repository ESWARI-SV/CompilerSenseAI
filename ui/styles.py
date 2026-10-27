"""ui/styles.py — CompilerSense AI design system (dense enterprise dark)."""
from __future__ import annotations

import html
from importlib import import_module

st = import_module("streamlit")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--bg:#10151c;--rail:#0d1218;--panel:#141b24;--line:#232c38;--txt:#d7dde6;--mut:#8794a6;
--blue:#2f81f7;--ok:#7de29a;--warn:#e0b04a;--err:#ff6b6b;}
html,body,[class*="css"],[data-testid="stAppViewContainer"]{font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:14px}
code,pre,kbd,[data-testid="stCode"] *{font-family:'IBM Plex Mono',ui-monospace,monospace!important}
.block-container{padding:4rem 2rem 3rem;max-width:1400px}
[data-testid="stSidebar"]{background:var(--rail);border-right:1px solid var(--line)}
[data-testid="stSidebar"] h3{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);font-weight:500}
.stTabs [data-baseweb="tab-list"]{gap:24px;border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab"]{height:40px;padding:0;color:var(--mut);font-weight:500}
.stTabs [aria-selected="true"]{color:#fff}
.stTabs [data-baseweb="tab-highlight"]{background:#4da3ff}
[data-testid="stExpander"]{background:var(--panel);border:1px solid var(--line);border-radius:6px}
[data-testid="stExpander"] summary{font-weight:600;color:#fff}
[data-testid="stAlert"]{border-radius:4px;border:0}
[data-testid="stMetricValue"]{font-family:'IBM Plex Mono',monospace;font-weight:500;color:#fff}
[data-testid="stMetricLabel"]{color:var(--mut);text-transform:uppercase;font-size:11px;letter-spacing:.05em}
.stButton>button{border-radius:4px;border:1px solid #2d3948;background:transparent;color:var(--txt);padding:.5rem 1rem}
.stButton>button:hover{border-color:var(--blue);color:#fff}
.stButton>button[kind="primary"]{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600}
.cs-brand{font-weight:600;font-size:17px;color:#fff;letter-spacing:-.01em}.cs-brand i{font-style:normal;color:#4da3ff}
.cs-sub{color:var(--mut);font-size:12px;line-height:1.5;margin-top:4px}
.cs-head h1{font-size:24px;font-weight:600;color:#fff;margin:18px 0 4px;padding:0;letter-spacing:-.02em}
.cs-chips{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 14px}
.cs-chip{font:12px 'IBM Plex Mono',monospace;padding:3px 10px;border-radius:3px;background:var(--panel);border:1px solid var(--line);color:var(--txt)}
.cs-chip.ok{background:#12301f;border-color:#1d4a2e;color:var(--ok)}
.cs-chip.warn{background:#3a2e12;border-color:#5a4618;color:var(--warn)}
.cs-chip.err{background:#3a1a1f;border-color:#5a2a31;color:var(--err)}
.cs-head a{display:none}
.stApp{background:#0b0f14}
[data-testid="stHeader"]{background:transparent}
.stTabs [data-baseweb="tab-list"]{gap:28px}
.stTabs [data-baseweb="tab"]{height:44px;font-size:14px}
.stTabs [aria-selected="true"]{color:#fff!important;font-weight:600}
.stTabs [data-baseweb="tab-highlight"]{background:#2f81f7;height:2px}
iframe[title*="streamlit_ace"]{border:1px solid var(--line);border-radius:6px}
[data-testid="stAlert"]{border:1px solid var(--line);border-radius:6px;padding:.6rem .9rem}
[data-testid="stExpander"]{background:var(--panel)}
[data-testid="stMarkdownContainer"] *,button,label,summary,[data-baseweb="tab"]{font-family:'IBM Plex Sans',system-ui,sans-serif}
.cs-head h1{font-size:22px}
.cs-head a{display:none}
.cs-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:8px 0 18px}
.cs-kpi{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--blue);border-radius:6px;padding:12px 14px}
.cs-kpi.ok{border-top-color:var(--ok)}.cs-kpi.warn{border-top-color:var(--warn)}.cs-kpi.err{border-top-color:var(--err)}
.cs-kl{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}
.cs-kv{font:500 26px 'IBM Plex Mono',monospace;color:#fff;margin-top:4px}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def brand() -> None:
    st.markdown(
        '<div class="cs-brand">CompilerSense <i>AI</i></div>'
        '<div class="cs-sub">AI-Assisted Syntax Error Detection and Correction</div>',
        unsafe_allow_html=True,
    )


def page_header(title: str) -> None:
    st.markdown(f'<div class="cs-head"><h1>{html.escape(title)}</h1></div>', unsafe_allow_html=True)


def chip(text: str, tone: str = "") -> str:
    return f'<span class="cs-chip {tone}">{html.escape(str(text))}</span>'


def chips(items: list[tuple[str, str]]) -> None:
    st.markdown('<div class="cs-chips">' + "".join(chip(t, k) for t, k in items) + "</div>", unsafe_allow_html=True)

def kpis(items: list[tuple[str, str, str]]) -> None:
    cards = "".join(
        f'<div class="cs-kpi {tone}"><div class="cs-kl">{html.escape(label)}</div>'
        f'<div class="cs-kv">{html.escape(value)}</div></div>'
        for label, value, tone in items
    )
    st.markdown(f'<div class="cs-kpis">{cards}</div>', unsafe_allow_html=True)