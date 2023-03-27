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

def is_active_blood_moon(day, hour):
    return((day % 7 == 0 and hour > 21) and (day % 7 == 1 and hour < 4))

def days_to_blood_moon(day):
    return (7 - (day % 7))

def get_servertime(ticks):
    curServerDays = ticks / 24000
    curServerDay = math.floor(curServerDays) + 1
    curServerHours = (curServerDays - math.floor(curServerDays)) * 24
    curServerHour = math.floor(curServerHours)
    curServerMinutes = (curServerHours - math.floor(curServerHours)) * 60
    curServerMinute = math.floor(curServerMinutes)
    return (curServerDay, curServerHour, curServerMinute)

def get_info(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        packet = b'\xff\xff\xff\xff\x54Source Engine Query\x00'
        logging.debug('sending info request')
        s.sendto(packet, (host, port))
        s.settimeout(10)
        data, addr = s.recvfrom(128)
        logging.debug(f"got data: {data}")
        logging.debug('sending info request with challenge response')
        s.sendto(packet + data[5:], (host, port))
        s.settimeout(10)
        data, addr = s.recvfrom(10240)
        logging.debug(f"got data: {data}")
    except socket.timeout:
        logging.error("socket timeout on A2S_INFO request")
        s.close()
        return None

    s.close()
    
    # parse info
    info = {
        'protocol': int(data[5])
    }

    idx = 6
    strEnd = data.find(b'\x00', idx)
    info['Name'] = data[idx:strEnd].decode('utf-8')
    idx = strEnd + 1
    strEnd = data.find(b'\x00', idx)
    info['Map'] = data[idx:strEnd].decode('utf-8')
    idx = strEnd + 1
    strEnd = data.find(b'\x00', idx)
    info['Folder'] = data[idx:strEnd].decode('utf-8')
    idx = strEnd + 1
    strEnd = data.find(b'\x00', idx)
    info['Game'] = data[idx:strEnd].decode('utf-8')
    idx = strEnd + 1
    info['ID'] = data[idx:(idx+2)]
    idx = idx + 2
    info['Players'] = int(data[idx])
    idx = idx + 1
    info['Max Players'] = int(data[idx])

    return info


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
    async def do_start(update, context):
        rules = get_rules(args.host, args.port)
        info = get_info(args.host, args.port)
        day, hour, minute = get_servertime(int(rules['CurrentServerTime']))
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

    return do_start

def cmd_status(args):
    async def do_status(update, context):
        logging.info('in do_status callback...')
        info = get_info(args.host, args.port)
        if info is None:
            return
        logging.info(f"{info['Players']} out of {info['Max Players']} connected")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{info['Players']} out of {info['Max Players']} connected")
    return do_status

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

def job_alert_minute(args, active_chats):

    async def callback_minute(context):
        rules = get_rules(args.host, args.port)
        info = get_info(args.host, args.port)
        if rules is None or info is None:
            # nothing to do, the server didn't respond. Just return
            return
        ticks = int(rules['CurrentServerTime'])
        day, hour, minute = get_servertime(ticks)

        if day % 7 == 0:
            for cid in active_chats:
                if not active_chats[cid]['blood_moon']['day_alert']:
                    await context.bot.send_message(chat_id=cid, text='\U0001f6a8 It is a Blood Moon day! \U0001f6a8')
                    active_chats[cid]['blood_moon']['day_alert'] = True
        else:
            for cid in active_chats:
                active_chats[cid]['blood_moon']['day_alert'] = False
        
        if is_active_blood_moon(day, hour):
            for cid in active_chats:
                if not active_chats[cid]['blood_moon']['start_alert']:
                    await context.bot.send_message(chat_id=cid, text='\U0001f6a8\U0001f6a8\U0001f6a8 The Blood Moon has begun! \U0001f6a8\U0001f6a8\U0001f6a8')
                    active_chats[cid]['blood_moon']['start_alert'] = True
        else:
            for cid in active_chats:
                active_chats[cid]['blood_moon']['start_alert'] = False

    return callback_minute

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