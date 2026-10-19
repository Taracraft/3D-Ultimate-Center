"""Read a private local installer seed; never return its secret to the frontend."""
import json
from pathlib import Path
import os
import stat
import uuid

SEED_NAME = '.ultimate-3d-studio-setup.json'
LEGACY_SEED_NAME = '.taracraft-studio-setup.json'

def read_setup_seed(config_dir):
    path = Path(config_dir) / SEED_NAME
    if not path.exists() and not path.is_symlink():
        path = Path(config_dir) / LEGACY_SEED_NAME
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 8192
                or info.st_mode & 0o077 or info.st_uid not in {0, os.geteuid()}):
            return {}
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as source:
            actual = os.fstat(source.fileno())
            if (actual.st_ino, actual.st_dev) != (info.st_ino, info.st_dev):
                return {}
            value = json.loads(source.read(8193))
        if (not isinstance(value, dict) or value.get('schema') != 1
                or set(value) != {'schema','session','slicer_base_url','slicer_api_secret'}):
            return {}
        uuid.UUID(value['session'])
        from .slicer_connection_settings import normalize_slicer_base_url, validate_slicer_api_secret
        return {'slicer_enabled': True,
                'slicer_base_url': normalize_slicer_base_url(value['slicer_base_url']),
                'slicer_api_secret': validate_slicer_api_secret(value['slicer_api_secret'])}
    except (OSError, ValueError, TypeError, KeyError):
        return {}
