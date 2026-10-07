import os
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings


if __name__ == '__main__':
    if os.path.exists(settings.sqlite_path):
        os.remove(settings.sqlite_path)
        print(f'Eliminado {settings.sqlite_path}')
    else:
        print('No hay base SQLite para limpiar')
