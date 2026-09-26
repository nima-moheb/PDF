from . import engine as _engine
from .visual_v05 import install as _install_visual_v05
from .visual_v06 import install as _install_visual_v06
from .delivery_v061 import install as _install_delivery_v061
from .visual_v062 import install as _install_visual_v062

_install_visual_v05()
_install_visual_v06()
_install_delivery_v061()
_install_visual_v062()

build = _engine.build

__all__ = ["build"]
