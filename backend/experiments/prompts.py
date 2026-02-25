"""
Load system prompts from agent folders and the organization playbook.
Every agent receives the playbook so analysis is done against organization compliance.
"""
from pathlib import Path

_AGENTS_DIR = Path(__file__).parent / "agents"
# ProjectDocs/Playbook.md at repo root (backend/experiments -> backend -> repo root)
_PLAYBOOK_PATH = Path(__file__).resolve().parent.parent.parent / "ProjectDocs" / "Playbook.md"


def get_playbook_content() -> str:
    """Return the full Collegiate Menu & Station Playbook text, or empty string if not found."""
    if not _PLAYBOOK_PATH.exists():
        return ""
    return _PLAYBOOK_PATH.read_text(encoding="utf-8").strip()


def get_playbook_section() -> str:
    """Return the playbook wrapped in a section tag for inclusion in system prompts."""
    content = get_playbook_content()
    if not content:
        return ""
    return "\n\n<organization_playbook>\nThe following is the organization compliance playbook. Use it as the authoritative reference for menu analysis and compliance reporting. All findings and recommendations must align with these standards.\n\n" + content + "\n</organization_playbook>"


def _read_prompt(agent_slug: str) -> str:
    path = _AGENTS_DIR / agent_slug / "system_prompt.txt"
    return path.read_text().strip()


def _prompt_with_playbook(agent_slug: str) -> str:
    return _read_prompt(agent_slug) + get_playbook_section()


def get_orchestrator_prompt() -> str:
    return _prompt_with_playbook("orchestrator")


def get_menu_structure_prompt() -> str:
    return _prompt_with_playbook("menu_structure")


def get_data_integrity_prompt() -> str:
    return _prompt_with_playbook("data_integrity")


def get_rotation_recurrence_prompt() -> str:
    return _prompt_with_playbook("rotation_recurrence")


def get_nutrition_cost_prompt() -> str:
    return _prompt_with_playbook("nutrition_cost")


def get_synthesizer_prompt() -> str:
    return _prompt_with_playbook("synthesizer")
