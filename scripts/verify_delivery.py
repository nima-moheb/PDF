"""Compatibility command; the CLI also verifies the accepted build/QA receipts."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reportkit.cli import main
if __name__=='__main__':
    raise SystemExit(main(['verify',*sys.argv[1:]]))
