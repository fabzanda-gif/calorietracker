from pathlib import Path
import json
import shutil


ROOT = Path("frontend")

if not ROOT.exists():
    raise SystemExit(
        "frontend/ not found. Run this script from the repository root."
    )

package_path = ROOT / "package.json"
package = json.loads(
    package_path.read_text(
        encoding="utf-8",
    )
)

dependencies = package.setdefault(
    "dependencies",
    {},
)

dependencies[
    "@supabase/supabase-js"
] = "^2.57.4"

package_path.write_text(
    json.dumps(
        package,
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)

payload_root = Path(
    "_5d2_payload/frontend"
)

if not payload_root.exists():
    raise SystemExit(
        "_5d2_payload/frontend not found."
    )

for source in payload_root.rglob("*"):
    if source.is_dir():
        continue

    relative = source.relative_to(
        payload_root
    )
    destination = ROOT / relative
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    shutil.copy2(
        source,
        destination,
    )

print("Updated frontend files.")
print(
    "Next: cd frontend && "
    "npm install && npm run typecheck"
)
