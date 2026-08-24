from pathlib import Path

path = Path("backend/tests/test_api_ranked_meal_options.py")
text = path.read_text(encoding="utf-8")

needle = """class FakeMealsRepository:
"""

if needle not in text:
    raise SystemExit("FakeMealsRepository not found; no changes made.")

# Insert the compatibility method immediately after the class declaration.
replacement = """class FakeMealsRepository:
    def list_history_compatible(self, user_id):
        # This test predates order-history candidates. Keep its original
        # scenario unchanged by explicitly providing no order history.
        return ([], True)

"""

if "def list_history_compatible(self, user_id):" in text:
    print("Already fixed; no changes needed.")
else:
    text = text.replace(needle, replacement, 1)
    path.write_text(text, encoding="utf-8")
    print("Updated:", path)
