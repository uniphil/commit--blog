#!/usr/bin/env python3
from pathlib import Path


workers = 2
preload_app = True
bind = 'unix:/tmp/caddy.sock'


def when_ready(_server):
    Path('/tmp/app-initialized').touch()
