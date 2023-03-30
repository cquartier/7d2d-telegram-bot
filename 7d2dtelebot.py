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
        return((self.days % 7 == 0 and self.hours > 21) and (self.day % 7 == 1 and self.hours < 4))

class SevenDaysToDieServer:

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self.address = (host, port)

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

        if stime.is_blood_moon_day():
            for cid in active_chats:
                if not active_chats[cid]['blood_moon']['day_alert']:
                    await context.bot.send_message(chat_id=cid, text='\U0001f6a8 It is a Blood Moon day! \U0001f6a8')
                    active_chats[cid]['blood_moon']['day_alert'] = True
        else:
            for cid in active_chats:
                active_chats[cid]['blood_moon']['day_alert'] = False
        
        if stime.is_active_blood_moon():
            for cid in active_chats:
                if not active_chats[cid]['blood_moon']['start_alert']:
                    await context.bot.send_message(chat_id=cid, text='\U0001f6a8\U0001f6a8\U0001f6a8 The Blood Moon has begun! \U0001f6a8\U0001f6a8\U0001f6a8')
                    active_chats[cid]['blood_moon']['start_alert'] = True
        else:
            for cid in active_chats:
                active_chats[cid]['blood_moon']['start_alert'] = False

    async def cmd_start(self, update, context):
        rules = get_rules(args.host, args.port)
        info = get_info(args.host, args.port)
        stime = ServerTime(rules['CurrentServerTime'])
        if update.effective_chat.id not in active_chats:
            data = {
                'blood_moon': {
                    'active': is_active_blood_moon(day, hour),
                    'start_alert': False,
                    'day_alert': False,
                    'days_until': days_to_blood_moon(day)
                },
                'cur_day': day,
                'cur_hour': hour
            }
            active_chats[update.effective_chat.id] = data
            logging.info(f"active_chats: {active_chats}")
            message = f"\U00002705 Starting Blood Moon Watch for this chat \U00002705\n\n"
        else:
            logging.info("this chat already active")
            message = f"\U00002705 Blood Moon Watch already active for this chat \U00002705\n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

    async def cmd_status(self, update, context):
        logging.info('in do_status callback...')
        rules = self._get_rules()
        if rules is None:
            return
        logging.info(f"{rules['Players']} out of {info['Max Players']} connected")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{info['Players']} out of {info['Max Players']} connected")

def get_rules(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        packet = b'\xff\xff\xff\xff\x56'
        s.sendto(packet + b'\xff\xff\xff\xff', (host, port))
        s.settimeout(10)
        data, addr = s.recvfrom(128)
        s.sendto(packet + data[5:], (host, port))
        s.settimeout(10)
        data, addr = s.recvfrom(10240)
    except socket.timeout:
        logging.error("socket timeout on A2S_RULES request")
        s.close()
        return None

    s.close()
    numKeys = int(data[5])
    dataStrs = data[7:].split(b'\x00')
    curKey = 0
    dataDict = {}
    while (curKey < numKeys):
        i = curKey * 2
        dataDict[dataStrs[i].decode('utf-8')] = dataStrs[i + 1].decode('utf-8')
        curKey = curKey + 1

    return dataDict

def cmd_start(args, active_chats):
    

def cmd_status(args):
    

def cmd_time(args):
    async def get_time(update, context):
        rules = get_rules(args.host, args.port)
        info = get_info(args.host, args.port)
        if rules is None or info is None:
            # nothing to do, the server didn't respond. Just return
            return

        day, hour, minute = get_servertime(int(rules['CurrentServerTime']))
        state = 'Paused' if info['Players'] == 0 else 'Running'
        logging.info(f"day {day} {hour:02d}:{minute:02d} ({state})")

        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"day {day} {hour:02d}:{minute:02d} ({state})")
    return get_time

def (args, active_chats):

    

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

    active_chats = dict()

    app = ApplicationBuilder().token(args.token).build()
    job_queue = app.job_queue

    job_minute = job_queue.run_repeating(job_alert_minute(args, active_chats), interval=30, first=10)
    
    start_handler = CommandHandler('start', cmd_start(args, active_chats))
    status_handler = CommandHandler('status', cmd_status(args))
    get_time_handler = CommandHandler('time', cmd_time(args))
    app.add_handler(start_handler)
    app.add_handler(status_handler)
    app.add_handler(get_time_handler)

    app.run_polling()

if __name__ == "__main__":
    main()