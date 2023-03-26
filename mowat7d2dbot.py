#!/usr/bin/env python

import logging
import socket
import sys
import math
import json
import argparse
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_servertime(ticks):
    curServerDays = ticks / 24000
    curServerDay = math.floor(curServerDays) + 1
    curServerHours = (curServerDays - math.floor(curServerDays)) * 24
    curServerHour = math.floor(curServerHours)
    curServerMinutes = (curServerHours - math.floor(curServerHours)) * 60
    curServerMinute = math.floor(curServerMinutes)
    curServerTime = f"{curServerHour:02d}:{curServerMinute:02d}"
    return (curServerDay, curServerTime)

def get_info():
    return None

def get_players():
    return None

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
        logging.error("socket timeout")
        s.close()
        return None

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

    async def do_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id not in active_chats:
            active_chats[update.effective_chat.id] = {'blood_moon_alert': False}
        logging.info(f"active_chats: {active_chats}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text='\U00002705 Starting Blood Moon Watch for this chat \U00002705')

    return do_start

def cmd_time(args):

    async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
        rules = get_rules(args.host, args.port)
        if rules is None:
            # nothing to do, the server didn't respond. Just return
            return

        logging.debug(rules)

        day, time = get_servertime(int(rules['CurrentServerTime']))
        
        logging.info(f"day {day} {time}")

        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"day {day} {time}")

    return get_time

def job_alert_minute(args, active_chats):

    async def callback_minute(context):
        rules = get_rules(args.host, args.port)
        if rules is None:
            # nothing to do, the server didn't respond. Just return
            return
        ticks = int(rules['CurrentServerTime'])
        logging.info(f"ticks {ticks}")
        day, time = get_servertime(ticks)
        logging.info(f"day {day} {time}")
        logging.info(f"blood moon? {day % 7 == 0}")
        if day % 7 == 0:
            for cid in active_chats:
                if not active_chats[cid]['blood_moon_alert']:
                    await context.bot.send_message(chat_id=cid, text='\U0001f6a8 It is a Blood Moon! \U0001f6a8')
                    active_chats[cid]['blood_moon_alert'] = True
        else:
            for cid in active_chats:
                active_chats[cid]['blood_moon_alert'] = False

    return callback_minute

def main():

    parser = argparse.ArgumentParser(
        description='Starts the MoWaT 7 Days to Die telegram bot server'
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
    #status_handler = CommandHandler('status', cmd_status)
    get_time_handler = CommandHandler('time', cmd_time(args))
    app.add_handler(start_handler)
    app.add_handler(get_time_handler)

    app.run_polling()

if __name__ == "__main__":
    main()