# -*- coding: utf-8 -*-

"""
jishaku.features.baseclass
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The base Feature class that serves as the superclass of all feature components.

:copyright: (c) 2021 Devon (scarletcafe) R
:license: MIT, see LICENSE for more details.

"""

import asyncio
import collections
import contextlib
import typing
from datetime import datetime, timezone

from discord.ext import commands
from typing_extensions import Concatenate, ParamSpec

import os
import discord

from jishaku.types import BotT, ContextA

__all__ = (
    'Feature',
    'CommandTask',
    'JishakuComponentV2'
)


class JishakuComponentV2(discord.ui.LayoutView):
    def __init__(self, cog: 'Feature', ctx: ContextA, content: str, timeout: float = 600.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx

        container = discord.ui.Container(accent_color=5793266)
        if content:
            container.add_item(discord.ui.TextDisplay(content))

        # Determine which buttons are necessary based on the command name
        cmd_name = ctx.command.name if ctx.command else ""
        show_rerun = cmd_name in ("py", "python", "sh", "shell", "sql", "git", "calc")
        show_cancel = cmd_name in ("py", "python", "sh", "shell", "sql", "git")

        # Only add a separator if there is visible content above
        if content:
            container.add_item(discord.ui.Separator())

        action_row = discord.ui.ActionRow()

        btn_dismiss = discord.ui.Button(label="Dismiss", style=discord.ButtonStyle.danger)
        btn_dismiss.callback = self.dismiss
        action_row.add_item(btn_dismiss)

        if show_rerun:
            btn_rerun = discord.ui.Button(label="Rerun", style=discord.ButtonStyle.primary)
            btn_rerun.callback = self.rerun_command
            action_row.add_item(btn_rerun)

        if show_cancel:
            btn_cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
            btn_cancel.callback = self.cancel_task
            action_row.add_item(btn_cancel)

        container.add_item(action_row)
        self.add_item(container)

    async def dismiss(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass

    async def rerun_command(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer()
        try:
            message = await self.ctx.channel.fetch_message(self.ctx.message.id)
            self.ctx.message = message
        except Exception:
            pass

        await self.ctx.reinvoke()

    async def cancel_task(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        task = None
        for t in self.cog.tasks:
            if t.ctx.message.id == self.ctx.message.id:
                task = t
                break

        if task and task.task:
            task.task.cancel()
            await interaction.response.send_message("Task cancelled successfully.", ephemeral=True)
        else:
            await interaction.response.send_message("No active task found for this command.", ephemeral=True)

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        is_allowed = (interaction.user.id == self.ctx.author.id)
        if not is_allowed:
            allowed_users = getattr(interaction.client, 'jishaku_allowed_users', set())
            if interaction.user.id in allowed_users or await interaction.client.is_owner(interaction.user):
                is_allowed = True

        if not is_allowed:
            await interaction.response.send_message("You do not have permission to control this Jishaku instance.", ephemeral=True)
            return False
        return True


_ConvertedCommand = commands.Command['Feature', typing.Any, typing.Any]
_ConvertedGroup = commands.Group['Feature', typing.Any, typing.Any]


_FeatureCommandToCommand = typing.Callable[
    ...,
    typing.Callable[
        [typing.Callable[..., typing.Any]],
        _ConvertedCommand
    ]
]
_FeatureCommandToGroup = typing.Callable[
    ...,
    typing.Callable[
        [typing.Callable[..., typing.Any]],
        _ConvertedGroup
    ]
]

T = typing.TypeVar('T')
P = ParamSpec('P')
GenericFeature = typing.TypeVar('GenericFeature', bound='Feature')


class CommandTask(typing.NamedTuple):
    """
    A running Jishaku task, wrapping asyncio.Task
    """

    index: int  # type: ignore
    ctx: ContextA
    task: typing.Optional['asyncio.Task[typing.Any]']


class Feature(commands.Cog):
    """
    Baseclass defining feature components of the jishaku cog.
    """

    class Command(typing.Generic[GenericFeature, P, T]):  # pylint: disable=too-few-public-methods
        """
        An intermediary class for Feature commands.
        Instances of this class will be converted into commands.Command or commands.Group instances when inside a Feature.

        :param parent: What this command should be parented to.
        :param standalone_ok: Whether the command should be allowed to be standalone if its parent isn't found.
        """

        def __init__(
            self,
            parent: typing.Optional[str] = None,
            standalone_ok: bool = False,
            **kwargs: typing.Any
        ):
            self.parent: typing.Optional[str] = parent
            self.parent_instance: typing.Optional[Feature.Command[GenericFeature, typing.Any, typing.Any]] = None
            self.standalone_ok = standalone_ok
            self.kwargs = kwargs
            self.callback: typing.Optional[
                typing.Callable[
                    Concatenate[GenericFeature, ContextA, P],
                    typing.Coroutine[typing.Any, typing.Any, T]
                ]
            ] = None
            self.depth: int = 0
            self.has_children: bool = False

        def __call__(
            self,
            callback: typing.Callable[
                ...,
                # This causes a weird pyright bug right now
                # Concatenate[GenericFeature, ContextA, P],
                typing.Coroutine[typing.Any, typing.Any, T]
            ]
        ):
            self.callback = callback  # type: ignore
            return self

        def convert(
            self,
            association_map: typing.Dict[
                'Feature.Command[GenericFeature, typing.Any, typing.Any]',
                'commands.Command[GenericFeature, typing.Any, typing.Any]',
            ]
        ) -> 'commands.Command[GenericFeature, P, T]':
            """
            Attempts to convert this Feature.Command into either a commands.Command or commands.Group
            """

            if self.parent:
                if not self.parent_instance:
                    raise RuntimeError("A Features.Command declared as having a parent was attempted to be converted before its parent was")

                parent = association_map[self.parent_instance]

                if not isinstance(parent, commands.Group):
                    raise RuntimeError("A Features.Command declared as a parent was associated with a non-commands.Group")

                command_type = parent.group if self.has_children else parent.command
            else:
                command_type = commands.group if self.has_children else commands.command

            if not self.callback:
                raise RuntimeError("A Features.Command lacked a callback at the time it was attempted to be converted")

            return command_type(**self.kwargs)(self.callback)

    load_time: datetime = datetime.now(timezone.utc)

    def __init__(self, *args: typing.Any, **kwargs: typing.Any):
        self.bot: BotT = kwargs.pop('bot')
        if not hasattr(self.bot, 'jishaku_allowed_users'):
            self.bot.jishaku_allowed_users = set()
            env_allowed = os.getenv("JISHAKU_ALLOWED_USERS")
            if env_allowed:
                for item in env_allowed.split(','):
                    item = item.strip()
                    if item.isdigit():
                        self.bot.jishaku_allowed_users.add(int(item))
        self.start_time: datetime = datetime.now(timezone.utc)
        self.tasks: typing.Deque[CommandTask] = collections.deque()
        self.task_count: int = 0

        # Generate and attach commands
        command_lookup: typing.Dict[str, Feature.Command['Feature', typing.Any, typing.Any]] = {}

        for kls in reversed(type(self).__mro__):
            for key, cmd in kls.__dict__.items():
                if isinstance(cmd, Feature.Command):
                    command_lookup[key] = cmd  # type: ignore

        command_set = list(command_lookup.items())

        # Try to associate every parented command with its parent
        for key, cmd in command_set:
            cmd.parent_instance = None
            cmd.depth = 0

            if cmd.parent and isinstance(cmd.parent, str):  # type: ignore
                if cmd.standalone_ok:
                    cmd.parent_instance = command_lookup.get(cmd.parent, None)
                else:
                    try:
                        cmd.parent_instance = command_lookup[cmd.parent]
                    except KeyError as exception:
                        raise RuntimeError(
                            f"Couldn't associate feature command {key} with its parent {cmd.parent}"
                        ) from exception
            # Also raise if any command lacks a callback
            if cmd.callback is None:
                raise RuntimeError(f"Feature command {key} lacks callback")

        # Assign depth and has_children
        for key, cmd in command_set:
            parent = cmd.parent_instance
            # Recurse parents increasing depth until we reach the top
            while parent:
                parent.has_children = True
                cmd.depth += 1
                parent = parent.parent_instance

        # Sort by depth
        command_set.sort(key=lambda c: c[1].depth)
        association_map: typing.Dict[
            Feature.Command['Feature', typing.Any, typing.Any],
            commands.Command['Feature', typing.Any, typing.Any]
        ] = {}

        self.feature_commands: typing.Dict[
            str,
            commands.Command['Feature', typing.Any, typing.Any]
        ] = {}

        for key, cmd in command_set:
            association_map[cmd] = target_cmd = cmd.convert(association_map)
            target_cmd.cog = self
            self.feature_commands[key] = target_cmd
            setattr(self, key, target_cmd)

        # pylint: disable=protected-access, access-member-before-definition
        self.__cog_commands__ = [*self.__cog_commands__, *self.feature_commands.values()]
        # pylint: enable=protected-access, access-member-before-definition

        # Don't really think this does much, but init Cog anyway.
        super().__init__(*args, **kwargs)

    # Ignored because this gets incorrectly clocked as a sync override
    async def cog_check(self, ctx: ContextA):  # type: ignore  # pylint: disable=invalid-overridden-method
        """
        Local check, makes all commands in resulting cogs owner-only or allowed users
        """
        allowed_users = getattr(ctx.bot, 'jishaku_allowed_users', set())
        if ctx.author.id in allowed_users or await ctx.bot.is_owner(ctx.author):
            return True
        raise commands.NotOwner("You do not have permission to use Jishaku.")

    async def cog_before_invoke(self, ctx: ContextA):
        """
        Hook before invoking commands to wrap ctx.send
        """
        original_send = ctx.send

        async def custom_send(*args: typing.Any, **kwargs: typing.Any):
            content = kwargs.pop("content", None)
            if not content and args:
                content = args[0]
                args = args[1:]
            else:
                content = ""

            if not kwargs.get("view"):
                kwargs["view"] = JishakuComponentV2(self, ctx, str(content))
            elif content:
                kwargs["content"] = content

            return await original_send(*args, **kwargs)

        ctx.send = custom_send

    @contextlib.contextmanager
    def submit(self, ctx: ContextA):
        """
        A context-manager that submits the current task to jishaku's task list
        and removes it afterwards.

        Parameters
        -----------
        ctx: commands.Context
            A Context object used to derive information about this command task.
        """

        self.task_count += 1

        try:
            current_task = asyncio.current_task()  # pylint: disable=no-member
        except RuntimeError:
            # asyncio.current_task doesn't document that it can raise RuntimeError, but it does.
            # It propagates from asyncio.get_running_loop(), so it happens when there is no loop running.
            # It's unclear if this is a regression or an intentional change, since in 3.6,
            #  asyncio.Task.current_task() would have just returned None in this case.
            current_task = None

        cmdtask = CommandTask(self.task_count, ctx, current_task)

        self.tasks.append(cmdtask)

        try:
            yield cmdtask
        finally:
            if cmdtask in self.tasks:
                self.tasks.remove(cmdtask)
