"""Run Django's manage commands with eventlet monkey-patched first.

eventlet has no launcher like ``python -m gevent.monkey``, so the eventlet tox
envs run ``python -m tests.eventlet_main test ...``, which coverage can
wrap, unlike ``python -c``.
"""

import eventlet

eventlet.monkey_patch()

import runpy  # noqa: E402

runpy.run_module("django", run_name="__main__", alter_sys=True)
