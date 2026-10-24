import sys
import time

import sounddevice as sd

from src.llm import LLM
from src.sql import SQLiteDB, format_table
from src.voice import Voice

print("Input device:", sd.query_devices(kind="input")["name"])

t = time.time()
voice = Voice()
print(f"Whisper model loaded in {time.time() - t:.1f}s")

db = None
if len(sys.argv) > 1:                               # optional CSV path enables the full pipeline
    db = SQLiteDB()
    print(db.load_csv(sys.argv[1]))

input("\nPress Enter to start recording...")
voice.start_recording()
input("Recording... press Enter to stop.")
audio = voice.stop_recording()
peak = abs(audio).max() if audio.size else 0
print(f"Recorded {len(audio) / 16000:.1f}s, peak level {peak:.3f}")

hint = None
if db:
    hint = "Table columns: " + ", ".join(c.replace("_", " ") for c in db.columns()) + "."

t = time.time()
text = voice.transcribe(audio, hint=hint)
print(f"Transcript ({time.time() - t:.1f}s): {text!r}")
if not text:
    raise SystemExit("Nothing recognized. Check the mic level above.")

if db:
    llm, schema = LLM(), db.schema()
    sql = llm.text2sql(text, schema)
    for attempt in range(2):                        # same retry loop as try_sql.py
        try:
            result = db.execute(sql)
            break
        except Exception as e:
            if attempt == 1:
                raise SystemExit(f"SQL failed: {e}\n{sql}")
            sql = llm.text2sql(text, schema, previous_sql=sql, error=str(e))
    print("\nSQL:", sql)
    print(format_table(result))