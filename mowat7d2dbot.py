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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

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

def cmd_start(args):

    async def do_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info(context.args)
        await context.bot.send_message(chat_id=update.effective_chat.id, text='\U0001f6a8 Is this thing on? \U0001f6a8')

    return do_start

def cmd_time(args):

    async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
        rules = get_rules(args.host, args.port)

        logging.debug(rules)

        curServerTime = int(rules['CurrentServerTime'])

        curServerDays = curServerTime / 24000
        logging.info(curServerDays)

        curServerDay = math.floor(curServerDays) + 1
        logging.info(curServerDay)
        
        curServerHours = (curServerDays - math.floor(curServerDays)) * 24
        logging.info(curServerHours)

        curServerHour = math.floor(curServerHours)
        curServerMinutes = (curServerHours - math.floor(curServerHours)) * 60
        curServerMinute = math.floor(curServerMinutes)
        logging.info(f"day {curServerDay} {curServerHour:02d}:{curServerMinute:02d}")

        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"day {curServerDay} {curServerHour:02d}:{curServerMinute:02d}")

    return get_time

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

    global args
    args = parser.parse_args()

    app = ApplicationBuilder().token(args.token).build()
    
    start_handler = CommandHandler('start', cmd_start(args))
    #status_handler = CommandHandler('status', cmd_status)
    get_time_handler = CommandHandler('time', cmd_time(args))
    app.add_handler(start_handler)
    app.add_handler(get_time_handler)

    app.run_polling()

if __name__ == "__main__":
    main()