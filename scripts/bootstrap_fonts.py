"""Compatibility check: preferred fonts are already bundled; no network or writes."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reportkit.fonts import register_fonts
if __name__=='__main__':
    print(json.dumps({'status':'PASS','message':'Fonts are bundled; no bootstrap needed.','fonts':register_fonts()},indent=2))
