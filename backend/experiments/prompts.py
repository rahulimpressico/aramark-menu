"""
Load system prompts from agent folders and the organization playbook.
Every agent receives the playbook so analysis is done against organisation compliance.
Each agent also receives its SKILLS.md so the agent uses the defined skills when executing.
"""
from pathlib import Path
from experiments.log_config import log

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
    return "\n\n<organization_playbook>\nThe following is the organisation compliance playbook. Use it as the authority when analysing menus.\n\n" + content + "\n</organization_playbook>"


def _read_prompt(agent_slug: str) -> str:
    path = _AGENTS_DIR / agent_slug / "system_prompt.txt"
    return path.read_text().strip()


def _read_skills(agent_slug: str) -> str:
    """Return the contents of SKILLS.md for the agent, or empty string if not found."""
    path = _AGENTS_DIR / agent_slug / "SKILLS.md"
    if not path.exists():
        log.warning("SKILLS.md not found for agent {}", agent_slug)
        return ""
    return path.read_text(encoding="utf-8").strip()


def _skills_section(agent_slug: str) -> str:
    """Return the skills section for inclusion in system prompts."""
    content = _read_skills(agent_slug)
    if not content:
        log.warning("SKILLS.md not found for agent {}", agent_slug)
        return ""
    return "\n\n<skills>\nUse these skills when planning and executing:\n\n" + content + "\n</skills>"


def _prompt_with_playbook(agent_slug: str) -> str:
    """System prompt + skills + playbook so the agent uses SKILLS.md when getting work done."""
    return _read_prompt(agent_slug) + _skills_section(agent_slug) + get_playbook_section()


def get_orchestrator_prompt() -> str:
    return _prompt_with_playbook("orchestrator")


def get_operator_prompt() -> str:
    return _prompt_with_playbook("operator")


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
