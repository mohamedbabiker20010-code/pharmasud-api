#!/usr/bin/env python3
"""Generate a reproducible route and mutation inventory for release review."""

import argparse
import inspect
import re
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parents[1]
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CLOSED_ROUTES = {"/api/auth/seed-demo", "/api/auth/create-pharmacy"}
ONBOARDING_ROUTES = {"/api/auth/activate", "/api/auth/setup"}


def dependency_names(dependant):
    names = set()
    for dependency in dependant.dependencies:
        call = dependency.call
        name = getattr(call, "__name__", call.__class__.__name__)
        if name in {"checker", "permission_checker"} and getattr(call, "__closure__", None):
            values = [cell.cell_contents for cell in call.__closure__]
            permission = next((value for value in values if isinstance(value, str) and "." in value), None)
            name = f"permission:{permission}" if permission else "permission"
        names.add(name)
        names.update(dependency_names(dependency))
    return names


def rate_limit_for(endpoint):
    key = f"{endpoint.__module__}.{endpoint.__name__}"
    limits = main.limiter._route_limits.get(key, [])
    return ", ".join(str(item.limit) for item in limits) or "none"


def route_rows():
    rows = []
    for route in main.app.routes:
        if not hasattr(route, "dependant"):
            continue
        methods = sorted(set(getattr(route, "methods", set())) - {"HEAD", "OPTIONS"})
        if not methods:
            continue
        endpoint = route.endpoint
        source_endpoint = inspect.unwrap(endpoint)
        source = inspect.getsourcefile(source_endpoint) or "framework"
        try:
            line = inspect.getsourcelines(source_endpoint)[1]
        except (OSError, TypeError):
            line = 0
        deps = dependency_names(route.dependant)
        auth = "JWT" if {"get_current_user", "require_admin"} & deps or any(item.startswith("permission:") for item in deps) else "none"
        authorization = ", ".join(sorted(item for item in deps if item == "require_admin" or item.startswith("permission:"))) or "none"
        mutates = bool(set(methods) & MUTATING_METHODS) and route.path not in CLOSED_ROUTES and route.path != "/api/auth/login"
        destructive = "DELETE" in methods or any(token in route.path for token in ("reset-password", "change-password", "toggle"))
        if route.path in CLOSED_ROUTES:
            exposure, risk = "404 in all environments", "closed"
        elif route.path in ONBOARDING_ROUTES:
            exposure, risk = "public; product-key gated", "controlled onboarding"
        elif auth == "JWT":
            exposure, risk = "authenticated", "protected"
        else:
            exposure, risk = "public", "read-only" if not mutates else "review"
        rows.append([
            ",".join(methods), route.path, endpoint.__name__, f"{Path(source).name}:{line}",
            auth, authorization, rate_limit_for(endpoint), "YES" if mutates else "NO",
            "YES" if destructive else "NO", exposure, risk,
        ])
    return rows


def mutation_rows():
    patterns = {
        "user insert": re.compile(r"\bUser\s*\("),
        "user delete": re.compile(r"query\(User\).*delete|db\.delete\(employee\)"),
        "password_hash": re.compile(r"password_hash\s*="),
        "username": re.compile(r"username\s*="),
        "pharmacy_id": re.compile(r"pharmacy_id\s*="),
        "role": re.compile(r"(?<!_)role\s*="),
        "role_id": re.compile(r"role_id\s*="),
        "is_active": re.compile(r"is_active\s*="),
        "raw user SQL": re.compile(r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+users", re.I),
    }
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".sql", ".sh", ".ps1", ".yaml", ".yml", ".json"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for category, pattern in patterns.items():
                if pattern.search(line):
                    rows.append([str(path.relative_to(ROOT)), str(number), category, line.strip()[:100]])
    return rows


def markdown_table(headers, rows):
    output = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    output.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return "\n".join(output)


def build_report():
    routes = route_rows()
    mutations = mutation_rows()
    return "\n".join([
        "# PharmaSUD Production Readiness Evidence",
        "",
        "Generated from the release branch by `scripts/security_inventory.py`.",
        "",
        "## Route Security Inventory",
        "",
        markdown_table(
            ["Method", "Path", "Function", "Source", "Auth", "Authorization", "Rate", "Mutates", "Destructive", "Exposure", "Risk"],
            routes,
        ),
        "",
        f"Route count: {len(routes)}.",
        "",
        "## User Mutation Inventory",
        "",
        markdown_table(["File", "Line", "Category", "Evidence"], mutations),
        "",
        "## Automatic Execution",
        "",
        "Production starts only `uvicorn main:app`. FastAPI lifespan calls `startup.initialize_database()`, which creates schema/RBAC metadata only. It does not import or invoke demo/test/maintenance scripts. No GitHub Actions, cron, Celery, APScheduler, or background worker configuration exists.",
        "",
        "## External PostgreSQL Gate",
        "",
        "`render.yaml` expects dashboard-supplied `DATABASE_URL`. Real Neon startup/integration remains an external gate until credentials are supplied.",
    ])


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main_cli()
