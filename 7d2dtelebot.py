#!/usr/bin/env python

import logging
import socket
import sys
import math
import json
import argparse
import a2s
from decimal import *
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

class ServerTime:
    TICKS_PER_DAY = Decimal(24000)
    def __init__(self, ticks):
        self.ticks = Decimal(ticks)
        self._days = self.ticks / ServerTime.TICKS_PER_DAY
        self.days = math.floor(self._days) + 1
        self._hours = (self._days % Decimal(1)) * Decimal(24)
        self.hours = math.floor(self._hours)
        self._minutes = (self._hours % Decimal(1)) * Decimal(60)
        self.minutes = math.floor(self._minutes)

    def is_blood_moon_day(self):
        return(self.days % 7 == 0)

    def is_active_blood_moon(self):
        return((self.days % 7 == 0 and self.hours > 21) or (self.days % 7 == 1 and self.hours < 4))

class SevenDaysToDieServer:

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self.address = (host, port)
        self.active_chats = dict()

    def _get_rules(self):
        rules = None
        try:
            rules = a2s.rules(self.address)
        except socket.timeout:
            logging.error("socket timeout on A2S_RULES request")
        return rules

    async def job_alert_minute(self, context):
        rules = self._get_rules()

        if rules is None:
            # nothing to do, the server didn't respond. Just return
            return

        stime = ServerTime(int(rules['CurrentServerTime']))

        for cid in self.active_chats:
            logging.info(self.active_chats[cid])
            last_stime = ServerTime(self.active_chats[cid]['last_ticks'])
            last_pcount = self.active_chats[cid]['last_players']
            cur_pcount = int(rules['CurrentPlayers'])

            if cur_pcount != last_pcount:
                timemsg = ''
                if cur_pcount > last_pcount:
                    diff = cur_pcount - last_pcount
                    connmsg = 'connected'
                    if last_pcount == 0:
                        timemsg = ' (server time is now running)'
                else:
                    diff = last_pcount - cur_pcount
                    connmsg = 'disconnected'
                    if cur_pcount == 0:
                        timemsg = ' (server time is now paused)'

                playermsg = f"{diff} player{' has' if diff == 1 else 's have'} {connmsg}{timemsg}"
                await context.bot.send_message(chat_id=cid, text=playermsg)

            if stime.is_active_blood_moon():
                if not self.active_chats[cid]['blood_moon']['start_alert']:
                    await context.bot.send_message(chat_id=cid, text='\U0001f6a8\U0001f6a8\U0001f6a8 The Blood Moon has begun! \U0001f6a8\U0001f6a8\U0001f6a8')
                    logging.info(f"blood moon start alert sent to chat {cid}")
                    self.active_chats[cid]['blood_moon']['start_alert'] = True
            else:
                self.active_chats[cid]['blood_moon']['start_alert'] = False
            
            if stime.is_blood_moon_day():
                if not self.active_chats[cid]['blood_moon']['day_alert']:
                    await context.bot.send_message(chat_id=cid, text='\U0001f6a8 It is a Blood Moon day! \U0001f6a8')
                    logging.info(f"blood moon day alert sent to chat {cid}")
                    self.active_chats[cid]['blood_moon']['day_alert'] = True    
            else:
                self.active_chats[cid]['blood_moon']['day_alert'] = False

            # only send day updates when its not a blood moon day
            if stime.days != last_stime.days and not stime.is_blood_moon_day():
                await context.bot.send_message(chat_id=cid, text=f'A New Day: {stime.days} ({7 - (stime.days % 7)} days until the next blood moon)')
                logging.info(f"new day alert sent to chat {cid}")

            self.active_chats[cid]['last_ticks'] = stime.ticks
            self.active_chats[cid]['last_players'] = cur_pcount

    async def cmd_start(self, update, context):
        rules = self._get_rules()
        stime = ServerTime(int(rules['CurrentServerTime']))

        if rules is None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"\U0000274c Blood Moon Watch could not be started, server did not respond \U0000274c\n\n")
            return
        
        if update.effective_chat.id not in self.active_chats:
            data = {
                'blood_moon': {
                    'start_alert': False,
                    'day_alert': False
                },
                'last_ticks': stime.ticks,
                'last_players': int(rules['CurrentPlayers'])
            }
            self.active_chats[update.effective_chat.id] = data
            logging.info(f"active_chats: {self.active_chats}")
            message = f"\U00002705 Starting Blood Moon Watch for this chat \U00002705\n\n"
        else:
            logging.info("this chat already active")
            message = f"\U00002705 Blood Moon Watch already active for this chat \U00002705\n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

    async def cmd_status(self, update, context):
        rules = self._get_rules()
        if rules is None:
            msg = f"\U0000274c timed out on request. Server dead? \U0000274c"
        else:
            stime = ServerTime(int(rules['CurrentServerTime']))
            msg = f"\U0001f9df {rules['GameHost']} \U0001f9df\n\n"
            msg += f"{rules['CurrentPlayers']} out of {rules['MaxPlayers']} connected\n"
            msg += f"day {stime.days} {stime.hours:02d}:{stime.minutes:02d} ({'Paused' if int(rules['CurrentPlayers']) == 0 else 'Running'})"
            logging.info(f"sending status response to {update.effective_chat.id}")
            logging.debug(msg)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    async def cmd_time(self, update, context):
        rules = rules = self._get_rules()
        if rules is None:
            msg = f"\U0000274c timed out on request. Server dead? \U0000274c"
        else:
            stime = ServerTime(int(rules['CurrentServerTime']))
            msg = f"day {stime.days} {stime.hours:02d}:{stime.minutes:02d} ({'Paused' if int(rules['CurrentPlayers']) == 0 else 'Running'})"
            logging.info(msg)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    async def cmd_test(self, update, context):
        if len(context.args) == 0:
            msg = f"\U0000274c help: /test <ticks> \U0000274c"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        else:
            new_stime = ServerTime(int(context.args[0]))
            rules = self._get_rules()
            if rules is None:
                msg = f"\U0000274c timed out on request. Server dead? \U0000274c"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            else:
                stime = ServerTime(int(rules['CurrentServerTime']))
                msg = f"current ticks: {stime.ticks}, testing alerts if new ticks were: {new_stime.ticks}"
                logging.info(msg)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

                # test alerts...
                if new_stime.is_active_blood_moon():
                    await context.bot.send_message(chat_id=update.effective_chat.id, text='\U0001f6a8\U0001f6a8\U0001f6a8 The Blood Moon has begun! \U0001f6a8\U0001f6a8\U0001f6a8')
                elif new_stime.is_blood_moon_day():
                    await context.bot.send_message(chat_id=update.effective_chat.id, text='\U0001f6a8 It is a Blood Moon day! \U0001f6a8')
                elif (new_stime.days != stime.days):
                    daysuntil = 7 - (new_stime.days % 7)
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f'A New Day: {new_stime.days} ({daysuntil} days until the next blood moon)')
                
                # msg = f"day {stime.days} {stime.hours:02d}:{stime.minutes:02d} ({'Paused' if rules['CurrentPlayers'] == 0 else 'Running'})"
                # logging.info(msg)
                # await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        

def main():

    parser = argparse.ArgumentParser(
        description='Starts the 7 Days to Die telegram bot server'
    )

    parser.add_argument(
        'host', 
        help='7d2d server host name/ip'
    )
    parser.add_argument(
        'port',
        type=int,
        help='7d2d server host port'
    )
    parser.add_argument(
        'token',
        help='telegram bot token'
    )

    args = parser.parse_args()

    server = SevenDaysToDieServer(args.host, args.port)

    app = ApplicationBuilder().token(args.token).build()
    job_queue = app.job_queue

    job_minute = job_queue.run_repeating(server.job_alert_minute, interval=30, first=10)
    
    start_handler = CommandHandler('start', server.cmd_start)
    status_handler = CommandHandler('status', server.cmd_status)
    get_time_handler = CommandHandler('time', server.cmd_time)
    test_handler = CommandHandler('test', server.cmd_test)
    app.add_handler(start_handler)
    app.add_handler(status_handler)
    app.add_handler(get_time_handler)
    app.add_handler(test_handler)

    app.run_polling()

if __name__ == "__main__":
    main()