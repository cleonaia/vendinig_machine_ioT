from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scenarios.run_all import run_normal, run_replay


if __name__ == '__main__':
    print('Demo flujo normal:', run_normal())
    print('Demo replay bloqueado:', run_replay())
