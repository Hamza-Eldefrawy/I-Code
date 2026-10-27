import os
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

# ---------------- CONFIG ----------------
# Local development default. Set ICODE_API_URL in your deployment environment.
API_URL = os.getenv("ICODE_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = (5, 60)  # connect timeout, response timeout

BG = "#050806"
PANEL = "#0b140e"
BORDER = "#193020"
TEXT = "#e2ece5"
MUTED = "#789280"
GREEN = "#2ea043"
BRIGHT_GREEN = "#4ade80"

LOGO_SVG = """
<svg viewBox="0 0 120 120" width="{size}" height="{size}"
     role="img" aria-label="I-Code logo"
     style="color:#2ea043;flex:none;">
  <path d="M58 27 C56 14 68 5 80 6 C82 18 71 27 58 27 Z" fill="currentColor"/>
  <path d="M59 35 C50 35 43 29 35 29 C20 29 12 42 12 59 C12 80 28 103 42 103 C48 103 52 99 59 99 C66 99 70 103 76 103 C89 103 104 82 104 59 C104 42 96 29 81 29 C73 29 67 35 59 35 Z" fill="currentColor"/>
  <circle cx="101" cy="57" r="19" fill="#050806"/>
  <path d="M22 98 C50 116 98 96 76 74 C52 52 6 58 24 28 C38 8 96 14 106 42" fill="none" stroke="#050806" stroke-width="14" stroke-linecap="round"/>
  <path d="M22 98 C50 116 98 96 76 74 C52 52 6 58 24 28 C38 8 96 14 106 42" fill="none" stroke="currentColor" stroke-width="8.5" stroke-linecap="round"/>
  <ellipse cx="104" cy="46" rx="9" ry="6.5" transform="rotate(120 104 46)" fill="currentColor"/>
  <circle cx="103" cy="49" r="1.6" fill="#050806"/>
  <path d="M99 53 L94 58 M94 58 L89 57 M94 58 L93 63" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/>
</svg>
"""

st.set_page_config(
    page_title="I-Code",
    page_icon="🐍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------- THEME ----------------
st.markdown(
    f"""
    <style>
    :root {{
        --bg: {BG}; --panel: {PANEL}; --border: {BORDER};
        --text: {TEXT}; --muted: {MUTED}; --green: {GREEN};
        --bright-green: {BRIGHT_GREEN};
    }}
    .stApp {{ background: var(--bg); color: var(--text); }}
    [data-testid="stSidebar"] {{
        background: var(--panel); border-right: 1px solid var(--border);
    }}
    [data-testid="stHeader"] {{ background: transparent; }}
    .stButton > button {{
        background: var(--panel); color: var(--text);
        border: 1px solid var(--border); border-radius: 8px;
        transition: border-color .2s, color .2s;
    }}
    .stButton > button:hover {{
        border-color: var(--green); color: var(--bright-green);
    }}
    .stTextInput input, .stTextArea textarea,
    [data-testid="stChatInput"] textarea {{
        background: var(--panel) !important; color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }}
    [data-testid="stChatMessage"] {{
        background: var(--panel); border: 1px solid var(--border);
        border-radius: 12px; padding: 12px; margin-bottom: 10px;
    }}
    pre, code {{ background: #030604 !important; border-color: var(--border) !important; }}
    .brand-box {{
        display:flex; align-items:center; gap:12px;
        font-family:ui-monospace,"Cascadia Code",Consolas,monospace;
        font-size:22px; font-weight:700; margin-bottom:16px;
    }}
    .empty-hero {{
        text-align:center; padding:5vh 0 2vh;
        font-family:ui-monospace,"Cascadia Code",Consolas,monospace;
    }}
    .muted {{ color: var(--muted); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- SESSION STATE ----------------
DEFAULT_STATE = {
    "sid": None,
    "online": False,
    "msgs": [],
    "csv_info": None,
    "sql_cards": [],
    "run_result": None,
    "voice_sql_q": "",
    "last_error": None,
}
for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value.copy() if isinstance(value, (list, dict)) else value


# ---------------- API HELPERS ----------------
class APIError(RuntimeError):
    """Readable API/network error for the UI."""


def _decode_response(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text[:500] or "The API returned an empty response."}

    if not isinstance(payload, dict):
        payload = {"data": payload}
    return payload


def api_call(
    method: str,
    path: str,
    json_data: dict | None = None,
    files: dict | None = None,
    *,
    retry_session: bool = True,
) -> dict[str, Any]:
    """Call the API, attach the current session, and show useful errors."""
    headers = {}
    if st.session_state.sid:
        headers["x-session-id"] = st.session_state.sid

    try:
        response = requests.request(
            method=method,
            url=f"{API_URL}{path}",
            headers=headers,
            json=json_data,
            files=files,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        st.session_state.online = False
        raise APIError("The API request timed out. Try again in a moment.") from exc
    except requests.RequestException as exc:
        st.session_state.online = False
        raise APIError(
            f"Cannot reach the API at {API_URL}. Check that the backend is running "
            "and that ICODE_API_URL is configured correctly."
        ) from exc

    st.session_state.online = True
    payload = _decode_response(response)
    detail = payload.get("detail", payload.get("message", response.text[:300]))

    # Recreate an expired session once, then retry the original request.
    if (
        response.status_code in (400, 401, 404)
        and retry_session
        and "unknown session" in str(detail).lower()
        and path != "/sessions"
    ):
        start_session()
        return api_call(
            method, path, json_data=json_data, files=files, retry_session=False
        )

    if not response.ok:
        raise APIError(f"API error ({response.status_code}): {detail}")

    return payload


def start_session() -> None:
    try:
        result = api_call("POST", "/sessions", retry_session=False)
        st.session_state.sid = result.get("session_id")
        if not st.session_state.sid:
            raise APIError("The API created a session but did not return session_id.")
    except Exception as exc:
        st.session_state.sid = None
        st.session_state.last_error = str(exc)


def ensure_session() -> bool:
    if st.session_state.sid:
        return True
    start_session()
    return bool(st.session_state.sid)


def extract_code_blocks(markdown_text: str) -> list[str]:
    """Extract fenced code blocks without treating prose as executable code."""
    return [
        match.strip()
        for match in re.findall(r"```([\w+#.-]*)\n([\s\S]*?)```", markdown_text)
        if False
    ] if False else [
        code.strip()
        for _, code in re.findall(r"```([\w+#.-]*)\n([\s\S]*?)```", markdown_text)
        if code.strip()
    ]


def send_message(text: str) -> None:
    text = text.strip()
    if not text:
        return

    st.session_state.msgs.append({"role": "user", "text": text})
    try:
        if not ensure_session():
            raise APIError(st.session_state.last_error or "Could not create an API session.")

        intent_result = api_call("POST", "/analyze", json_data={"text": text})
        intent = intent_result.get("intent")

        if intent == "explain":
            answer = api_call("POST", "/explain", json_data={"text": text}).get("answer", "")
            st.session_state.msgs.append({"role": "assistant", "text": answer or "No explanation was returned."})
        elif intent == "generate":
            result = api_call("POST", "/generate", json_data={"text": text})
            st.session_state.msgs.append({
                "role": "assistant",
                "text": result.get("answer", "No answer was returned."),
                "teach": {"request": text, "done": False} if result.get("not_found") else None,
            })
        else:
            st.session_state.msgs.append({
                "role": "assistant",
                "text": "Would you like me to **explain existing code** or **write new code**?",
            })
    except Exception as exc:
        st.session_state.msgs.append({
            "role": "assistant",
            "text": f"**Request failed:** {exc}",
        })


def reset_session() -> None:
    old_sid = st.session_state.sid
    if old_sid:
        try:
            api_call("DELETE", f"/sessions/{old_sid}", retry_session=False)
        except Exception:
            pass

    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value.copy() if isinstance(value, (list, dict)) else value
    start_session()


# Create a session lazily so the page can still render if the backend is offline.
if st.session_state.sid is None:
    start_session()


# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(
        f'<div class="brand-box">{LOGO_SVG.format(size=44)}<span>I-Code</span></div>',
        unsafe_allow_html=True,
    )
    mode = st.radio("Navigation", ["Chat", "Data (SQL)"], label_visibility="collapsed")
    st.divider()

    if st.button("＋ New session", use_container_width=True):
        reset_session()
        st.rerun()

    status_color = BRIGHT_GREEN if st.session_state.online else "#ff7b7b"
    status_label = "● Connected" if st.session_state.online else "● Offline"
    st.markdown(
        f'<p style="color:{status_color};font-size:14px;margin-top:12px">{status_label}</p>',
        unsafe_allow_html=True,
    )
    st.caption(f"Backend: `{API_URL}`")

    st.divider()
    audio_value = st.audio_input("Voice input")
    if audio_value is not None and st.button("Transcribe voice", use_container_width=True):
        try:
            result = api_call(
                "POST",
                "/voice/transcribe",
                files={"file": ("voice.wav", audio_value.getvalue(), "audio/wav")},
            )
            transcript = result.get("transcript", "").strip()
            if not transcript:
                st.warning("I couldn't detect speech. Try recording again.")
            elif mode == "Chat":
                send_message(transcript)
                st.rerun()
            else:
                st.session_state.voice_sql_q = transcript
                st.success("Transcript ready. You can edit it in the SQL question box.")
                st.rerun()
        except Exception as exc:
            st.error(str(exc))

# ---------------- CHAT MODE ----------------
if mode == "Chat":
    has_result = st.session_state.run_result is not None
    col_main, col_run = st.columns([2, 1] if has_result else [1, 0.001])

    with col_main:
        if not st.session_state.msgs:
            st.markdown(
                f'<div class="empty-hero">{LOGO_SVG.format(size=140)}'
                '<h1>I-Code</h1>'
                '<p class="muted">Write, explain, and run code. Ask questions about your CSV.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns(3)
            if c1.button("Write a function", use_container_width=True):
                send_message("Write a function that checks if any two numbers in a list are closer than a threshold")
                st.rerun()
            if c2.button("Explain some code", use_container_width=True):
                send_message("Explain this code:\n```python\ndef f(n):\n    return 1 if n < 2 else n * f(n - 1)\n```")
                st.rerun()
            if c3.button("Try the learning loop", use_container_width=True):
                send_message("Build a Flask API with one endpoint")
                st.rerun()

        for idx, message in enumerate(st.session_state.msgs):
            with st.chat_message(message["role"]):
                st.markdown(message["text"])

                if message["role"] != "assistant":
                    continue

                blocks = extract_code_blocks(message["text"])
                for block_idx, code_text in enumerate(blocks):
                    if st.button("▶ Run code", key=f"run_{idx}_{block_idx}"):
                        # Running arbitrary code is dangerous. The backend must sandbox it.
                        try:
                            result = api_call("POST", "/run", json_data={"text": code_text})
                            st.session_state.run_result = {"code": code_text, "res": result}
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                teaching = message.get("teach")
                if teaching and not teaching.get("done"):
                    st.info("I couldn't find this solution in my knowledge base. You can provide a correct solution to teach I-Code.")
                    solution = st.text_area("Correct solution", key=f"teach_txt_{idx}")
                    if st.button("Save solution", key=f"teach_btn_{idx}"):
                        if not solution.strip():
                            st.warning("Paste a solution first.")
                        else:
                            try:
                                api_call(
                                    "POST",
                                    "/feedback",
                                    json_data={"request": teaching["request"], "solution": solution.strip()},
                                )
                                teaching["done"] = True
                                st.session_state.msgs.append({
                                    "role": "assistant",
                                    "text": "Solution saved. Ask the question again to try it.",
                                })
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

        prompt = st.chat_input("Ask I-Code to write or explain code…")
        if prompt:
            send_message(prompt)
            st.rerun()

    if has_result:
        with col_run:
            st.subheader("Code runner")
            st.warning("Only run code in a properly sandboxed backend.")
            if st.button("Close runner"):
                st.session_state.run_result = None
                st.rerun()

            st.code(st.session_state.run_result["code"], language="python")
            result = st.session_state.run_result["res"]
            success = result.get("returncode") == 0 and not result.get("timed_out")
            status = (
                "Timed out" if result.get("timed_out")
                else "Success" if success
                else f"Failed (exit {result.get('returncode')})"
            )
            st.markdown(f"**{status}** · `{result.get('duration', '?')} s`")
            if result.get("stdout", "").strip():
                st.code(result["stdout"], language="text")
            if result.get("stderr", "").strip():
                st.error(result["stderr"])

# ---------------- DATA / SQL MODE ----------------
else:
    st.subheader("Data (SQL)")
    st.caption("Upload a CSV, ask a question, inspect the generated SQL, and rerun it after editing.")

    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded_file is not None:
        current_info = st.session_state.csv_info or {}
        if current_info.get("_filename") != uploaded_file.name:
            try:
                result = api_call(
                    "POST",
                    "/sql/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                )
                result["_filename"] = uploaded_file.name
                st.session_state.csv_info = result
                st.session_state.sql_cards = []
                st.success(f"Loaded {uploaded_file.name}")
            except Exception as exc:
                st.error(str(exc))

    if st.session_state.csv_info:
        info = st.session_state.csv_info
        metric1, metric2 = st.columns(2)
        metric1.metric("Rows", info.get("rows", "—"))
        metric2.metric("Columns", len(info.get("columns", [])))
        st.markdown(f"**Table:** `{info.get('table', 'unknown')}`")
        st.caption("Columns: " + ", ".join(map(str, info.get("columns", []))))

        sql_question = st.text_input(
            "Ask a question about your data",
            key="sql_question",
            value=st.session_state.voice_sql_q,
            placeholder="e.g. Which category has the highest average value?",
        )
        if st.button("Generate SQL", type="primary", use_container_width=True):
            if not sql_question.strip():
                st.warning("Enter a question first.")
            else:
                card = {"q": sql_question.strip(), "sql": "", "res": None, "err": None}
                try:
                    generated = api_call(
                        "POST", "/sql/query", json_data={"question": sql_question.strip()}
                    )
                    card["sql"] = generated.get("sql", "")
                    if not card["sql"]:
                        raise APIError("The API did not return a SQL query.")
                except Exception as exc:
                    card["err"] = str(exc)
                st.session_state.sql_cards.insert(0, card)
                st.session_state.voice_sql_q = ""
                st.rerun()
    else:
        st.info("Upload a CSV file to begin asking questions about your data.")

    for card_idx, card in enumerate(st.session_state.sql_cards):
        with st.container(border=True):
            st.markdown(f"**{card['q']}**")
            edited_sql = st.text_area(
                "Generated SQL (review before running)",
                value=card["sql"],
                key=f"sql_text_{card_idx}",
                height=110,
            )
            if st.button("▶ Run SQL", key=f"sql_run_{card_idx}"):
                card["sql"] = edited_sql
                try:
                    # The backend must validate SQL and restrict it to safe read-only queries.
                    result = api_call(
                        "POST", "/sql/execute", json_data={"sql": edited_sql}
                    )
                    card["res"] = result.get("raw")
                    card["err"] = None
                except Exception as exc:
                    card["err"] = str(exc)
                    card["res"] = None
                st.rerun()

            if card.get("err"):
                st.error(card["err"])

            raw = card.get("res")
            if raw is not None:
                rows = raw.get("rows") or []
                columns = raw.get("columns") or []
                if not rows:
                    st.caption("Query returned no rows.")
                else:
                    dataframe = pd.DataFrame(rows, columns=columns)
                    st.dataframe(dataframe, use_container_width=True, hide_index=True)
                if raw.get("truncated"):
                    st.caption("Results were truncated by the backend.")
