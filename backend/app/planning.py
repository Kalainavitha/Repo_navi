from datetime import date, timedelta
import math
import re

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_LOOKUP = {name.lower(): index for index, name in enumerate(WEEKDAY_NAMES)}
TASK_CATEGORIES = ["UI/Frontend", "Backend", "QA/Testing", "Integration", "DevOps/Deployment", "Documentation", "Planning & Analysis", "Other"]

PRIORITY_NAMES = {1: "Low", 2: "Medium", 3: "High"}
PRIORITY_RANKS = {"Low": 1, "Medium": 2, "High": 3}
SEVERITY_WEIGHT = {"High": 10, "Medium": 4, "Low": 1}
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def normalize_category(value):
    key = re.sub(r"[^a-z0-9]", "", str(value or "").lower())
    aliases = {
        "frontend": "UI/Frontend", "frontendbuild": "UI/Frontend", "ui": "UI/Frontend",
        "uifrontend": "UI/Frontend", "backend": "Backend", "api": "Backend",
        "backendapi": "Backend", "backendapis": "Backend", "datamodel": "Backend",
        "qatesting": "QA/Testing", "qa": "QA/Testing", "testing": "QA/Testing",
        "qualityassurance": "QA/Testing", "integration": "Integration",
        "devops": "DevOps/Deployment", "deployment": "DevOps/Deployment",
        "devopsdeployment": "DevOps/Deployment", "infrastructuresetup": "DevOps/Deployment",
        "releasepreparation": "DevOps/Deployment", "documentation": "Documentation",
        "requirementsanalysis": "Planning & Analysis", "architecturedesign": "Planning & Analysis",
        "planninganalysis": "Planning & Analysis", "other": "Other",
    }
    return aliases.get(key, "Other")


def _normalize_workdays(value):
    raw = value or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",") if part.strip()]
    mapped = set()
    for item in raw:
        if isinstance(item, int):
            index = item
        elif isinstance(item, str):
            key = item.strip().lower()
            if key.isdigit():
                index = int(key)
            else:
                index = WEEKDAY_LOOKUP.get(key)
                if index is None:
                    index = WEEKDAY_LOOKUP.get(key.replace("day", "").strip())
        else:
            continue
        if index is not None and 0 <= index <= 6:
            mapped.add(index)
    if not mapped:
        mapped = set(range(5))
    return mapped


def _skills(member):
    found = set()
    for skill in member.get("skills", []) or []:
        skill = str(skill).strip().lower()
        if skill:
            found.add(skill)
            found.update(re.findall(r"[a-z0-9]+", skill))
    return found


def _normalize_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------------------
# Story analysis. Keywords are matched on whole words (a few on word stems), never on
# substrings, so "ui" no longer matches "build" and "api" no longer matches "capital".
# --------------------------------------------------------------------------------------

BACKEND_WORDS = [
    "api", "apis", "endpoint", "endpoints", "backend", "server", "service", "services", "database", "data",
    "store", "storage", "save", "persist", "record", "records", "report", "reports", "search", "query",
    "calculate", "calculation", "process", "payment", "payments", "invoice", "billing", "order", "orders",
    "inventory", "schedule", "queue", "batch", "validate", "validation", "permission", "permissions",
    "role", "roles", "authenticate", "authentication", "authorization", "login", "password", "token",
    "session", "otp", "register", "registration", "signup", "account", "audit",
]
UI_WORDS = [
    "ui", "ux", "page", "pages", "screen", "screens", "form", "forms", "dashboard", "view", "display",
    "show", "button", "interface", "frontend", "mobile", "responsive", "layout", "navigation", "menu",
    "chart", "charts", "table", "list", "click", "filter", "sort", "upload", "download", "notification",
    "notifications", "theme", "visual", "widget", "calendar", "profile", "homepage", "landing",
]
INTEGRATION_WORDS = [
    "integrate", "integration", "integrations", "third", "webhook", "webhooks", "sync", "synchronize",
    "import", "export", "email", "sms", "gateway", "oauth", "sso", "external", "crm", "erp", "slack",
    "stripe", "paypal", "salesforce",
]
DEVOPS_WORDS = [
    "deploy", "deployment", "infrastructure", "pipeline", "ci", "cd", "hosting", "cloud", "aws", "azure",
    "gcp", "docker", "kubernetes", "monitoring", "logging", "backup", "migration", "migrate",
    "scalability", "scalable", "uptime", "release",
]
DOCS_WORDS = ["document", "documentation", "guide", "manual", "training", "readme", "handbook"]
SECURITY_WORDS = [
    "security", "secure", "encrypt", "encryption", "compliance", "gdpr", "hipaa", "authentication",
    "authorization", "permission", "permissions", "password", "login", "token", "otp", "sso", "oauth",
]
COMPLEX_WORDS = [
    "realtime", "encrypt", "encryption", "payment", "payments", "multitenant", "scalable", "scalability",
    "ai", "oauth", "sso", "integration", "integrate", "migration", "migrate", "compliance", "analytics",
    "recommendation", "concurrent", "offline", "sync", "synchronize",
]
COMPLEX_PHRASES = ["real time", "real-time", "machine learning", "multi tenant", "multi-tenant"]
CRITICAL_WORDS = ["critical", "must", "mandatory", "security", "payment", "payments", "compliance", "urgent"]

BACKEND_PROJECT_TYPES = {"api", "backend", "service", "data", "integration", "platform"}
FRONTEND_PROJECT_TYPES = {"mobile", "web", "website", "frontend", "ui", "app", "application", "portal"}

PHASES = {
    "setup": {
        "phase": "Infrastructure setup", "role": "Full-Stack Developer", "rank": 3, "base": 8.0,
        "skills": ["devops", "setup", "git", "ci", "cd", "docker", "infrastructure", "backend", "python", "node", "aws", "linux"],
    },
    "design": {
        "phase": "Architecture & design", "role": "Project Manager", "rank": 2, "base": 4.0,
        "skills": ["architecture", "design", "planning", "analysis", "risk", "stakeholder"],
    },
    "backend": {
        "phase": "Backend", "role": "Backend Developer", "rank": 3, "base": 8.0,
        "skills": ["backend", "api", "database", "python", "fastapi", "sql", "node", "java", "django", "server", "security"],
    },
    "frontend": {
        "phase": "Frontend", "role": "Frontend Developer", "rank": 2, "base": 6.0,
        "skills": ["frontend", "ui", "ux", "react", "typescript", "javascript", "css", "html", "vue", "angular"],
    },
    "integration": {
        "phase": "Integration", "role": "Full-Stack Developer", "rank": 2, "base": 4.0,
        "skills": ["integration", "api", "frontend", "backend", "workflow", "rest", "webhook", "python", "fastapi", "react", "typescript", "javascript", "node"],
    },
    "devops": {
        "phase": "Infrastructure setup", "role": "DevOps Engineer", "rank": 2, "base": 3.0,
        "skills": ["devops", "deployment", "docker", "aws", "ci", "cd", "cloud", "kubernetes", "linux"],
    },
    "qa": {
        "phase": "QA / Testing", "role": "QA Engineer", "rank": 1, "base": 3.0,
        "skills": ["qa", "test", "testing", "automation", "validation", "selenium", "cypress", "verify"],
    },
    "docs": {
        "phase": "Documentation", "role": "Project Manager", "rank": 1, "base": 2.0,
        "skills": ["documentation", "writing", "guide", "support", "planning"],
    },
    "release": {
        "phase": "Release preparation", "role": "QA Engineer", "rank": 2, "base": 4.0,
        "skills": ["qa", "release", "deployment", "planning", "stakeholder", "testing"],
    },
    "implementation": {
        "phase": "Implementation", "role": "Full-Stack Developer", "rank": 2, "base": 6.0,
        "skills": ["backend", "frontend", "api", "react", "python", "javascript", "database"],
    },
}


def _tokens(text) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _hit(tokens: set[str], words) -> int:
    return sum(1 for word in words if word in tokens)


HEADING_PREFIX = re.compile(r"^\s*(?:user\s+story|story|requirement|epic|feature)\s*(?:#?\d+)?\s*[:\-\u2013\u2014]?\s*", re.IGNORECASE)
HEADING_METADATA = re.compile(r"\b(?:story\s*id|priority|status|draft|epic|objective|acceptance|scope|owner|version)\b", re.IGNORECASE)


def _clean_heading(text: str) -> str:
    """Turn a pasted document heading ("User Story: X ... Story ID DASH-001 Priority Medium") into just "X"."""
    text = re.sub(r"[^A-Za-z0-9 /&'(),.\-]+", " ", str(text or ""))
    text = HEADING_PREFIX.sub("", re.sub(r"\s+", " ", text)).strip()
    cut = HEADING_METADATA.search(text)
    if cut and cut.start() > 0:
        text = text[: cut.start()]
    # "Dashboard Landing Page Simple dashboard landing page" -> keep up to the first copy of the repeated phrase
    words = text.split()
    lowered = [word.lower().strip(".,()") for word in words]
    for size in range(6, 2, -1):
        for start in range(0, len(words) - size * 2 + 1):
            phrase = lowered[start:start + size]
            for later in range(start + size, len(words) - size + 1):
                if lowered[later:later + size] == phrase:
                    return " ".join(words[:start + size]).strip(" .,:;-/")
    return text.strip(" .,:;-/")


def _feature_name(story: dict, position: int) -> str:
    raw = str(story.get("title") or "")
    raw = re.split(r"\s*,?\s+so that\b", raw, maxsplit=1, flags=re.IGNORECASE)[0]
    raw = _clean_heading(raw)
    raw = re.sub(r"^(?:to\s+)?(?:be able to\s+)?", "", raw.strip(), flags=re.IGNORECASE).strip(" .,:;")
    raw = re.sub(r"^(?:a|an|the)\s+", "", raw, flags=re.IGNORECASE)
    if len(raw) < 3:
        return f"Requirement {position}"
    raw = raw[0].upper() + raw[1:]
    if len(raw) > 55:
        raw = raw[:55].rsplit(" ", 1)[0].rstrip(" ,;") + "…"
    return raw


def _want_clause(story: dict, feature: str) -> str:
    text = re.sub(r"\s+", " ", str(story.get("description") or "")).strip()
    match = re.search(r"\bI (?:want|need|would like)\s+(?:to\s+)?(.+?)(?:,?\s+so that\b|[.!?]|$)", text, re.IGNORECASE)
    clause = match.group(1).strip() if match else ""
    if not clause:
        # No "I want ..." sentence (e.g. a pasted heading): stay neutral instead of echoing document metadata.
        clause = f"use the \u201c{feature}\u201d feature"
    return clause[:110].rstrip(" ,;")


def _story_facets(story: dict, project: dict) -> dict:
    text = " ".join([
        str(story.get("title") or ""), str(story.get("description") or ""),
        " ".join(str(item) for item in story.get("acceptance_criteria") or []),
    ])
    tokens = _tokens(text)
    flat = " ".join(re.findall(r"[a-z0-9\-]+", text.lower()))
    facets = {
        "backend": _hit(tokens, BACKEND_WORDS) > 0,
        "ui": _hit(tokens, UI_WORDS) > 0,
        "integration": _hit(tokens, INTEGRATION_WORDS) > 0,
        "devops": _hit(tokens, DEVOPS_WORDS) > 0,
        "docs": _hit(tokens, DOCS_WORDS) > 0,
        "security": _hit(tokens, SECURITY_WORDS) > 0,
    }
    if facets["integration"] and not facets["backend"]:
        facets["backend"] = True

    if not (facets["backend"] or facets["ui"] or facets["devops"]):
        # The story text says nothing specific: fall back on the project type, only as a weak prior.
        type_tokens = _tokens(project.get("project_type"))
        if type_tokens & BACKEND_PROJECT_TYPES:
            facets["backend"] = True
        elif type_tokens & FRONTEND_PROJECT_TYPES:
            facets["backend"] = facets["ui"] = True
        else:
            facets["generic"] = True

    complex_hits = _hit(tokens, COMPLEX_WORDS) + sum(1 for phrase in COMPLEX_PHRASES if phrase in flat)
    words = len(re.findall(r"[a-z0-9]+", text.lower()))
    criteria = len(story.get("acceptance_criteria") or [])
    facets["words"] = words
    facets["criteria"] = criteria
    facets["complex_hits"] = complex_hits
    facets["critical"] = _hit(tokens, CRITICAL_WORDS) > 0
    return facets


def _effort(base: float, facets: dict, complexity: str) -> float:
    size = min(2.0, max(0.75, 0.75 + facets["words"] / 70)) + facets["criteria"] * 0.06
    project_factor = {"Low": 0.8, "Medium": 1.0, "High": 1.3}.get(str(complexity or "Medium").title(), 1.0)
    story_factor = 1 + 0.1 * min(facets["complex_hits"], 4)
    return max(2.0, round(base * size * project_factor * story_factor * 2) / 2)


def _task_priority(phase_key: str, story: dict, facets: dict, project: dict) -> str:
    rank = PHASES[phase_key]["rank"]
    story_priority = str(story.get("priority") or "Medium").title()
    if story_priority == "High":
        rank += 1
    elif story_priority == "Low":
        rank -= 1
    if facets["critical"] and PHASES[phase_key]["rank"] >= 2:
        rank += 1
    if str(project.get("priority") or "").title() == "High" and PHASES[phase_key]["rank"] >= 2:
        rank += 1
    return PRIORITY_NAMES[max(1, min(3, rank))]


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _phase_copy(phase_key: str, feature_title: str, want: str, facets: dict) -> dict:
    secure = facets.get("security")
    feature = f"\u201c{feature_title}\u201d"
    copy = {
        "setup": (
            "Set up repository, environments and CI/CD",
            "Create the repository, development and staging environments, and the build/deploy pipeline the whole team will use.",
            "Repository, environments and CI pipeline ready for the team.",
            ["Team can build, run and deploy the project from a clean checkout"],
        ),
        "design": (
            f"Design approach: {feature_title}",
            f"Clarify the requirement, agree the technical approach and edge cases for {feature}, and confirm what 'done' looks like before build starts.",
            f"Agree the approach and edge cases for {feature}.",
            ["Approach and open questions agreed with the product owner"],
        ),
        "backend": (
            f"Build secure backend and access rules: {feature_title}" if secure else f"Build backend logic: {feature_title}",
            f"Implement the server-side logic, data handling and validation needed so users can {want}."
            + (" Includes access control and security checks." if secure else ""),
            f"Server-side logic, data and validation so users can {want}.",
            ["Endpoints and business rules implemented with validation", "Unit tests cover the main and error paths"],
        ),
        "frontend": (
            f"Build screens: {feature_title}",
            f"Build the screens and interactions that let users {want}, including loading, empty and error states.",
            f"User-facing screens so users can {want}.",
            ["Screens work on supported devices", "Loading, empty and error states are handled"],
        ),
        "integration": (
            f"Integrate end to end: {feature_title}",
            f"Connect the screens to the backend and any external services so the {feature} flow works end to end.",
            f"Connect UI, backend and external services for {feature}.",
            ["The flow works end to end against real services"],
        ),
        "devops": (
            f"Prepare deployment: {feature_title}",
            f"Prepare environments, configuration and release steps required to ship {feature}.",
            f"Environment and release steps needed to ship {feature}.",
            ["Configuration is versioned and the release steps are repeatable"],
        ),
        "qa": (
            f"Test and verify: {feature_title}",
            f"Verify {feature} against its acceptance criteria, cover edge cases and fix defects found.",
            f"Verify {feature} against its acceptance criteria and fix defects.",
            [],
        ),
        "docs": (
            f"Document: {feature_title}",
            f"Write the user and support documentation for {feature}.",
            f"User and support documentation for {feature}.",
            ["Documentation reviewed by someone outside the build team"],
        ),
        "release": (
            "Release preparation and user acceptance testing",
            "Run the full regression and user acceptance pass, fix blockers and prepare the go-live checklist.",
            "Full regression, user acceptance and go-live checklist.",
            ["Stakeholders sign off the release", "No open blocker defects"],
        ),
        "implementation": (
            f"Implement: {feature_title}",
            f"Build the {feature} capability end to end so users can {want}.",
            f"End-to-end implementation so users can {want}.",
            ["The capability works as described in the story"],
        ),
    }[phase_key]
    return {"title": copy[0], "description": copy[1], "summary": _clip(copy[2], 150), "criteria": copy[3]}


def _build_tasks(project: dict, stories: list[dict]) -> list[dict]:
    complexity = project.get("complexity") or "Medium"
    tasks: list[dict] = []
    story_last_dev: dict[str, str] = {}
    use_bookends = len(stories) >= 3

    def next_id():
        return f"TSK-{len(tasks) + 1:03d}"

    def add(phase_key, story, facets, feature, want, effort, depends_on, story_ids):
        copy = _phase_copy(phase_key, feature, want, facets)
        spec = PHASES[phase_key]
        criteria = copy["criteria"]
        if phase_key == "qa":
            criteria = [str(item) for item in (story or {}).get("acceptance_criteria") or []] or [f"Confirm {feature} works as expected."]
        task = {
            "id": next_id(),
            "title": copy["title"],
            "description": copy["description"],
            "summary": copy["summary"],
            "story_ids": story_ids,
            "category": normalize_category(spec["phase"]),
            "phase": spec["phase"],
            "effort_hours": effort,
            "remaining_hours": effort,
            "priority": _task_priority(phase_key, story or {}, facets, project),
            "required_skills": list(spec["skills"]),
            "preferred_role": spec["role"],
            "assignee_id": None,
            "assignee_name": None,
            "dependencies": list(dict.fromkeys(depends_on)),
            "acceptance_criteria": criteria,
            "start_date": None,
            "end_date": None,
            "status": "Pending",
            "uncertain": False,
            "rationale": "",
            "warning": None,
            "source_story": (story or {}).get("title", "Project-wide"),
            "risk_level": "Low",
            "risk_note": None,
            "daily_allocations": [],
        }
        tasks.append(task)
        return task["id"]

    setup_id = None
    if use_bookends:
        setup_id = add(
            "setup", None, {"words": 40, "criteria": 0, "complex_hits": 0, "critical": False, "security": False},
            "the project", "build and ship the project", _effort(PHASES["setup"]["base"], {"words": 40, "criteria": 0, "complex_hits": 0}, complexity), [], [],
        )

    qa_ids: list[str] = []
    total_dev = 0.0
    for position, story in enumerate(stories, start=1):
        story_id = story.get("id", f"ST-{position:03d}")
        feature = _feature_name(story, position)
        facets = _story_facets(story, project)
        want = _want_clause(story, feature)

        entry_deps: list[str] = []
        for dependency_id in story.get("dependencies") or []:
            if dependency_id in story_last_dev:
                entry_deps.append(story_last_dev[dependency_id])
        if setup_id:
            entry_deps.append(setup_id)

        def effort_for(key):
            return _effort(PHASES[key]["base"], facets, complexity)

        dev_ids: list[str] = []
        large = facets["words"] > 55 or facets["criteria"] >= 4 or facets["complex_hits"] >= 2 or str(complexity).title() == "High"

        design_id = None
        if facets.get("generic"):
            dev_ids.append(add("implementation", story, facets, feature, want, effort_for("implementation"), entry_deps, [story_id]))
        else:
            if large:
                design_id = add("design", story, facets, feature, want, effort_for("design"), entry_deps, [story_id])
            base_deps = [design_id] if design_id else entry_deps
            backend_id = frontend_id = None
            if facets["backend"]:
                backend_id = add("backend", story, facets, feature, want, effort_for("backend") * (1.2 if facets["security"] else 1.0), base_deps, [story_id])
                dev_ids.append(backend_id)
            if facets["ui"]:
                frontend_id = add("frontend", story, facets, feature, want, effort_for("frontend"), base_deps, [story_id])
                dev_ids.append(frontend_id)
            if facets["integration"] or (backend_id and frontend_id and str(complexity).title() != "Low"):
                dev_ids.append(add(
                    "integration", story, facets, feature, want, effort_for("integration"),
                    [item for item in (backend_id, frontend_id) if item] or base_deps, [story_id],
                ))
            if facets["devops"]:
                dev_ids.append(add("devops", story, facets, feature, want, effort_for("devops"), [backend_id] if backend_id else base_deps, [story_id]))

        dev_effort = sum(task["effort_hours"] for task in tasks if task["id"] in dev_ids)
        total_dev += dev_effort
        qa_effort = max(2.0, round(dev_effort * 0.3 * 2) / 2)
        qa_id = add("qa", story, facets, feature, want, qa_effort, dev_ids or entry_deps, [story_id])
        qa_ids.append(qa_id)
        last_id = qa_id
        if facets["docs"] or str(complexity).title() == "High":
            last_id = add("docs", story, facets, feature, want, effort_for("docs"), [qa_id], [story_id])
        story_last_dev[story_id] = (dev_ids[-1] if dev_ids else qa_id)

    if use_bookends:
        add(
            "release", None, {"words": 40, "criteria": 0, "complex_hits": 0, "critical": False, "security": False},
            "the release", "go live", max(4.0, round(total_dev * 0.08 * 2) / 2), qa_ids, [],
        )
    return tasks


# --------------------------------------------------------------------------------------
# Assignment and scheduling
# --------------------------------------------------------------------------------------

GENERIC_ROLE_WORDS = {"developer", "engineer", "specialist", "analyst", "member", "team"}


def _role_fit(preferred_role: str, member_role: str, is_lead: bool = False) -> float:
    wanted = _tokens(preferred_role) - GENERIC_ROLE_WORDS
    have = _tokens(member_role)
    if wanted & have:
        return 3.0
    if {"full", "stack", "fullstack"} & have and preferred_role in {"Backend Developer", "Frontend Developer", "Full-Stack Developer"}:
        return 1.5
    if preferred_role == "Full-Stack Developer" and {"backend", "frontend", "developer", "engineer"} & have:
        return 1.5
    if preferred_role == "Project Manager" and (is_lead or "lead" in have or "architect" in have):
        return 2.0
    return 0.0


def _fit_score(member: dict, task: dict) -> float:
    skills = _skills(member)
    overlap = sum(1 for skill in task["required_skills"] if skill in skills)
    roles = f'{member.get("role", "")} {member.get("additional_role") or ""}'
    return min(overlap, 4) * 2.0 + _role_fit(task["preferred_role"], roles, bool(member.get("is_lead")))


def _daily_capacity(member: dict, project: dict) -> float:
    return float(member.get("hours_per_day", project.get("hours_per_day", 8))) * float(member.get("allocation", 100)) / 100


def _available_hours(member: dict, project: dict, start: date, end: date) -> float:
    project_days = _normalize_workdays(project.get("working_days"))
    member_days = _normalize_workdays(member.get("working_days") or project.get("working_days"))
    holidays = {_normalize_date(value) for value in project.get("holidays", []) or [] if _normalize_date(value)}
    leave = {_normalize_date(value) for value in member.get("leave_dates", []) or [] if _normalize_date(value)}
    available_from = _normalize_date(member.get("available_from"))
    available_until = _normalize_date(member.get("available_until"))
    capacity = _daily_capacity(member, project)
    total = 0.0
    cursor = start
    while cursor <= end:
        if (
            cursor.weekday() in (project_days & member_days)
            and cursor not in holidays and cursor not in leave
            and (not available_from or cursor >= available_from)
            and (not available_until or cursor <= available_until)
        ):
            total += capacity
        cursor += timedelta(days=1)
    return total


def _booked_in_window(bookings: dict, member_id: str, start: date, end: date) -> float:
    low, high = start.isoformat(), end.isoformat()
    return sum(hours for day, hours in (bookings.get(member_id) or {}).items() if low <= day <= high)


TECHNICAL_PHASES = {"Backend", "Frontend", "Integration", "QA / Testing", "Infrastructure setup", "Implementation"}
MANAGER_WORDS = {"manager", "lead", "analyst", "owner", "designer", "scrum", "coordinator"}
HANDS_ON_WORDS = {"developer", "engineer", "architect", "tester", "qa", "devops", "programmer", "fullstack"}


def _is_manager_only(member: dict) -> bool:
    """A manager/lead/analyst with no hands-on role: should not be handed build or test work if developers exist."""
    roles = _tokens(f'{member.get("role", "")} {member.get("additional_role") or ""}')
    return bool(roles & MANAGER_WORDS) and not (roles & HANDS_ON_WORDS)


def _rank_candidates(task, members, project, window, projected, bookings):
    """Return member ids ordered best-first for this task, plus whether any real skill match exists.

    High-priority work favours the most experienced qualified person, but every candidate is
    penalised for the weeks of work already queued for them (this plan plus what they are booked
    on in other projects in the first four weeks), so a senior who is already busy gives way.
    """
    start, end = window
    near_end = min(end, start + timedelta(days=27))
    scored = []
    for member in members:
        fit = _fit_score(member, task)
        capacity = _available_hours(member, project, start, end)
        if capacity <= 0:
            continue
        weekly = max(1.0, _daily_capacity(member, project) * len(_normalize_workdays(member.get("working_days") or project.get("working_days"))))
        queued = projected[member["id"]] + _booked_in_window(bookings, member["id"], start, near_end)
        total = projected[member["id"]] + _booked_in_window(bookings, member["id"], start, end)
        scored.append((member, fit, queued / weekly, total / capacity))
    if not scored:
        return [], False
    best_fit = max(item[1] for item in scored)
    matched = best_fit > 0
    pool = [item for item in scored if item[1] >= 0.4 * best_fit] if matched else scored
    ranked = []
    for member, fit, queue_weeks, load in pool:
        experience = min(float(member.get("experience", 0) or 0), 15) / 15
        overload = max(0.0, load - 1.0) * 6
        if task["priority"] == "High":
            score = fit * 0.5 + experience * 8 - queue_weeks * 3.5 - overload
        elif task["priority"] == "Medium":
            score = fit * 0.8 + experience * 2 - queue_weeks * 3.0 - overload
        else:
            score = fit * 0.8 + (1 - experience) * 1.5 - queue_weeks * 3.5 - overload
        # With no skill match, a developer is a better stand-in than a manager for build/test work.
        if fit == 0 and task["phase"] in TECHNICAL_PHASES and _is_manager_only(member):
            score -= 8
        ranked.append((score, member.get("name", ""), member["id"]))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked], matched


def _find_slots(task, member, tasks, project, calendar):
    """Dry-run: where would this member's free capacity let the task fit? Nothing is written."""
    start_date = _normalize_date(project.get("start_date")) or date.today()
    deadline = _normalize_date(project.get("deadline"))
    project_workdays = _normalize_workdays(project.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]))
    member_workdays = _normalize_workdays(member.get("working_days", project.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])))
    workdays = project_workdays & member_workdays
    holiday_dates = {_normalize_date(value) for value in project.get("holidays", []) if _normalize_date(value)}
    leave_dates = {_normalize_date(value) for value in member.get("leave_dates", []) if _normalize_date(value)}
    available_from = _normalize_date(member.get("available_from"))
    available_until = _normalize_date(member.get("available_until"))
    daily_capacity = _daily_capacity(member, project)
    requested_start = _normalize_date(task.get("requested_start_date"))

    current_date = max(start_date, requested_start) if requested_start else start_date
    for dep_id in task.get("dependencies", []):
        dependency = next((candidate for candidate in tasks if candidate["id"] == dep_id), None)
        if dependency and dependency.get("end_date"):
            dep_end = _normalize_date(dependency["end_date"])
            if dep_end:
                current_date = max(current_date, dep_end + timedelta(days=1))

    cursor = current_date
    selected_dates = []
    pending = {}
    remaining = float(task["effort_hours"])
    max_window = deadline + timedelta(days=180) if deadline else start_date + timedelta(days=365)

    while remaining > 0 and cursor <= max_window:
        day_value = cursor.isoformat()
        day_check = cursor.weekday() in workdays and cursor not in holiday_dates and cursor not in leave_dates
        availability_ok = True
        if available_from and cursor < available_from:
            availability_ok = False
        if available_until and cursor > available_until:
            availability_ok = False
        if day_check and availability_ok:
            capacity_left = max(0.0, daily_capacity - calendar.get(day_value, 0.0))
            if capacity_left > 0:
                consumed = min(remaining, capacity_left)
                remaining -= consumed
                pending[day_value] = consumed
                selected_dates.append(cursor)
        cursor += timedelta(days=1)

    if remaining > 0 or not selected_dates:
        return None
    return {"pending": pending, "selected": selected_dates}


def _schedule_task(task, task_index, tasks, members, project, workloads, member_calendar, story_lookup):
    task["daily_allocations"] = []
    member_id = task.get("assignee_id")
    if not member_id:
        return task

    member = next((member for member in members if member["id"] == member_id), None)
    if not member:
        task["assignee_id"] = None
        task["assignee_name"] = None
        task["warning"] = "The task has no valid assignee on the current project roster."
        return task

    calendar = member_calendar.setdefault(member["id"], {})
    slots = _find_slots(task, member, tasks, project, calendar)
    if slots is None:
        # Nothing is written to the shared calendar when a schedule is not feasible.
        task["assignee_id"] = None
        task["assignee_name"] = None
        task["daily_allocations"] = []
        task["warning"] = f"No feasible schedule was possible for {task['title']} within the current team capacity."
        return task

    for day_value, consumed in slots["pending"].items():
        calendar[day_value] = calendar.get(day_value, 0.0) + consumed
        task["daily_allocations"].append({"date": day_value, "hours": round(consumed, 2)})
    task["start_date"] = slots["selected"][0].isoformat()
    task["end_date"] = slots["selected"][-1].isoformat()
    workloads[member["id"]]["assigned_hours"] += float(task["effort_hours"])
    return task


def _copy_bookings(existing_bookings):
    return {member_id: dict(days) for member_id, days in (existing_bookings or {}).items()}


def reschedule_tasks(project: dict, members: list[dict], tasks: list[dict], existing_bookings: dict | None = None):
    workloads = {member["id"]: {"assigned_hours": 0.0, "available_hours": 0.0, "utilization": 0.0} for member in members}
    member_calendar = _copy_bookings(existing_bookings)
    scheduled = []
    for index, task in enumerate(tasks):
        assigned_before = task.get("assignee_id")
        result = _schedule_task(task, index, scheduled, members, project, workloads, member_calendar, {})
        if assigned_before and not result.get("assignee_id"):
            raise ValueError(result.get("warning") or f"No feasible schedule was possible for {task['title']}.")
        scheduled.append(result)
    return scheduled


# --------------------------------------------------------------------------------------
# Risks
# --------------------------------------------------------------------------------------

def _risk(kind, severity, message, task_id=None, member_id=None):
    return {"type": kind, "severity": severity, "message": message, "task_id": task_id, "member_id": member_id}


def _task_risks(task, member_by_id, workloads, deadline, matched_flags, fallback_flags, bookings):
    notes = []
    level = 0

    def note(severity, text):
        nonlocal level
        level = max(level, {"Low": 1, "Medium": 2, "High": 3}[severity])
        notes.append(text)

    member = member_by_id.get(task.get("assignee_id"))
    if not task.get("assignee_id"):
        note("High", "No team member could take this task within the available capacity.")
    else:
        if not matched_flags.get(task["id"], True):
            note("Medium", "No team member matched the required skills; assigned on availability.")
        if task["priority"] == "High" and float(member.get("experience", 0) or 0) < 2:
            note("Medium", f"High-priority task on a member with {float(member.get('experience', 0) or 0):g} years of experience.")
        total_util = workloads.get(member["id"], {}).get("total_utilization", 0)
        if total_util > 100:
            note("High", f"{member['name']} is over capacity ({total_util:g}% of available hours).")
        elif total_util > 85:
            note("Medium", f"{member['name']} is heavily loaded ({total_util:g}% of available hours).")
        if fallback_flags.get(task["id"]):
            note("Low", "The first-choice assignee was busy or had no capacity, so the task moved to the next best match.")
        booked = sum(
            bookings.get(member["id"], {}).get(item["date"], 0.0) for item in task.get("daily_allocations", [])
        )
        if booked > 0:
            note("Low", f"{member['name']} also has {booked:g}h booked on other projects during this task.")
    if task["effort_hours"] > 24:
        note("Medium", f"Large task ({task['effort_hours']:g}h); consider splitting it.")
    if deadline and task.get("end_date") and _normalize_date(task["end_date"]) and _normalize_date(task["end_date"]) > deadline:
        note("High", "Finishes after the project deadline.")
    task["risk_level"] = {0: "Low", 1: "Low", 2: "Medium", 3: "High"}[level]
    task["risk_note"] = " ".join(notes) if notes else None


def _plan_risks(tasks, members, workloads, deadline, projected_completion, buffer_percent, project_start):
    risks = []
    by_id = {member["id"]: member for member in members}

    unassigned = [task for task in tasks if not task.get("assignee_id")]
    for task in unassigned:
        risks.append(_risk("unassigned", "High", f"{task['id']} \"{task['title']}\" could not be scheduled with the current team capacity.", task["id"]))

    if deadline and projected_completion:
        done = date.fromisoformat(projected_completion)
        if done > deadline:
            risks.append(_risk("deadline", "High", f"The plan finishes {(done - deadline).days} day(s) after the deadline ({deadline.isoformat()})."))
        else:
            duration = max(1, (done - project_start).days)
            buffer_days = math.ceil(duration * float(buffer_percent or 0) / 100)
            slack = (deadline - done).days
            if buffer_days and slack < buffer_days:
                risks.append(_risk(
                    "buffer", "Medium",
                    f"Only {slack} day(s) of slack before the deadline, below the {buffer_days} day(s) needed for a {buffer_percent:g}% buffer.",
                ))
    if not deadline:
        risks.append(_risk("deadline", "Low", "No deadline was set, so schedule slippage cannot be measured."))

    for member in members:
        load = workloads[member["id"]]
        if load["total_utilization"] > 100:
            risks.append(_risk("overload", "High", f"{member['name']} is planned at {load['total_utilization']:g}% of available hours.", member_id=member["id"]))
        elif load["total_utilization"] > 85:
            risks.append(_risk("overload", "Medium", f"{member['name']} is planned at {load['total_utilization']:g}% of available hours.", member_id=member["id"]))
        if load.get("other_project_hours", 0) > 0 and load["assigned_hours"] > 0:
            risks.append(_risk(
                "shared", "Low",
                f"{member['name']} is also booked for {load['other_project_hours']:g}h on other projects in this period.",
                member_id=member["id"],
            ))

    high_tasks = [task for task in tasks if task["priority"] == "High" and task.get("assignee_id")]
    if len(members) == 1:
        risks.append(_risk("single_person", "Medium", "The whole plan depends on one team member."))
    elif len(high_tasks) >= 3:
        counts = {}
        for task in high_tasks:
            counts[task["assignee_id"]] = counts.get(task["assignee_id"], 0) + 1
        top_id, top_count = max(counts.items(), key=lambda item: item[1])
        if top_count / len(high_tasks) > 0.6:
            risks.append(_risk(
                "single_person", "Medium",
                f"{by_id[top_id]['name']} owns {top_count} of {len(high_tasks)} high-priority tasks; their absence would stall the plan.",
                member_id=top_id,
            ))

    mismatched = [task for task in tasks if "No team member matched" in (task.get("risk_note") or "")]
    if mismatched:
        risks.append(_risk("skills", "Medium", f"{len(mismatched)} task(s) have no skill match on the team; assigned by availability."))
    juniors = [task for task in tasks if "High-priority task on a member" in (task.get("risk_note") or "")]
    if juniors:
        risks.append(_risk("experience", "Medium", f"{len(juniors)} high-priority task(s) are held by members with under 2 years of experience."))
    large = [task for task in tasks if task["effort_hours"] > 24]
    if large:
        risks.append(_risk("large_task", "Medium", f"{len(large)} task(s) exceed 24h and should be split to reduce estimate risk."))

    risks.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["type"]))
    return risks


# --------------------------------------------------------------------------------------
# Plan generation
# --------------------------------------------------------------------------------------

def _calibrated(task: dict, member_id: str, calibration) -> tuple[dict, float]:
    """The task as this person would experience it: hours stretched/trimmed by what history says about them."""
    if calibration is None:
        return task, 1.0
    factor = float(calibration(member_id, task.get("phase") or ""))
    if factor == 1.0:
        return task, 1.0
    hours = max(1.0, round(float(task["effort_hours"]) * factor * 2) / 2)
    return {**task, "effort_hours": hours, "remaining_hours": hours}, factor


def _generate_plan_once(project: dict, stories: list[dict], existing_bookings: dict | None = None, speed_first: bool = False, calibration=None):
    members = project.get("members", [])
    existing_bookings = _copy_bookings(existing_bookings)
    original_bookings = _copy_bookings(existing_bookings)
    project_start = _normalize_date(project.get("start_date")) or date.today()
    project_deadline = _normalize_date(project.get("deadline"))
    window_end = project_deadline or (project_start + timedelta(days=180))
    window = (project_start, max(window_end, project_start))

    workloads = {member["id"]: {"assigned_hours": 0.0, "available_hours": 0.0, "utilization": 0.0} for member in members}
    member_calendar = existing_bookings
    story_lookup = {story["id"]: story for story in stories if story.get("id")}
    warnings = []

    raw_tasks = _build_tasks(project, stories)
    member_by_id = {member["id"]: member for member in members}

    # Assignment pass: High-priority work is placed first so the most experienced qualified
    # people claim it; projected hours (this plan) plus bookings on other projects keep the
    # load balanced as we go.
    projected = {member["id"]: 0.0 for member in members}
    candidates_by_task: dict[str, list[str]] = {}
    matched_flags: dict[str, bool] = {}
    fallback_flags: dict[str, bool] = {}
    for task in sorted(raw_tasks, key=lambda item: (-PRIORITY_RANKS[item["priority"]], item["id"])):
        ranked, matched = _rank_candidates(task, members, project, window, projected, original_bookings)
        candidates_by_task[task["id"]] = ranked
        matched_flags[task["id"]] = matched
        if not ranked:
            continue
        chosen = member_by_id[ranked[0]]
        task["assignee_id"] = chosen["id"]
        task["assignee_name"] = chosen["name"]
        projected[chosen["id"]] += task["effort_hours"]

    # Schedule in creation order (dependencies always come first). For each task the best few
    # candidates are dry-run against the live calendars (including other projects' bookings).
    # The most experienced-first ranking wins unless that person would finish noticeably later
    # than someone else, with a tolerance that is tighter for lower-priority work.
    tolerance_days = {"High": 0, "Medium": 0, "Low": 0} if speed_first else {"High": 8, "Medium": 3, "Low": 1}
    estimate_factors: dict[str, float] = {}
    scheduled_tasks = []
    for task in raw_tasks:
        options = candidates_by_task.get(task["id"], [])
        original_choice = task.get("assignee_id")
        trials = []
        for rank, member_id in enumerate(options[:4]):
            slots = _find_slots(_calibrated(task, member_id, calibration)[0], member_by_id[member_id], scheduled_tasks, project, member_calendar.get(member_id, {}))
            if slots:
                trials.append((rank, member_id, slots["selected"][-1]))
        if task["phase"] in TECHNICAL_PHASES:
            # A manager with no matching skill only gets build/test work when no hands-on person can take it.
            hands_on = [
                item for item in trials
                if not (_is_manager_only(member_by_id[item[1]]) and _fit_score(member_by_id[item[1]], task) == 0)
            ]
            if hands_on:
                trials = hands_on
        chosen_id = None
        if trials:
            # Prefer candidates who finish inside the deadline. Among those, the best-ranked (most experienced
            # for High work) wins unless they would finish noticeably later. If everyone is late, take the earliest.
            on_time = [item for item in trials if not project_deadline or item[2] <= project_deadline]
            pool = on_time or trials
            earliest = min(item[2] for item in pool)
            allowed = tolerance_days[task["priority"]] if on_time else 0
            acceptable = [item for item in pool if (item[2] - earliest).days <= allowed]
            chosen_id = min(acceptable, key=lambda item: item[0])[1]
            if not speed_first and task["priority"] == "High" and float(member_by_id[chosen_id].get("experience") or 0) < 2:
                # Critical work stays with someone seasoned as long as they can still meet the deadline.
                seasoned = [
                    item for item in trials
                    if float(member_by_id[item[1]].get("experience") or 0) >= 2 and (not project_deadline or item[2] <= project_deadline)
                ]
                if seasoned:
                    chosen_id = min(seasoned, key=lambda item: item[0])[1]
        elif options[4:]:
            for member_id in options[4:]:
                if _find_slots(task, member_by_id[member_id], scheduled_tasks, project, member_calendar.get(member_id, {})):
                    chosen_id = member_id
                    break

        if chosen_id:
            task["assignee_id"] = chosen_id
            task["assignee_name"] = member_by_id[chosen_id]["name"]
            task["warning"] = None
            adjusted, factor = _calibrated(task, chosen_id, calibration)
            if factor != 1.0:
                estimate_factors[task["id"]] = factor
                task["effort_hours"] = adjusted["effort_hours"]
                task["remaining_hours"] = adjusted["remaining_hours"]
            _schedule_task(task, 0, scheduled_tasks, members, project, workloads, member_calendar, story_lookup)
            if chosen_id != original_choice:
                fallback_flags[task["id"]] = True
                if original_choice:
                    projected[original_choice] -= task["effort_hours"]
                projected[chosen_id] += task["effort_hours"]
        else:
            task["assignee_id"] = None
            task["assignee_name"] = None
            task["uncertain"] = True
            if not options:
                task["warning"] = f"No team member has available capacity for {task['phase']} work in this window."
            else:
                task["warning"] = f"No feasible schedule was possible for {task['title']} within the current team capacity."
            warnings.append(task["warning"])
        scheduled_tasks.append(task)

    for story in stories:
        for dependency_id in story.get("dependencies", []) or []:
            if dependency_id not in story_lookup:
                warnings.append(f"Story {story.get('id')} references a missing dependency: {dependency_id}.")

    task_ids = {item["id"] for item in scheduled_tasks}
    for task in scheduled_tasks:
        invalid = [dep for dep in task["dependencies"] if dep not in task_ids]
        if invalid:
            warnings.append(f"Task {task['id']} depends on unknown tasks: {', '.join(invalid)}.")

    # Workloads, including hours the same people already have on other projects.
    for member in members:
        available = _available_hours(member, project, project_start, window[1])
        other = _booked_in_window(original_bookings, member["id"], project_start, window[1])
        assigned = workloads[member["id"]]["assigned_hours"]
        workloads[member["id"]].update({
            "available_hours": round(available, 1),
            "utilization": round(assigned / available * 100, 1) if available else 0.0,
            "other_project_hours": round(other, 1),
            "total_utilization": round((assigned + other) / available * 100, 1) if available else (100.0 if assigned or other else 0.0),
        })
        if workloads[member["id"]]["total_utilization"] > 100:
            workloads[member["id"]]["total_utilization"] = round(workloads[member["id"]]["total_utilization"], 1)

    scheduled_end_dates = [
        d for d in (_normalize_date(task["end_date"]) for task in scheduled_tasks if task.get("end_date"))
        if d is not None
    ]
    projected_completion = max(scheduled_end_dates).isoformat() if scheduled_end_dates else None

    deadline_feasible = True
    if project_deadline and projected_completion:
        deadline_feasible = date.fromisoformat(projected_completion) <= project_deadline
    if not deadline_feasible:
        warnings.append("The generated schedule exceeds the target deadline.")

    buffer_percent = float(project.get("buffer_percent") or 0)
    buffered_completion = None
    if projected_completion:
        done = date.fromisoformat(projected_completion)
        buffered_completion = (done + timedelta(days=math.ceil(max(1, (done - project_start).days) * buffer_percent / 100))).isoformat()

    for task in scheduled_tasks:
        member = member_by_id.get(task.get("assignee_id"))
        if member:
            skills = sorted(_skills(member) & set(task["required_skills"]))[:3]
            task["rationale"] = (
                f"{member['name']} ({float(member.get('experience', 0) or 0):g} yrs, {member.get('role', 'team member')}) "
                f"was chosen for this {task['priority'].lower()}-priority {task['phase'].lower()} task"
                + (f"; matching skills: {', '.join(skills)}" if skills else "")
                + f". Their planned load on this project is {projected[member['id']]:g}h."
            )
        else:
            task["rationale"] = "No assignee could be scheduled for this task."
        factor = estimate_factors.get(task["id"])
        if factor and member:
            gap = round(abs(factor - 1.0) * 100)
            task["rationale"] += (
                f" Estimate adjusted x{factor:g}: {member['name']}'s past {task['phase']} tasks took {gap}% "
                f"{'longer' if factor > 1 else 'less time'} than planned."
            )
        _task_risks(task, member_by_id, workloads, project_deadline, matched_flags, fallback_flags, original_bookings)

    risks = _plan_risks(scheduled_tasks, members, workloads, project_deadline, projected_completion, buffer_percent, project_start)
    if speed_first:
        risks.append(_risk(
            "deadline_first", "Medium",
            "The deadline is tight, so work was spread across the whole team (including less experienced people) to finish sooner.",
        ))
        risks.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["type"]))
    for risk in risks:
        if risk["severity"] != "Low":
            warnings.append(risk["message"])
    risk_score = min(100, sum(SEVERITY_WEIGHT[risk["severity"]] for risk in risks))
    risk_level = "High" if any(r["severity"] == "High" for r in risks) else "Medium" if any(r["severity"] == "Medium" for r in risks) else "Low"

    summary = {
        "story_count": len(stories),
        "task_count": len(scheduled_tasks),
        "completed_tasks": 0,
        "in_progress_tasks": 0,
        "pending_tasks": sum(1 for task in scheduled_tasks if task["status"] == "Pending"),
        "blocked_tasks": 0,
        "unassigned_tasks": sum(1 for task in scheduled_tasks if not task.get("assignee_id")),
        "estimated_hours": round(sum(task["effort_hours"] for task in scheduled_tasks), 1),
        "remaining_hours": round(sum(task["remaining_hours"] for task in scheduled_tasks), 1),
        "progress_percent": 0,
        "projected_completion": projected_completion,
        "buffered_completion": buffered_completion,
        "deadline_feasible": deadline_feasible,
        "schedule_mode": "deadline_first" if speed_first else "experience_first",
        "estimates_adjusted": len(estimate_factors),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risks": risks,
        "warnings": list(dict.fromkeys(warnings)),
    }

    for task in scheduled_tasks:
        task.pop("requested_start_date", None)
    return {"stories": stories, "tasks": scheduled_tasks, "workloads": workloads, "summary": summary}


def generate_plan(project: dict, stories: list[dict], existing_bookings: dict | None = None, calibration=None):
    """Experience-first plan (senior people keep High-priority work). If that misses the deadline, try a
    deadline-first plan that spreads work over the whole team and keep it only if it finishes earlier."""
    plan = _generate_plan_once(project, stories, existing_bookings, calibration=calibration)
    if _normalize_date(project.get("deadline")) and not plan["summary"]["deadline_feasible"]:
        rushed = _generate_plan_once(project, stories, existing_bookings, speed_first=True, calibration=calibration)
        first_end = plan["summary"]["projected_completion"]
        rushed_end = rushed["summary"]["projected_completion"]
        if (
            rushed["summary"]["unassigned_tasks"] <= plan["summary"]["unassigned_tasks"]
            and rushed_end and (not first_end or rushed_end < first_end)
        ):
            return rushed
    return plan


# --------------------------------------------------------------------------------------
# Re-plan from today
# --------------------------------------------------------------------------------------

def replan_from(project: dict, members: list[dict], tasks: list[dict], today: date, existing_bookings: dict | None = None):
    """Reschedule only the unfinished work so that it starts no earlier than `today`.

    Completed tasks are history and pass through untouched (dependants treat them as done). Every other
    assigned task is placed again, in its original order, around leave, holidays, availability and the hours
    people already have on other projects. Each result carries `replanned` (True when new dates were found).
    """
    workloads = {member["id"]: {"assigned_hours": 0.0, "available_hours": 0.0, "utilization": 0.0} for member in members}
    calendar = _copy_bookings(existing_bookings)
    yesterday = today - timedelta(days=1)
    scheduled: list[dict] = []
    results: list[dict] = []

    for task in tasks:
        if task.get("status") == "Completed":
            done = {**task, "daily_allocations": task.get("daily_allocations", []), "replanned": False}
            end = _normalize_date(task.get("end_date"))
            scheduled.append({**done, "end_date": min(end, yesterday).isoformat() if end else None})
            results.append(done)
            continue

        if not task.get("assignee_id"):
            kept = {**task, "daily_allocations": [], "replanned": False}
            scheduled.append(kept)
            results.append(kept)
            continue

        remaining = float(task.get("remaining_hours") or 0) or float(task.get("effort_hours") or 0)
        work = {**task, "effort_hours": remaining, "requested_start_date": today.isoformat(), "warning": None}
        attempt = _schedule_task(work, 0, scheduled, members, project, workloads, calendar, {})
        if attempt.get("assignee_id"):
            result = {
                **task,
                "start_date": attempt["start_date"], "end_date": attempt["end_date"],
                "daily_allocations": attempt["daily_allocations"], "replanned": True,
                "warning": "Halted: resolve the blocker before this can finish on the new date." if task.get("status") == "Blocked" else None,
            }
        else:
            result = {
                **task, "daily_allocations": [], "replanned": False,
                "warning": "No capacity was found to re-plan this task; its previous dates were kept.",
            }
        scheduled.append(result)
        results.append(result)
    return results


# --------------------------------------------------------------------------------------
# New team members: hand unstarted work to people who have none yet
# --------------------------------------------------------------------------------------

PHASE_ROLE: dict[str, str] = {}
for _spec in PHASES.values():
    PHASE_ROLE.setdefault(_spec["phase"], _spec["role"])


def rebalance_unstarted(project: dict, members: list[dict], tasks: list[dict], today: date, existing_bookings: dict | None = None, calibration=None):
    """Offer the project's *unstarted* tasks to people who do not have any work on it yet (new joiners).

    Tasks that are In process, Halted or Completed never move. Every Pending task is re-ranked with the normal rules
    (skills, experience, priority, availability, other projects' bookings); it only changes hands when a newcomer is
    the best fit, so nobody else gets shuffled. All Pending tasks are then scheduled again from `today`.
    Returns (results, newcomer_ids): one dict per task, with `moved` set when the assignee changed.
    """
    member_by_id = {member["id"]: member for member in members}
    busy_ids = {t["assignee_id"] for t in tasks if t.get("assignee_id")}
    newcomers = {member["id"] for member in members if member["id"] not in busy_ids}
    base_bookings = _copy_bookings(existing_bookings)
    calendar = _copy_bookings(existing_bookings)
    workloads = {member["id"]: {"assigned_hours": 0.0, "available_hours": 0.0, "utilization": 0.0} for member in members}
    projected = {member["id"]: 0.0 for member in members}

    start = max(today, _normalize_date(project.get("start_date")) or today)
    deadline = _normalize_date(project.get("deadline"))
    window = (start, max(deadline or (start + timedelta(days=180)), start))
    tolerance = {"High": 8, "Medium": 3, "Low": 1}

    # unstarted work is re-planned; everything else keeps its owner and its hours on the calendar
    for task in tasks:
        if task.get("status") != "Pending":
            owner = task.get("assignee_id")
            if owner:
                for allocation in task.get("daily_allocations", []):
                    day_hours = calendar.setdefault(owner, {})
                    day_hours[allocation["date"]] = day_hours.get(allocation["date"], 0.0) + float(allocation["hours"])
                if task.get("status") != "Completed":
                    projected[owner] = projected.get(owner, 0.0) + float(task.get("remaining_hours") or task.get("effort_hours") or 0)

    scheduled: list[dict] = []
    results: list[dict] = []
    for task in tasks:
        if task.get("status") != "Pending":
            kept = {**task, "moved": False, "replanned": False}
            scheduled.append(kept)
            results.append(kept)
            continue

        work = {
            **task, "preferred_role": PHASE_ROLE.get(task.get("phase") or "", "Full-Stack Developer"),
            "required_skills": task.get("required_skills") or [], "requested_start_date": today.isoformat(),
            "daily_allocations": [], "warning": None,
        }
        previous = task.get("assignee_id")
        ranked, _matched = _rank_candidates(work, members, project, window, projected, base_bookings)
        trials = []
        for rank, member_id in enumerate(ranked[:4]):
            slots = _find_slots(_calibrated(work, member_id, calibration)[0], member_by_id[member_id], scheduled, project, calendar.get(member_id, {}))
            if slots:
                trials.append((rank, member_id, slots["selected"][-1]))
        if work["phase"] in TECHNICAL_PHASES:
            hands_on = [item for item in trials if not (_is_manager_only(member_by_id[item[1]]) and _fit_score(member_by_id[item[1]], work) == 0)]
            trials = hands_on or trials
        chosen = previous
        if trials:
            on_time = [item for item in trials if not deadline or item[2] <= deadline]
            pool = on_time or trials
            earliest = min(item[2] for item in pool)
            allowed = tolerance[work["priority"] if work.get("priority") in tolerance else "Medium"] if on_time else 0
            acceptable = [item for item in pool if (item[2] - earliest).days <= allowed]
            best = min(acceptable, key=lambda item: item[0])[1]
            acceptable_ids = {item[1] for item in acceptable}
            # a newcomer takes the task only when they are the best fit; otherwise the current owner keeps it
            chosen = best if (best in newcomers or previous not in acceptable_ids) else previous
        if chosen is None or chosen not in member_by_id:
            result = {**task, "moved": False, "replanned": False, "daily_allocations": [], "warning": task.get("warning")}
            scheduled.append(result)
            results.append(result)
            continue

        adjusted, factor = _calibrated(work, chosen, calibration)
        work = {**work, "assignee_id": chosen, "assignee_name": member_by_id[chosen]["name"], "effort_hours": adjusted["effort_hours"]}
        placed = _schedule_task(work, 0, scheduled, members, project, workloads, calendar, {})
        if not placed.get("assignee_id"):
            result = {**task, "moved": False, "replanned": False, "daily_allocations": [], "warning": placed.get("warning")}
        else:
            projected[chosen] += float(adjusted["effort_hours"])
            result = {
                **task, "assignee_id": chosen, "assignee_name": member_by_id[chosen]["name"], "effort_hours": adjusted["effort_hours"],
                "remaining_hours": adjusted["remaining_hours"], "start_date": placed["start_date"], "end_date": placed["end_date"],
                "daily_allocations": placed["daily_allocations"], "moved": chosen != previous, "replanned": True, "warning": None,
            }
        scheduled.append(result)
        results.append(result)
    return results, newcomers
