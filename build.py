"""Backward-compatible build command. Prefer python -m reportkit for new work."""
import sys
from reportkit.cli import main
if __name__=='__main__':
    args=['--preview' if x=='--no-qa' else x for x in sys.argv[1:]]
    raise SystemExit(main(['build',*args]))
