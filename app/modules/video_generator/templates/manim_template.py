from __future__ import annotations

"""Template snippets and tips to guide Manim code generation.

Agents can use these strings as scaffolding when producing code.
"""

MANIM_TIPS = """
🎯 ESSENTIAL MANIM FUNDAMENTALS:
- Define a class deriving from `Scene` and implement `construct(self)` method
- Use `self.play(...)` to run animations and `self.add(...)` to add static objects
- Always use explicit imports: `from manim import Scene, Text, MathTex, Create, Transform, FadeOut, BLUE, PI`
- NEVER use star imports (`from manim import *`) - this causes linting errors
- Prefer medium or low quality for quick renders: `-qm` or `-ql`

🎨 VISUAL PRIMITIVES & OBJECTS:
- Basic shapes: `Circle`, `Square`, `Rectangle`, `Triangle`, `Polygon`, `Line`, `Arrow`
- Text elements: `Text`, `MathTex`, `Tex`, `MarkupText` for different formatting needs
- Mathematical: `NumberLine`, `Axes`, `Graph`, `FunctionGraph` for mathematical visualizations
- 3D objects: `Sphere`, `Cube`, `Cone`, `Cylinder` for three-dimensional content
- Custom shapes: Use `VMobject` and `SVGMobject` for complex geometries

✨ ANIMATION TECHNIQUES:
- Creation: `Create`, `Write`, `DrawBorderThenFill` for different drawing styles
- Transitions: `Transform`, `ReplacementTransform`, `FadeTransform` for smooth changes
- Movement: `MoveToTarget`, `Shift`, `Rotate`, `Scale` for object manipulation
- Visibility: `FadeIn`, `FadeOut`, `ShowCreation`, `Uncreate` for appearance control
- Timing: `self.wait(duration)` for pauses, `rate_func` for custom timing curves

🌈 COLOR & STYLING:
- Predefined colors: `BLUE`, `RED`, `GREEN`, `YELLOW`, `PURPLE`, `ORANGE`, `PINK`, `GRAY`
- Custom colors: `color=rgb_to_color([r, g, b])` or `color="#hexcode"`
- Text styling: `.set_color()`, `.set_font_size()`, `.set_font()`
- Object styling: `.set_fill()`, `.set_stroke()`, `.set_opacity()`

📐 POSITIONING & LAYOUT:
- Positioning: `.move_to()`, `.shift()`, `.next_to()`, `.align_to()`
- Alignment: `UP`, `DOWN`, `LEFT`, `RIGHT`, `ORIGIN` for directional constants
- Grouping: `VGroup`, `HGroup` for organizing multiple objects
- Spacing: Use `buff` parameter for consistent spacing between objects

🎬 SCENE MANAGEMENT:
- Clear screen: `self.clear()` to remove all objects
- Camera control: `self.camera.frame` for zooming and positioning
- Background: `self.camera.background_color` for scene background
- Resolution: Configure quality settings for optimal rendering speed

⚡ PERFORMANCE OPTIMIZATION:
- Use `-ql` (low quality) for rapid iteration and testing
- Use `-qm` (medium quality) for final renders
- Avoid excessive object creation in loops
- Use `VGroup` to animate multiple objects efficiently
- Consider using `rate_func=linear` for consistent timing

🔧 ADVANCED FEATURES:
- ValueTracker: For smooth parameter animations over time
- Custom animations: Inherit from `Animation` class for specialized effects
- Interactive elements: Use `ValueTracker` with `Updater` for dynamic content
- Mathematical functions: Leverage `np.sin`, `np.cos`, `np.exp` for smooth curves
- Graph visualizations: Use `Graph` and `Network` for complex data structures

📚 EDUCATIONAL BEST PRACTICES:
- Start simple and build complexity gradually
- Use consistent color coding throughout the animation
- Include pauses (`self.wait()`) for comprehension
- Group related concepts visually with `VGroup`
- Use arrows and highlights to guide attention
- Provide clear visual hierarchy with size and color

🚨 COMMON PITFALLS TO AVOID:
- Don't use star imports - always import explicitly
- Don't forget to call `self.wait()` between major sections
- Don't overcrowd the screen - use `self.clear()` between concepts
- Don't use decimal approximations for mathematical constants (use `PI`, `TAU`, `E`)
- Don't create objects inside loops without proper cleanup
- Don't forget to scale text appropriately for readability
""".strip()


def default_manim_skeleton(scene_name: str = "GeneratedScene") -> str:
    """Return a comprehensive, well-structured Manim script template.

    The generator agent should replace placeholder content, keep the structure, and
    ensure the scene class matches `scene_name` exactly. This template provides
    a solid foundation for educational animations with proper organization.
    """
    # Define the axis config separately to avoid f-string issues
    axis_config = '{"color": "GRAY", "stroke_width": 1}'
    
    return f"""from __future__ import annotations
from pydantic import BaseModel, Field
from manim import (
    Scene, Text, MathTex, Create, FadeIn, FadeOut, Transform, 
    BLUE, GREEN, RED, YELLOW, WHITE, PI, TAU, UP, DOWN, LEFT, RIGHT, ORIGIN,
    VGroup, Circle, Square, Arrow, NumberLine, Axes
)


class SceneConfig(BaseModel):
    \"\"\"Configuration parameters for the animation scene.\"\"\"
    title: str = Field(default="Educational Animation", description="Main title text")
    subtitle: str = Field(default="", description="Optional subtitle")
    primary_color: str = Field(default="BLUE", description="Primary color constant")
    secondary_color: str = Field(default="GREEN", description="Secondary color constant")
    accent_color: str = Field(default="RED", description="Accent color for highlights")
    duration: float = Field(default=5.0, description="Total animation duration")
    font_size: int = Field(default=48, description="Title font size")
    show_grid: bool = Field(default=False, description="Whether to show background grid")


class {scene_name}(Scene):
    \"\"\"Educational animation scene with configurable parameters.\"\"\"
    
    def __init__(self, config: SceneConfig | None = None, **kwargs):
        super().__init__(**kwargs)
        self.cfg = config or SceneConfig()
        self.objects = VGroup()  # Track all created objects for cleanup
    
    def construct(self):
        \"\"\"Main animation sequence.\"\"\"
        # Setup phase
        self.setup_scene()
        
        # Main content phase
        self.create_title()
        self.create_content()
        
        # Conclusion phase
        self.conclude_scene()
    
    def setup_scene(self):
        \"\"\"Initialize the scene with background and setup.\"\"\"
        if self.cfg.show_grid:
            # Add a subtle grid for reference
            grid = Axes(
                x_range=[-7, 7, 1],
                y_range=[-4, 4, 1],
                x_length=14,
                y_length=8,
                axis_config={axis_config}
            )
            grid.set_opacity(0.3)
            self.add(grid)
            self.objects.add(grid)
    
    def create_title(self):
        \"\"\"Create and animate the title sequence.\"\"\"
        # Main title
        title = Text(self.cfg.title, font_size=self.cfg.font_size)
        title.set_color(globals().get(self.cfg.primary_color, BLUE))
        title.move_to(UP * 2)
        
        # Subtitle (if provided)
        subtitle = None
        if self.cfg.subtitle:
            subtitle = Text(self.cfg.subtitle, font_size=36)
            subtitle.set_color(globals().get(self.cfg.secondary_color, GREEN))
            subtitle.next_to(title, DOWN, buff=0.5)
        
        # Animate title sequence
        self.play(FadeIn(title))
        if subtitle:
            self.play(FadeIn(subtitle))
        
        self.wait(1)
        
        # Store objects for cleanup
        self.objects.add(title)
        if subtitle:
            self.objects.add(subtitle)
    
    def create_content(self):
        \"\"\"Create the main educational content.\"\"\"
        # Example: Simple mathematical concept visualization
        # Replace this section with the actual educational content
        
        # Create a circle to demonstrate concepts
        circle = Circle(radius=1.5)
        circle.set_color(globals().get(self.cfg.primary_color, BLUE))
        circle.move_to(ORIGIN)
        
        # Add mathematical annotation
        equation = MathTex(r"x^2 + y^2 = r^2")
        equation.set_color(globals().get(self.cfg.accent_color, RED))
        equation.next_to(circle, DOWN, buff=1)
        
        # Animate the content
        self.play(Create(circle))
        self.play(FadeIn(equation))
        self.wait(2)
        
        # Store objects
        self.objects.add(circle, equation)
    
    def conclude_scene(self):
        \"\"\"Conclude the animation with cleanup.\"\"\"
        # Fade out all objects
        if self.objects:
            self.play(FadeOut(self.objects))
        
        # Final pause
        self.wait(0.5)
    
    def cleanup(self):
        \"\"\"Clean up any remaining objects.\"\"\"
        self.clear()
"""
