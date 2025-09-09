from __future__ import annotations

"""Template snippets and tips to guide Manim code generation.

Agents can use these strings as scaffolding when producing code.
"""

MANIM_TIPS = """
Key Manim tips:
- Define a class deriving from `Scene` and implement `construct(self)`.
- Use primitives like `Circle`, `Square`, `Text`, `MathTex` and animations like `Create`, `Transform`, `FadeOut`.
- Use `self.play(...)` to run animations and `self.add(...)` to add static objects.
- Do not use star imports. Import only the names you use, e.g.:
  `from manim import Scene, Text, MathTex, Create, Transform, FadeOut, BLUE`.
- Prefer medium or low quality for quick renders: `-qm` or `-ql`.
""".strip()


def default_manim_skeleton(scene_name: str = "GeneratedScene") -> str:
    """Return a minimal, valid Manim script using Pydantic for parameters.

    The generator agent should replace placeholder content, keep the shape, and
    ensure the scene class matches `scene_name` exactly.
    """
    return f"""from __future__ import annotations
from pydantic import BaseModel, Field
from manim import Scene, Text, Create, FadeOut, BLUE


class SceneConfig(BaseModel):
    title: str = Field(default="Untitled", description="Title text to display")
    primary_color: str = Field(default="BLUE", description="Color name constant")
    seconds: float = Field(default=3.0, description="Total approximate duration")


class {scene_name}(Scene):
    def __init__(self, config: SceneConfig | None = None, **kwargs):
        super().__init__(**kwargs)
        self.cfg = config or SceneConfig()

    def construct(self):
        # Example: simple animated title
        title = Text(self.cfg.title)
        title.set_color(globals().get(self.cfg.primary_color, BLUE))
        self.play(Create(title))
        self.wait(self.cfg.seconds)
        self.play(FadeOut(title))
"""
