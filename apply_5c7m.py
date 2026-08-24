from pathlib import Path

path = Path("backend/api/routers/days.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "from backend.services.generic_order_candidates import (\n"
    "    GenericOrderCandidateService,\n"
    ")\n",
    "from backend.services.generic_eating_out_candidates import (\n"
    "    GenericEatingOutCandidateService,\n"
    ")\n"
    "from backend.services.generic_order_candidates import (\n"
    "    GenericOrderCandidateService,\n"
    ")\n",
    1,
)

anchor = '''        all_candidates = MealCandidateService().build(
'''
insert = '''        generic_eating_out = []
        if normalized_mode == "out":
            generic_eating_out = (
                GenericEatingOutCandidateService().build(
                    meal_type=meal_type,
                    known_candidates=eating_out,
                    target_count=3,
                )
            )

        all_candidates = MealCandidateService().build(
'''
if anchor not in text:
    raise SystemExit("Fallback anchor not found")
text = text.replace(anchor, insert, 1)

anchor = '''                *eating_out,
            ],
'''
replacement = '''                *eating_out,
                *generic_eating_out,
            ],
'''
if anchor not in text:
    raise SystemExit("Candidate anchor not found")
text = text.replace(anchor, replacement, 1)

anchor = '            "known_eating_out_count": len(eating_out),\n'
replacement = (
    '            "known_eating_out_count": len(eating_out),\n'
    '            "generic_eating_out_count": len(generic_eating_out),\n'
)
if anchor not in text:
    raise SystemExit("Response anchor not found")
text = text.replace(anchor, replacement, 1)

path.write_text(text, encoding="utf-8")
print("Updated:", path)
