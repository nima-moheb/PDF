"""Public report compiler. Presentation is installed once; builds use one pipeline."""
from . import engine as _engine
from .visual_v05 import install as _v05
from .visual_v06 import install as _v06
from .visual_v062 import install as _v062
_v05()
_v06()
_v062()
from .presentation import install as _presentation
_presentation()
from .pipeline import build, ENGINE_VERSION
from .fonts import register_fonts
_engine.ENGINE_VERSION = ENGINE_VERSION
_engine.register_fonts = register_fonts
_engine.build = build
__version__ = ENGINE_VERSION
__all__ = ['build', '__version__']
