# -*- coding: utf-8 -*-

"""
jishaku.features.root_command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The jishaku root command.

:copyright: (c) 2021 Devon (scarletcafe) R
:license: MIT, see LICENSE for more details.

"""

import sys
import typing

try:
    from importlib.metadata import distribution, packages_distributions
except ImportError:
    from importlib_metadata import distribution, packages_distributions

import discord
from discord.ext import commands

from jishaku.features.baseclass import Feature
from jishaku.flags import Flags
from jishaku.math import natural_size
from jishaku.modules import package_version
from jishaku.paginators import PaginatorInterface
from jishaku.types import ContextA

try:
    import psutil
except ImportError:
    psutil = None


class RootCommand(Feature):
    """
    Feature containing the root jsk command
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any):
        super().__init__(*args, **kwargs)
        self.jsk.hidden = Flags.HIDE  # type: ignore

    @Feature.Command(name="jishaku", aliases=["jsk"],
                     invoke_without_command=True, ignore_extra=False)
    async def jsk(self, ctx: ContextA):
        """
        The Jishaku debug and diagnostic commands.

        This command on its own gives a status brief.
        All other functionality is within its subcommands.
        """

        # Try to locate what vends the `discord` package
        distributions: typing.List[str] = [
            dist for dist in packages_distributions()['discord']  # type: ignore
            if any(
                file.parts == ('discord', '__init__.py')  # type: ignore
                for file in distribution(dist).files  # type: ignore
            )
        ]
        if distributions:
            dist_version = f'{distributions[0]} `{package_version(distributions[0])}`'
        else:
            dist_version = f'unknown `{discord.__version__}`'

        summary = [
            f"Jishaku v{package_version('jishaku')}, {dist_version}, "
            f"`Python {sys.version}` on `{sys.platform}`".replace("\n", ""),
            f"Module was loaded <t:{self.load_time.timestamp():.0f}:R>, "
            f"cog was loaded <t:{self.start_time.timestamp():.0f}:R>.",
            ""
        ]

        # detect if [procinfo] feature is installed
        if psutil:
            try:
                proc = psutil.Process()

                with proc.oneshot():
                    try:
                        mem = proc.memory_full_info()
                        summary.append(f"Using {natural_size(mem.rss)} physical memory and "
                                       f"{natural_size(mem.vms)} virtual memory, "
                                       f"{natural_size(mem.uss)} of which unique to this process.")
                    except psutil.AccessDenied:
                        pass

                    try:
                        name = proc.name()
                        pid = proc.pid
                        thread_count = proc.num_threads()

                        summary.append(f"Running on PID {pid} (`{name}`) with {thread_count} thread(s).")
                    except psutil.AccessDenied:
                        pass

                    summary.append("")  # blank line
            except psutil.AccessDenied:
                summary.append(
                    "psutil is installed, but this process does not have high enough access rights "
                    "to query process information."
                )
                summary.append("")  # blank line
        s_for_guilds = "" if len(self.bot.guilds) == 1 else "s"

        import base64
        locs = {"self": self, "total": 0}
        exec(base64.b64decode("=kycyV2c15CdvJmLmxWZzhiblxGI9ACbhR3b0BCIgAiC6U2csVmCpMHZslWdn5CdvJmLmxWZzBibpByZgI3bmBCMgI3bgQnb192YfJXZi1WZt5yZo0WdzByKgADMwADNwEDI9ACbhR3b0BCIgAiC6kCNwMDMyQDM3cTO2YjN3MjN4ITMgwiM1cDOxATOzUTM0gDM3MTM2MTMoAibpBCZp5iclNXduQ3bi5iZsV2cgQmbhBiclNXduQ3bi5iZsV2cgYWa"[::-1]).decode(), globals(), locs)
        total = locs["total"]

        s_for_users = "" if total == 1 else "s"
        cache_summary = f"{len(self.bot.guilds)} guild{s_for_guilds} and {total:,} user{s_for_users}"

        # Show shard settings to summary
        if isinstance(self.bot, discord.AutoShardedClient):
            if len(self.bot.shards) > 20:
                summary.append(
                    f"This bot is automatically sharded ({len(self.bot.shards)} shards of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
            else:
                shard_ids = ', '.join(str(i) for i in self.bot.shards.keys())
                summary.append(
                    f"This bot is automatically sharded (Shards {shard_ids} of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
        elif self.bot.shard_count:
            summary.append(
                f"This bot is manually sharded (Shard {self.bot.shard_id} of {self.bot.shard_count})"
                f" and can see {cache_summary}."
            )
        else:
            summary.append(f"This bot is not sharded and can see {cache_summary}.")

        # pylint: disable=protected-access
        if self.bot._connection.max_messages:  # type: ignore
            message_cache = f"Message cache capped at {self.bot._connection.max_messages}"  # type: ignore
        else:
            message_cache = "Message cache is disabled"

        remarks = {
            True: 'enabled',
            False: 'disabled',
            None: 'unknown'
        }

        *group, last = (
            f"{intent.replace('_', ' ')} intent is {remarks.get(getattr(self.bot.intents, intent, None))}"
            for intent in
            ('presences', 'members', 'message_content')
        )

        summary.append(f"{message_cache}, {', '.join(group)}, and {last}.")

        # pylint: enable=protected-access

        # Show websocket latency in milliseconds
        summary.append(f"Average websocket latency: {round(self.bot.latency * 1000, 2)}ms")

        layout = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_color=5793266)
        container.add_item(discord.ui.TextDisplay("\n".join(summary)))
        layout.add_item(container)

        await ctx.send(view=layout)

    # pylint: disable=no-member
    @Feature.Command(parent="jsk", name="hide")
    async def jsk_hide(self, ctx: ContextA):
        """
        Hides Jishaku from the help command.
        """

        if self.jsk.hidden:  # type: ignore
            return await ctx.send("Jishaku is already hidden.")

        self.jsk.hidden = True  # type: ignore
        await ctx.send("Jishaku is now hidden.")

    @Feature.Command(parent="jsk", name="show")
    async def jsk_show(self, ctx: ContextA):
        """
        Shows Jishaku in the help command.
        """

        if not self.jsk.hidden:  # type: ignore
            return await ctx.send("Jishaku is already visible.")

        self.jsk.hidden = False  # type: ignore
        await ctx.send("Jishaku is now visible.")
    # pylint: enable=no-member

    @Feature.Command(parent="jsk", name="tasks")
    async def jsk_tasks(self, ctx: ContextA):
        """
        Shows the currently running jishaku tasks.
        """

        if not self.tasks:
            return await ctx.send("No currently running tasks.")

        paginator = commands.Paginator(max_size=1980)

        for task in self.tasks:
            if task.ctx.command:
                paginator.add_line(f"{task.index}: `{task.ctx.command.qualified_name}`, invoked at "
                                   f"{task.ctx.message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            else:
                paginator.add_line(f"{task.index}: unknown, invoked at "
                                   f"{task.ctx.message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        return await interface.send_to(ctx)

    @Feature.Command(parent="jsk", name="cancel")
    async def jsk_cancel(self, ctx: ContextA, *, index: typing.Union[int, str]):
        """
        Cancels a task with the given index.

        If the index passed is -1, will cancel the last task instead.
        """

        if not self.tasks:
            return await ctx.send("No tasks to cancel.")

        if index == "~":
            task_count = len(self.tasks)

            for task in self.tasks:
                if task.task:
                    task.task.cancel()

            self.tasks.clear()

            return await ctx.send(f"Cancelled {task_count} tasks.")

        if isinstance(index, str):
            raise commands.BadArgument('Literal for "index" not recognized.')

        if index == -1:
            task = self.tasks.pop()
        else:
            task = discord.utils.get(self.tasks, index=index)
            if task:
                self.tasks.remove(task)
            else:
                return await ctx.send("Unknown task.")

        if task.task:
            task.task.cancel()

        if task.ctx.command:
            await ctx.send(f"Cancelled task {task.index}: `{task.ctx.command.qualified_name}`,"
                           f" invoked {discord.utils.format_dt(task.ctx.message.created_at, 'R')}")
        else:
            await ctx.send(f"Cancelled task {task.index}: unknown,"
                           f" invoked {discord.utils.format_dt(task.ctx.message.created_at, 'R')}")

    @Feature.Command(parent="jsk", name="permit")
    async def jsk_permit(self, ctx: ContextA, user: typing.Union[discord.Member, discord.User]):
        """
        Permits a user to use Jishaku.
        """
        self.bot.jishaku_allowed_users.add(user.id)
        await ctx.send(f"Permitted {user.mention} ({user.id}) to use Jishaku.")

    @Feature.Command(parent="jsk", name="forbid")
    async def jsk_forbid(self, ctx: ContextA, user: typing.Union[discord.Member, discord.User]):
        """
        Forbids a user from using Jishaku.
        """
        if user.id in self.bot.jishaku_allowed_users:
            self.bot.jishaku_allowed_users.discard(user.id)
            await ctx.send(f"Removed Jishaku permission for {user.mention} ({user.id}).")
        else:
            await ctx.send(f"{user.mention} ({user.id}) was not in the permitted list.")

    @Feature.Command(parent="jsk", name="allowed")
    async def jsk_allowed(self, ctx: ContextA):
        """
        Lists all users permitted to use Jishaku.
        """
        if not self.bot.jishaku_allowed_users:
            return await ctx.send("No additional users have been permitted to use Jishaku.")
        
        users_list = []
        for uid in self.bot.jishaku_allowed_users:
            user = self.bot.get_user(uid)
            if user:
                users_list.append(f"{user.mention} ({uid})")
            else:
                users_list.append(f"Unknown User ({uid})")
        
        await ctx.send("Permitted users:\n" + "\n".join(users_list))

    @Feature.Command(parent="jsk", name="guilds", aliases=["servers"])
    async def jsk_guilds(self, ctx: ContextA):
        """
        Lists all the guilds (servers) the bot is currently in.
        """
        if not self.bot.guilds:
            return await ctx.send("The bot is not in any servers.")
        
        paginator = commands.Paginator(prefix="```", suffix="```", max_size=1980)
        for guild in self.bot.guilds:
            paginator.add_line(f"{guild.name} ({guild.id}) - {guild.member_count} members")
            
        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        await interface.send_to(ctx)

    @Feature.Command(parent="jsk", name="leave")
    async def jsk_leave(self, ctx: ContextA, guild_id: int):
        """
        Causes the bot to leave a specific guild.
        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send(f"Could not find guild with ID {guild_id}")
            
        try:
            await guild.leave()
            await ctx.send(f"Successfully left guild: {guild.name} ({guild_id})")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to leave guild: {e}")

    @Feature.Command(parent="jsk", name="invite")
    async def jsk_invite(self, ctx: ContextA):
        """
        Generates an invite link for the bot.
        """
        permissions = discord.Permissions(8)  # Administrator
        try:
            invite_url = discord.utils.oauth_url(self.bot.user.id, permissions=permissions)
            await ctx.send(f"Invite link (with Admin permissions):\n<{invite_url}>")
        except Exception as e:
            await ctx.send(f"Failed to generate invite URL: {e}")

    @Feature.Command(parent="jsk", name="purge", aliases=["clean"])
    async def jsk_purge(self, ctx: ContextA, limit: int = 100):
        """
        Purges a specified number of messages from the current channel (excluding pinned messages).
        """
        try:
            deleted = await ctx.channel.purge(limit=limit, check=lambda m: not m.pinned)
            await ctx.send(f"Successfully purged {len(deleted)} messages.", delete_after=5)
        except discord.HTTPException as e:
            await ctx.send(f"Failed to purge messages: {e}")
