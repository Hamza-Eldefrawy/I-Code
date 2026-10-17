import re
import streamlit as st

from src.orchestrator import Orchestrator
from src.code_runner import run_code, format_result

st.set_page_config(page_title="I-Code", layout="wide")

LANGUAGES = ["Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust"]
FRAMEWORKS = ["None", "Flask", "FastAPI", "Django", "PyTorch", "TensorFlow", "React", "Spring"]
BLOCK = re.compile(r"```([\w+#-]*)\n(.*?)```", re.DOTALL)

# ---------- state (survives Streamlit reruns) ----------
if "orch" not in st.session_state:
    st.session_state.orch = Orchestrator()
    st.session_state.history = []      # what the screen shows
    st.session_state.run_panel = None  # {"code", "lang", "result"} or None
orch = st.session_state.orch


# ---------- callbacks (run BEFORE the script reruns, so the layout sees the new state) ----------
def open_panel(code: str, lang: str):
    st.session_state.run_panel = {"code": code, "lang": lang, "result": None}


def close_panel():
    st.session_state.run_panel = None


def clear_chat():
    st.session_state.history = []
    st.session_state.run_panel = None
    orch.memory.clear()
    orch.awaiting_solution = False
    orch.pending_request = None


# ---------- helpers ----------
def split_message(text: str):
    """Split a message into ('text', str, None) and ('code', code, lang) parts."""
    parts, pos = [], 0
    for m in BLOCK.finditer(text):
        if m.start() > pos:
            parts.append(("text", text[pos:m.start()], None))
        parts.append(("code", m.group(2).strip("\n"), m.group(1) or "python"))
        pos = m.end()
    if pos < len(text):
        parts.append(("text", text[pos:], None))
    return parts


def render_message(msg: dict, idx: int):
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
            return
        for j, (kind, content, lang) in enumerate(split_message(msg["content"])):
            if kind == "text":
                if content.strip():
                    st.markdown(content)
            else:
                st.code(content, language=lang)
                st.button("▶ Run", key=f"run_{idx}_{j}", on_click=open_panel, args=(content, lang))


# ---------- sidebar ----------
with st.sidebar:
    st.title("I-Code")
    language = st.selectbox("Language", LANGUAGES)
    framework = st.selectbox("Framework", FRAMEWORKS)
    st.button("Clear conversation", on_click=clear_chat)

orch.memory.set_preferences(language, None if framework == "None" else framework)

# ---------- layout: chat on the left, run panel on the right when open ----------
panel = st.session_state.run_panel
if panel:
    chat_col, side_col = st.columns([3, 2], gap="large")
else:
    chat_col, side_col = st.container(), None

if orch.awaiting_solution:
    st.info("I'm waiting for the correct solution. Paste it in a code block, or ask something else.")

# chat_input must be at the top level so it stays pinned to the bottom of the page
prompt = st.chat_input("Ask I-Code to write or explain code...")

with chat_col:
    for i, msg in enumerate(st.session_state.history):
        render_message(msg, i)

    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        render_message(st.session_state.history[-1], len(st.session_state.history) - 1)
        with st.chat_message("assistant"):
            with st.spinner("I-Code is thinking..."):
                try:
                    answer = orch.handle(prompt)
                except Exception as e:
                    answer = f"Something went wrong: {e}"
        st.session_state.history.append({"role": "assistant", "content": answer})
        st.rerun()      # redraw everything through the normal path

if side_col is not None:
    with side_col:
        st.subheader("Run code")
        st.button("✕ Close", on_click=close_panel)
        st.code(panel["code"], language=panel["lang"])
        if panel["result"] is None:
            with st.spinner("Running..."):
                panel["result"] = run_code(panel["code"])
        st.markdown(format_result(panel["result"]))
        st.caption("This code runs on your machine.")