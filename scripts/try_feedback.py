from src.orchestrator import Orchestrator

o = Orchestrator()
FENCE = "`" * 3

solution_msg = (
    "Here is the correct implementation:\n"
    f"{FENCE}python\n"
    "from flask import Flask, jsonify\n\n"
    "app = Flask(__name__)\n\n"
    "@app.route('/hello')\n"
    "def hello():\n"
    "    return jsonify(message='Hello, world!')\n\n"
    "if __name__ == '__main__':\n"
    "    app.run(debug=True)\n"
    f"{FENCE}"
)

print("1) First ask (should fail):")
print(o.handle("Build a Flask API with one endpoint"))
print("   awaiting_solution =", o.awaiting_solution, "\n")

print("2) User sends the solution:")
print(o.handle(solution_msg))
print("   awaiting_solution =", o.awaiting_solution, "\n")

print("3) Ask again, worded differently:")
hits = o.retriever.search("Create a Flask app with a single /hello endpoint")
print("   top hit:", hits[0]["id"], round(hits[0]["distance"], 3))
print(o.handle("Create a Flask app with a single /hello endpoint"))

print("\n4) Non-solution reply is ignored:")
o.handle("Build a CNN model in PyTorch")        # not found, flag set
print("   awaiting_solution =", o.awaiting_solution)
print(o.handle("never mind, how do I reverse a string?")[:200])
print("   awaiting_solution =", o.awaiting_solution)

# cleanup (remove these two lines to keep the learned entry)
o.retriever.collection.delete(where={"source": "user_feedback"})
print("\nCleaned up. Count:", o.retriever.count())
