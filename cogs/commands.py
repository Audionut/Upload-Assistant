# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from src.prep import Prep
from src.args import Args
from src.clients import Clients
from src.search import Search
from src.trackers.BLU import BLU
from src.trackers.BHD import BHD
from src.trackers.AITHER import AITHER
from src.trackers.STC import STC
from src.trackers.LCD import LCD
from src.trackers.CBR import CBR
from data.config import config  # type: ignore

import discord  # type: ignore
from discord.ext import commands  # type: ignore
import os
from datetime import datetime
import asyncio
import json
import multiprocessing
from pathlib import Path
from glob import glob
import argparse


class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """
        This event receives the the guild when the bot joins.
        """
        print(f'Joined {guild.name} with {guild.member_count} users!')

    @commands.command(aliases=['up'])
    async def upload(self, ctx, path, *args, message_id=0, search_args=tuple()):
        f"""
        Upload: for a list of arguments do {config['DISCORD']['command_prefix']}args
        """
        if ctx.channel.id != int(config['DISCORD']['discord_channel_id']):
            return

        parser = Args(config)
        if path is None:
            await ctx.send("Missing Path")
            return
        elif path.lower() == "-h":
            meta, help, before_args = parser.parse("", dict())
            await ctx.send(parser.help)
            return
        meta = dict()
        meta['base_dir'] = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        path = os.path.abspath(path)
        if os.path.exists(path):
            meta['path'] = os.path.abspath(path)
            try:
                args = (meta['path'],) + args + search_args
                meta, help, before_args = parser.parse(args, meta)
            except SystemExit:
                await ctx.send(f"Invalid argument detected, use `{config['DISCORD']['command_prefix']}args` for list of valid args")
                return
            if meta['imghost'] is None:
                meta['imghost'] = config['DEFAULT']['img_host_1']
            # if not meta['unattended']:
            #     ua = config['DEFAULT'].get('auto_mode', False)
            #     if str(ua).lower() == "true":
            #         meta['unattended'] = True
            prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
            preparing_embed = discord.Embed(title="Preparing to upload:", description=f"```{path}```", color=0xffff00)
            if message_id == 0:
                message = await ctx.send(embed=preparing_embed)
                meta['embed_msg_id'] = message.id
            else:
                message = await ctx.fetch_message(message_id)
                await message.edit(embed=preparing_embed)
            # message = await ctx.fetch_message(message_id)
            meta['embed_msg_id'] = message.id
            await message.clear_reactions()
            meta = await prep.gather_prep(meta=meta, mode="discord")
            # await ctx.send(file=discord.File(f"{base_dir}/tmp/{folder_id}/Mediainfo.json"))
            await self.send_embed_and_upload(ctx, meta)
        else:
            await ctx.send("Invalid Path")

    @commands.command()
    async def args(self, ctx):
        f"""
        Arguments for {config['DISCORD']['command_prefix']}upload
        """

        parser = Args(config)
        meta, help, before_args = parser.parse("", dict())
        help = help.format_help()
        help = help.split('optional')[1]
        if len(help) > 2000:
            await ctx.send(f"```{help[:1990]}```")
            await ctx.send(f"```{help[1991:]}```")
        else:
            await ctx.send(help.format_help())

    @commands.command()
    async def edit(self, ctx, uuid=None, *args):
        """
        Edit uuid w/ args
        """
        if ctx.channel.id != int(config['DISCORD']['discord_channel_id']):
            return
        if uuid is None:
            await ctx.send("Missing ID, please try again using the ID in the footer")
        parser = Args(config)
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        try:
            with open(f"{base_dir}/tmp/{uuid}/meta.json") as f:
                meta = json.load(f)
                f.close()
        except FileNotFoundError:
            await ctx.send("ID not found, please try again using the ID in the footer")
            return
        prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
        try:
            args = (meta['path'],) + args
            meta, help, before_args = parser.parse(args, meta)
        except argparse.ArgumentError as error:
            ctx.send(error)
        msg = await ctx.fetch_message(meta['embed_msg_id'])
        await msg.delete()
        new_msg = await msg.channel.send(f"Editing {meta['uuid']}")
        meta['embed_msg_id'] = new_msg.id
        meta['edit'] = True
        meta = await prep.gather_prep(meta=meta, mode="discord")
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await prep.get_name(meta)
        await self.send_embed_and_upload(ctx, meta)

    @commands.group(invoke_without_command=True)
    async def search(self, ctx, *, args=None):
        """
        Search for a file to upload
        """
        search_terms = args
        parser = Args(config)
        try:
            input_string = args
            dict, parser, before_args = parser.parse(tuple(input_string.split(' ')), {})
            search_terms = " ".join(before_args)
            args = args.replace(search_terms, '')
            while args.startswith(" "):
                args = args[1:]
        except SystemExit:
            await ctx.send(f"Invalid argument detected, use `{config['DISCORD']['command_prefix']}args` for list of valid args")
            return

        if ctx.channel.id != int(config['DISCORD']['discord_channel_id']):
            return
        search = Search(config=config)
        if search_terms is None:
            await ctx.send("Missing search term(s)")
            return
        files_total = await search.searchFile(search_terms)
        if files_total == []:
            await ctx.send("Nothing Found")
            return
        files = "\n\n• ".join(files_total)
        if not files_total:
            embed = discord.Embed(description="No files found")
        elif len(files_total) >= 2:
            embed = discord.Embed(title=f"File search results for: `{search_terms}`", color=0x00ff40, description=f"```• {files}```")
            embed.add_field(name="What Now?", value=f"Please be more specific or use `{config['DISCORD']['command_prefix']}search dir` to find a directory")
            message = await ctx.send(embed=embed)
            return
        elif len(files_total) == 1:
            embed = discord.Embed(title=f"File search results for: {search_terms}", color=0x00ff40, description=f"```{files}```")
            embed.set_footer(text=f"{config['DISCORD']['discord_emojis']['UPLOAD']} to Upload")
            message = await ctx.send(embed=embed)
            await message.add_reaction(config['DISCORD']['discord_emojis']['UPLOAD'])
            channel = message.channel

            def check(reaction, user):
                if reaction.message.id == message.id:
                    if str(user.id) == config['DISCORD']['admin_id']:
                        if str(reaction.emoji) == config['DISCORD']['discord_emojis']['UPLOAD']:
                            return reaction

            try:
                await self.bot.wait_for("reaction_add", timeout=120, check=check)
            except asyncio.TimeoutError:
                await channel.send(f"Search: `{search_terms}`timed out")
            else:
                await self.upload(ctx, files_total[0], search_args=tuple(args.split(" ")), message_id=message.id)

    @search.command()
    async def dir(self, ctx, *, args=None):
        """
        Search for a directory to upload
        """
        search_terms = args
        parser = Args(config)
        try:
            input_string = args
            dict, parser, before_args = parser.parse(tuple(input_string.split(' ')), {})
            search_terms = " ".join(before_args)
            args = args.replace(search_terms, '')
            while args.startswith(" "):
                args = args[1:]
        except SystemExit:
            await ctx.send(f"Invalid argument detected, use `{config['DISCORD']['command_prefix']}args` for list of valid args")
            return

        if ctx.channel.id != int(config['DISCORD']['discord_channel_id']):
            return
        search = Search(config=config)
        if search_terms is None:
            await ctx.send("Missing search term(s)")
            return
        folders_total = await search.searchFolder(search_terms)
        if folders_total == []:
            await ctx.send("Nothing Found")
            return
        folders = "\n\n• ".join(folders_total)
        if not folders_total:
            embed = discord.Embed(description="No files found")
        elif len(folders_total) >= 2:
            embed = discord.Embed(title=f"Directory search results for: `{search_terms}`", color=0x00ff40, description=f"```• {folders}```")
            embed.add_field(name="What Now?", value=f"Please be more specific or use `{config['DISCORD']['command_prefix']}search dir` to find a directory")
            await ctx.send(embed=embed)
            return
        elif len(folders_total) == 1:
            embed = discord.Embed(title=f"Directory search results for: {search_terms}", color=0x00ff40, description=f"```{folders}```")
            embed.set_footer(text=f"{config['DISCORD']['discord_emojis']['UPLOAD']} to Upload")
            message = await ctx.send(embed=embed)
            await message.add_reaction(config['DISCORD']['discord_emojis']['UPLOAD'])
            channel = message.channel

            def check(reaction, user):
                if reaction.message.id == message.id:
                    if str(user.id) == config['DISCORD']['admin_id']:
                        if str(reaction.emoji) == config['DISCORD']['discord_emojis']['UPLOAD']:
                            return reaction

            try:
                await self.bot.wait_for("reaction_add", timeout=120, check=check)
            except asyncio.TimeoutError:
                await channel.send(f"Search: `{search_terms}`timed out")
            else:
                await self.upload(ctx, path=folders_total[0], search_args=tuple(args.split(" ")), message_id=message.id)
        # await ctx.send(folders_total)
        return

    async def send_embed_and_upload(self, ctx, meta):
        prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await prep.get_name(meta)

        if meta.get('uploaded_screens', False) is False:
            if meta.get('embed_msg_id', '0') != '0':
                message = await ctx.fetch_message(meta['embed_msg_id'])
                await message.edit(embed=discord.Embed(title="Uploading Screenshots", color=0xffff00))
            else:
                message = await ctx.send(embed=discord.Embed(title="Uploading Screenshots", color=0xffff00))
                meta['embed_msg_id'] = message.id

            channel = message.channel.id
            return_dict = multiprocessing.Manager().dict()
            u = multiprocessing.Process(target=prep.upload_screens, args=(meta, meta['screens'], 1, 0, meta['screens'], [], return_dict))
            u.start()
            while u.is_alive() is True:
                await asyncio.sleep(3)
            meta['image_list'] = return_dict['image_list']
            if meta['debug']:
                print(meta['image_list'])
            meta['uploaded_screens'] = True

        # Create base .torrent
        if len(glob(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")) == 0:
            if meta.get('embed_msg_id', '0') != '0':
                message = await ctx.fetch_message(int(meta['embed_msg_id']))
                await message.edit(embed=discord.Embed(title="Creating .torrent", color=0xffff00))
            else:
                message = await ctx.send(embed=discord.Embed(title="Creating .torrent", color=0xffff00))
                meta['embed_msg_id'] = message.id
            channel = message.channel
            if meta['nohash'] is False:
                if meta.get('torrenthash', None) is not None:
                    reuse_torrent = await client.find_existing_torrent(meta)  # noqa F821
                    if reuse_torrent is not None:
                        prep.create_base_from_existing_torrent(reuse_torrent, meta['base_dir'], meta['uuid'])

                p = multiprocessing.Process(target=prep.create_torrent, args=(meta, Path(meta['path'])))
                p.start()
                while p.is_alive() is True:
                    await asyncio.sleep(5)

                if int(meta.get('randomized', 0)) >= 1:
                    prep.create_random_torrents(meta['base_dir'], meta['uuid'], meta['randomized'], meta['path'])
            else:
                meta['client'] = 'none'

        # Format for embed
        if meta['tag'] == "":
            tag = ""
        else:
            tag = f" / {meta['tag'][1:]}"
        if meta['imdb_id'] == "0":
            imdb = ""
        else:
            imdb = f" / [IMDb](https://www.imdb.com/title/tt{meta['imdb_id']})"
        if meta['tvdb_id'] == "0":
            tvdb = ""
        else:
            tvdb = f" / [TVDB](https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series)"
        if meta['is_disc'] == "DVD":
            res = meta['source']
        else:
            res = meta['resolution']
        missing = await self.get_missing(meta)

        embed = discord.Embed(
            title=f"Upload: {meta['title']}",
            url=f"https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}",
            description=meta['overview'],
            color=0x0080ff,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Links", value=f"[TMDB](https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}){imdb}{tvdb}")
        embed.add_field(name=f"{res} / {meta['type']}{tag}", value=f"```{meta['name']}```", inline=False)
        if missing != []:
            embed.add_field(name="POTENTIALLY MISSING INFORMATION:", value="\n".join(missing), inline=False)
        embed.set_thumbnail(url=f"https://image.tmdb.org/t/p/original{meta['poster']}")
        embed.set_footer(text=meta['uuid'])
        embed.set_author(name="L4G's Upload Assistant", url="https://github.com/Audionut/Upload-Assistant", icon_url="https://images2.imgbox.com/6e/da/dXfdgNYs_o.png")

        message = await ctx.fetch_message(meta['embed_msg_id'])
        await message.edit(embed=embed)

        if meta.get('trackers', None) is not None:
            trackers = meta['trackers']
        else:
            trackers = config['TRACKERS']['default_trackers']
        trackers = trackers.split(',')
        for each in trackers:
            if "BLU" in each.replace(' ', ''):
                await message.add_reaction(config['DISCORD']['discord_emojis']['BLU'])
                await asyncio.sleep(0.3)
            if "BHD" in each.replace(' ', ''):
                await message.add_reaction(config['DISCORD']['discord_emojis']['BHD'])
                await asyncio.sleep(0.3)
            if "AITHER" in each.replace(' ', ''):
                await message.add_reaction(config['DISCORD']['discord_emojis']['AITHER'])
                await asyncio.sleep(0.3)
            if "STC" in each.replace(' ', ''):
                await message.add_reaction(config['DISCORD']['discord_emojis']['STC'])
                await asyncio.sleep(0.3)
            if "LCD" in each.replace(' ', ''):
                await message.add_reaction(config['DISCORD']['discord_emojis']['LCD'])
                await asyncio.sleep(0.3)
            if "CBR" in each.replace(' ', ''):
                await message.add_reaction(config['DISCORD']['discord_emojis']['CBR'])
                await asyncio.sleep(0.3)
        await message.add_reaction(config['DISCORD']['discord_emojis']['MANUAL'])
        await asyncio.sleep(0.3)
        await message.add_reaction(config['DISCORD']['discord_emojis']['CANCEL'])
        await asyncio.sleep(0.3)
        await message.add_reaction(config['DISCORD']['discord_emojis']['UPLOAD'])

        # Save meta to json
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)
            f.close()

        def check(reaction, user):
            if reaction.message.id == meta['embed_msg_id']:
                if str(user.id) == config['DISCORD']['admin_id']:
                    if str(reaction.emoji) == config['DISCORD']['discord_emojis']['UPLOAD']:
                        return reaction
                    if str(reaction.emoji) == config['DISCORD']['discord_emojis']['CANCEL']:
                        if meta['embed_msg_id']:
                            pass
                        raise CancelException
                    # if str(reaction.emoji) == config['DISCORD']['discord_emojis']['MANUAL']:
                    #     raise ManualException
        try:
            await self.bot.wait_for("reaction_add", timeout=43200, check=check)
        except asyncio.TimeoutError:
            try:
                msg = await ctx.fetch_message(meta['embed_msg_id'])
                timeout_embed = discord.Embed(title=f"{meta['title']} has timed out", color=0xff0000)
                await msg.clear_reactions()
                await msg.edit(embed=timeout_embed)
                return
            except Exception:
                print("timeout after edit")
                pass
        except CancelException:
            msg = await ctx.fetch_message(meta['embed_msg_id'])
            cancel_embed = discord.Embed(title=f"{meta['title']} has been cancelled", color=0xff0000)
            await msg.clear_reactions()
            await msg.edit(embed=cancel_embed)
            return
        else:

            # Check which are selected and upload to them
            msg = await ctx.fetch_message(message.id)
            tracker_list = list()
            tracker_emojis = config['DISCORD']['discord_emojis']
            while not tracker_list:
                await asyncio.sleep(1)
                for each in msg.reactions:
                    if each.count >= 2:
                        tracker = list(config['DISCORD']['discord_emojis'].keys())[list(config['DISCORD']['discord_emojis'].values()).index(str(each))]
                        if tracker not in ("UPLOAD"):
                            tracker_list.append(tracker)

            upload_embed_description = ' / '.join(tracker_list)
            upload_embed = discord.Embed(title=f"Uploading `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
            await msg.edit(embed=upload_embed)
            await msg.clear_reactions()

            client = Clients(config=config)
            if "MANUAL" in tracker_list:
                for manual_tracker in tracker_list:
                    manual_tracker = manual_tracker.replace(" ", "")
                    if manual_tracker.upper() == "BLU":
                        blu = BLU(config=config)
                        await blu.edit_desc(meta)
                    if manual_tracker.upper() == "BHD":
                        bhd = BHD(config=config)
                        await bhd.edit_desc(meta)
                    if manual_tracker.upper() == "AITHER":
                        aither = AITHER(config=config)
                        await aither.edit_desc(meta)
                    if manual_tracker.upper() == "STC":
                        stc = STC(config=config)
                        await stc.edit_desc(meta)
                    if manual_tracker.upper() == "LCD":
                        lcd = LCD(config=config)
                        await lcd.edit_desc(meta)
                    if manual_tracker.upper() == "CBR":
                        cbr = CBR(config=config)
                        await cbr.edit_desc(meta)
                archive_url = await prep.package(meta)
                upload_embed_description = upload_embed_description.replace('MANUAL', '~~MANUAL~~')
                if archive_url is False:
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0xff0000)
                    upload_embed.add_field(name="Unable to upload prep files", value=f"The files can be found at `tmp/{meta['title']}.tar`")
                    await msg.edit(embed=upload_embed)
                else:
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
                    upload_embed.add_field(name="Files can be found at:", value=f"{archive_url} or `tmp/{meta['uuid']}`")
                    await msg.edit(embed=upload_embed)
            if "BLU" in tracker_list:
                blu = BLU(config=config)
                dupes = await blu.search_existing(meta)
                meta = await self.dupe_embed(dupes, meta, tracker_emojis, channel)
                if meta['upload'] is True:
                    await blu.upload(meta)
                    await client.add_to_client(meta, "BLU")
                    upload_embed_description = upload_embed_description.replace('BLU', '~~BLU~~')
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
                    await msg.edit(embed=upload_embed)
            if "BHD" in tracker_list:
                bhd = BHD(config=config)
                dupes = await bhd.search_existing(meta)
                meta = await self.dupe_embed(dupes, meta, tracker_emojis, channel)
                if meta['upload'] is True:
                    await bhd.upload(meta)
                    await client.add_to_client(meta, "BHD")
                    upload_embed_description = upload_embed_description.replace('BHD', '~~BHD~~')
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
                    await msg.edit(embed=upload_embed)
            if "AITHER" in tracker_list:
                aither = AITHER(config=config)
                dupes = await aither.search_existing(meta)
                meta = await self.dupe_embed(dupes, meta, tracker_emojis, channel)
                if meta['upload'] is True:
                    await aither.upload(meta)
                    await client.add_to_client(meta, "AITHER")
                    upload_embed_description = upload_embed_description.replace('AITHER', '~~AITHER~~')
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
                    await msg.edit(embed=upload_embed)
            if "STC" in tracker_list:
                stc = STC(config=config)
                dupes = await stc.search_existing(meta)
                meta = await self.dupe_embed(dupes, meta, tracker_emojis, channel)
                if meta['upload'] is True:
                    await stc.upload(meta)
                    await client.add_to_client(meta, "STC")
                    upload_embed_description = upload_embed_description.replace('STC', '~~STC~~')
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
                    await msg.edit(embed=upload_embed)
            if "LCD" in tracker_list:
                lcd = LCD(config=config)
                dupes = await lcd.search_existing(meta)
                meta = await self.dupe_embed(dupes, meta, tracker_emojis, channel)
                if meta['upload'] is True:
                    await lcd.upload(meta)
                    await client.add_to_client(meta, "LCD")
                    upload_embed_description = upload_embed_description.replace('LCD', '~~LCD~~')
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
                    await msg.edit(embed=upload_embed)
            if "CBR" in tracker_list:
                cbr = CBR(config=config)
                dupes = await cbr.search_existing(meta)
                meta = await self.dupe_embed(dupes, meta, tracker_emojis, channel)
                if meta['upload'] is True:
                    await cbr.upload(meta)
                    await client.add_to_client(meta, "CBR")
                    upload_embed_description = upload_embed_description.replace('CBR', '~~CBR~~')
                    upload_embed = discord.Embed(title=f"Uploaded `{meta['name']}` to:", description=upload_embed_description, color=0x00ff40)
                    await msg.edit(embed=upload_embed)
            return None

    async def dupe_embed(self, dupes, meta, emojis, channel):
        if not dupes:
            print("No dupes found")
            meta['upload'] = True
            return meta
        else:
            dupe_text = "\n\n•".join(dupes)
            dupe_text = f"```•{dupe_text}```"
            embed = discord.Embed(title="Check if these are actually dupes!", description=dupe_text, color=0xff0000)
            embed.set_footer(text=f"{emojis['CANCEL']} to abort upload | {emojis['UPLOAD']} to upload anyways")
            message = await channel.send(embed=embed)
            await message.add_reaction(emojis['CANCEL'])
            await asyncio.sleep(0.3)
            await message.add_reaction(emojis['UPLOAD'])

            def check(reaction, user):
                if reaction.message.id == message.id:
                    if str(user.id) == config['DISCORD']['admin_id']:
                        if str(reaction.emoji) == emojis['UPLOAD']:
                            return reaction
                        if str(reaction.emoji) == emojis['CANCEL']:
                            if meta['embed_msg_id']:
                                pass
                            raise CancelException

            try:
                await self.bot.wait_for("reaction_add", timeout=600, check=check)
            except asyncio.TimeoutError:
                try:
                    await channel.send(f"{meta['uuid']} timed out")
                    meta['upload'] = False
                except Exception:
                    return
            except CancelException:
                await channel.send(f"{meta['title']} cancelled")
                meta['upload'] = False
            else:
                meta['upload'] = True
                for each in dupes:
                    if each == meta['name']:
                        meta['name'] = f"{meta['name']} DUPE?"
            finally:
                await message.delete()
        return meta

    async def get_missing(self, meta):
        missing = []
        if meta.get('imdb_id', '0') == '0':
            missing.append('--imdb')
        if isinstance(meta['potential_missing'], list) and len(meta['potential_missing']) > 0:
            for each in meta['potential_missing']:
                if meta.get(each, '').replace(' ', '') == "":
                    missing.append(f"--{each}")
        return missing


def setup(bot):
    bot.add_cog(Commands(bot))


class CancelException(Exception):
    pass


class ManualException(Exception):
    pass
