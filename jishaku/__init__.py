# -*- coding: utf-8 -*-

"""
jishaku
~~~~~~~

A discord.py extension including useful tools for bot development and debugging.

:copyright: (c) 2024 Devon (scarletcafe) R
:license: MIT, see LICENSE for more details.

"""

from jishaku.cog import Jishaku, STANDARD_FEATURES, OPTIONAL_FEATURES, setup
from jishaku.features.baseclass import Feature
from jishaku.flags import Flags
from jishaku.meta import *  # noqa: F403

from discord.ext import commands


def _walk_all_commands(bot: commands.Bot):
    """Walk all commands recursively including subcommands."""
    def _recurse(cmd):
        yield cmd
        if isinstance(cmd, commands.Group):
            for sub in cmd.commands:
                yield from _recurse(sub)

    for cmd in bot.commands:
        yield from _recurse(cmd)


class _CommandCountProxy:
    """
    Proxy wrapping bot.commands that returns walk_commands() length for len().
    This makes len(bot.commands) count subcommands, while iteration still returns top-level.
    """
    def __init__(self, real_set, bot):
        self._real = real_set
        self._bot = bot

    def __len__(self):
        return sum(1 for _ in self._bot.walk_commands())

    def __iter__(self):
        return iter(self._real)

    def __contains__(self, item):
        return item in self._real

    def __repr__(self):
        return repr(self._real)


_orig_commands_fget = commands.Bot.commands.fget


def _patched_commands_fget(self):
    return _CommandCountProxy(_orig_commands_fget(self), self)


commands.Bot.commands = property(_patched_commands_fget)

__all__ = (
    'Jishaku',
    'Feature',
    'Flags',
    'STANDARD_FEATURES',
    'OPTIONAL_FEATURES',
    'setup',
)

