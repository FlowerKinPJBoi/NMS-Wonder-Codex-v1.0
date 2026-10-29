"""Interaction deadlines stay responsive while cloud-style storage is delayed.

Use the real SQLite economy with the PostgreSQL I/O profile to exercise the
thread boundary deterministically, without Discord or network credentials.
The separate PostgreSQL integration suite covers SQL and transaction behavior.
"""
import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord

from ffc_game.ffc_wilds.config import CATALOG_PATH, Settings
from ffc_game.ffc_wilds.discord_bot import EncounterView, WildsBot, WildsCommands
from ffc_game.ffc_wilds.engine import GameEngine

GUILD = "123456789012345678"
CHANNEL = "234567890123456789"
USER = 345678901234567890
MESSAGE = 456789012345678901


class CloudAsyncAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = GameEngine(":memory:", CATALOG_PATH)
        self.engine.configure_channel(GUILD, CHANNEL)
        self.engine.set_enabled(GUILD, CHANNEL, True)
        # GameIO selects its worker by backend; SQLite remains the real,
        # thread-safe underlying connection for this transport-only fixture.
        self.engine.backend = "postgresql"
        self.owned = True
        self.guard_threads = []
        def guard():
            self.guard_threads.append(threading.get_ident())
            if not self.owned:
                raise RuntimeError("synthetic credential must never appear")
        self.bot = WildsBot(Settings(GUILD, CHANNEL), engine=self.engine,
                            operation_guard=guard, persist_settings=False,
                            automatic_backups=False)
        self.bot.is_ready = Mock(return_value=True)
        self.bot.channel_ready = True
        self.post = SimpleNamespace(id=MESSAGE, edit=AsyncMock())
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = int(CHANNEL)
        channel.guild = SimpleNamespace(id=int(GUILD))
        channel.send = AsyncMock(return_value=self.post)
        channel.get_partial_message = Mock(return_value=self.post)
        self.bot.game_channel = channel
        self.sequence = 0

    async def asyncTearDown(self):
        await self.bot.close()

    def interaction(self):
        self.sequence += 1
        return SimpleNamespace(
            id=MESSAGE + self.sequence, guild_id=int(GUILD), channel_id=int(CHANNEL),
            user=SimpleNamespace(id=USER, bot=False, display_name="Explorer"),
            response=SimpleNamespace(is_done=Mock(return_value=False),
                                     send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()), message=self.post,
        )

    def spawn(self):
        event = self.engine.spawn(GUILD, CHANNEL, kind="fish")
        return self.engine.bind_message(event["id"], str(MESSAGE))

    async def wait_entered(self, entered):
        for _ in range(200):
            if entered.is_set():
                return
            await asyncio.sleep(0.005)
        self.fail("The synthetic storage worker did not start")

    async def test_collection_ack_precedes_slow_guard_and_worker_does_not_block_loop(self):
        event = self.spawn()
        view = EncounterView(self.bot, event)
        interaction = self.interaction()
        entered, release = threading.Event(), threading.Event()
        main_thread = threading.get_ident()
        calls = []
        def slow_guard():
            calls.append(("guard", threading.get_ident()))
            entered.set()
            self.assertTrue(release.wait(2))
        async def defer(**kwargs):
            calls.append(("ack", threading.get_ident()))
        self.bot.operation_guard = slow_guard
        interaction.response.defer.side_effect = defer
        task = asyncio.create_task(view.collect(interaction))
        try:
            await self.wait_entered(entered)
            self.assertEqual(calls[0], ("ack", main_thread))
            interaction.response.defer.assert_awaited_once()
            self.assertFalse(task.done())
            ticks = 0
            for _ in range(5):
                await asyncio.sleep(0.005)
                ticks += 1
            self.assertEqual(ticks, 5)
            self.assertTrue(all(thread != main_thread for label, thread in calls if label == "guard"))
        finally:
            release.set()
        await task
        self.assertEqual(self.engine.profile(GUILD, str(USER))["catches"], 1)
        interaction.followup.send.assert_awaited_once()
        view.stop()

    async def test_background_storage_does_not_delay_a_new_collection_ack(self):
        view = EncounterView(self.bot, self.spawn())
        entered, release = threading.Event(), threading.Event()
        def slow_background():
            entered.set()
            self.assertTrue(release.wait(2))
        background = asyncio.create_task(self.bot.db_call(slow_background))
        await self.wait_entered(entered)
        interaction = self.interaction()
        collect = asyncio.create_task(view.collect(interaction))
        try:
            await asyncio.sleep(0.02)
            interaction.response.defer.assert_awaited_once()
            self.assertFalse(background.done())
            self.assertFalse(collect.done())
        finally:
            release.set()
        await background
        await collect
        self.assertEqual(self.engine.profile(GUILD, str(USER))["catches"], 1)
        view.stop()

    async def test_inventory_check_and_callback_defer_once_then_use_followup(self):
        commands = WildsCommands(self.bot)
        interaction = self.interaction()
        self.assertTrue(await commands.interaction_check(interaction))
        await commands.inventory.callback(commands, interaction)
        interaction.response.defer.assert_awaited_once()
        interaction.response.send_message.assert_not_awaited()
        interaction.followup.send.assert_awaited_once()
        self.assertTrue(interaction.followup.send.await_args.kwargs["ephemeral"])

    async def test_cloud_profile_craft_and_warp_use_acknowledged_responses(self):
        commands = WildsCommands(self.bot)
        profile = self.interaction()
        self.assertTrue(await commands.interaction_check(profile))
        await commands.profile.callback(commands, profile)
        profile.response.defer.assert_awaited_once()
        profile.followup.send.assert_awaited_once()
        craft = self.interaction()
        self.assertTrue(await commands.interaction_check(craft))
        await commands.craft.callback(commands, craft, "not-a-recipe")
        craft.response.defer.assert_awaited_once()
        craft.followup.send.assert_awaited_once()
        warp = self.interaction()
        await self.bot.show_warp(warp)
        warp.response.defer.assert_awaited_once()
        warp.response.send_message.assert_not_awaited()
        warp.followup.send.assert_awaited_once()
        self.assertTrue(all(button.disabled for button in warp.followup.send.await_args.kwargs["view"].children[:2]))

    async def test_lost_ownership_during_ack_cannot_award_a_cloud_collection(self):
        view = EncounterView(self.bot, self.spawn())
        interaction = self.interaction()
        async def defer(**kwargs):
            self.owned = False
        interaction.response.defer.side_effect = defer
        with patch.object(self.bot, "close", new=AsyncMock()):
            await view.collect(interaction)
            await asyncio.sleep(0)
            self.assertTrue(self.bot._host_failed)
            self.assertEqual(self.engine.profile(GUILD, str(USER))["catches"], 0)
            self.bot.game_channel.send.assert_not_awaited()
        view.stop()

    async def test_concurrent_close_and_cancellation_wait_for_inflight_database_work(self):
        entered, release = threading.Event(), threading.Event()
        finished = threading.Event()
        def operation():
            entered.set()
            self.assertTrue(release.wait(2))
            finished.set()
        work = asyncio.create_task(self.bot.db_call(operation))
        await self.wait_entered(entered)
        first = asyncio.create_task(self.bot.close())
        second = asyncio.create_task(self.bot.close())
        await asyncio.sleep(0.02)
        first.cancel()
        await asyncio.sleep(0)
        first.cancel()
        self.assertFalse(second.done())
        self.assertFalse(self.bot._closed_engine)
        release.set()
        await work
        with self.assertRaises(asyncio.CancelledError):
            await first
        await second
        self.assertTrue(finished.is_set())
        self.assertTrue(self.bot.io.closed)
        self.assertTrue(self.bot._closed_engine)

    async def test_safe_error_diagnostics_never_include_exception_text(self):
        error = discord.NotFound(SimpleNamespace(status=404, reason="private-token"),
                                 {"code": 10062, "message": "private-token-do-not-log"})
        with self.assertLogs("ffc_wilds", level="WARNING") as logs:
            self.bot.log_safe_error("collection_callback", error)
        text = "\n".join(logs.output)
        self.assertIn("10062", text)
        self.assertIn("NotFound", text)
        self.assertNotIn("private-token", text)

    async def test_scheduler_close_during_public_send_finishes_without_retry_loop(self):
        self.bot.wait_until_ready = AsyncMock()
        self.engine.db.execute("UPDATE channels SET next_spawn_at=0")
        entered = asyncio.Event()
        async def blocked_send(**kwargs):
            entered.set()
            await asyncio.Future()
        self.bot.game_channel.send.side_effect = blocked_send
        self.bot.scheduler.start()
        await asyncio.wait_for(entered.wait(), 2)
        closing = asyncio.create_task(self.bot.close())
        try:
            done, _ = await asyncio.wait({closing}, timeout=1)
            self.assertIn(closing, done, "Shutdown must not retry a cancelled scheduler forever")
            await closing
            self.assertTrue(self.bot.scheduler.get_task().done())
            self.assertTrue(self.bot.io.closed)
            self.assertTrue(self.bot._closed_engine)
        finally:
            # Also permit a failed regression to cleanly release its fixture.
            self.bot.scheduler.stop()
            self.bot.scheduler.cancel()
            await asyncio.wait_for(asyncio.shield(closing), 2)

    async def test_cancelled_public_edit_preserves_cancellation_when_shutdown_fences_guard(self):
        entered = asyncio.Event()
        async def blocked_edit(**kwargs):
            entered.set()
            await asyncio.Future()
        self.post.edit.side_effect = blocked_edit
        editing = asyncio.create_task(self.bot.edit_public(self.post, view=None))
        await asyncio.wait_for(entered.wait(), 2)
        self.bot._closing = True
        editing.cancel()
        try:
            with self.assertRaises(asyncio.CancelledError):
                await editing
        finally:
            self.bot._closing = False

    async def test_autocomplete_uses_no_regular_defer_or_remote_guard(self):
        interaction = self.interaction()
        interaction.type = discord.InteractionType.autocomplete
        before = len(self.guard_threads)
        self.assertTrue(await self.bot.require_channel(interaction))
        interaction.response.defer.assert_not_awaited()
        self.assertEqual(len(self.guard_threads), before)


if __name__ == "__main__":
    unittest.main()
