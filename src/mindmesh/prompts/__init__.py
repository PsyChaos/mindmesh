"""Prompt template loader for MindMesh."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from mindmesh.schemas import Message

_PROMPTS_DIR = Path(__file__).parent
_SEPARATOR = "---USER---"
_SYSTEM_MARKER = "---SYSTEM---"


class PromptLoader:
    """Loads and renders Jinja2 prompt templates into Message lists.

    If custom_dir is provided and contains the requested template,
    it is used. Otherwise falls back to built-in templates.
    """

    def __init__(
        self,
        prompts_dir: Path = _PROMPTS_DIR,
        custom_dir: Path | None = None,
    ) -> None:
        self._builtin_dir = prompts_dir
        self._custom_dir = custom_dir
        search_path = [str(custom_dir), str(prompts_dir)] if custom_dir else [str(prompts_dir)]
        self._env = Environment(
            loader=FileSystemLoader(search_path),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def load(self, template_name: str, **kwargs: object) -> list[Message]:
        """Render a prompt template and return [system_message, user_message].

        Raises FileNotFoundError if the template does not exist.
        """
        filename = f"{template_name}.md"
        resolved = self._resolve(filename)
        if resolved is None:
            raise FileNotFoundError(
                f"Prompt template not found: {filename}"
            )

        template = self._env.get_template(filename)
        rendered = template.render(**kwargs)

        system_content, user_content = self._split(rendered)
        return [
            Message(role="system", content=system_content.strip()),
            Message(role="user", content=user_content.strip()),
        ]

    def _resolve(self, filename: str) -> Path | None:
        if self._custom_dir and (self._custom_dir / filename).exists():
            return self._custom_dir / filename
        builtin = self._builtin_dir / filename
        return builtin if builtin.exists() else None

    def _split(self, rendered: str) -> tuple[str, str]:
        system_content = rendered
        if _SYSTEM_MARKER in system_content:
            system_content = system_content.split(_SYSTEM_MARKER, 1)[1]

        if _SEPARATOR not in system_content:
            return system_content, ""

        system_part, user_part = system_content.split(_SEPARATOR, 1)
        return system_part, user_part
