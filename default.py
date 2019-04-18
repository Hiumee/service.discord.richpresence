import xbmc, xbmcaddon
import json
import time

from lib import discordpresence

DISCORD_CLIENT_ID = '544620244014989312'

SUPPORTED_TYPES = ['episode', 'movie']
SETT = ['state', 'details']

getsetting = {
                'movie':   {
                    'state': {
                        "0": lambda data: ''.join(i+', ' for i in data['genre'])[:-2],
                        "1": lambda data: data['title'],
                        "2": lambda data: None
                        },
                    'details': {
                        "0": lambda data: data['title'],
                        "1": lambda data: ''.join(i+', ' for i in data['genre'])[:-2],
                        "2": lambda data: None
                    }

                },
                'episode': {
                    'state': {
                        "0": lambda data: '{}x{:02} {}'.format(data['season'],data['episode'],data['title']),
                        "1": lambda data: data['showtitle'],
                        "2": lambda data: ''.join(i+', ' for i in data['genre'])[:-2],
                        "3": lambda data: None
                    },
                    'details': {
                        "0": lambda data: data['showtitle'],
                        "1": lambda data: '{}x{:02} {}'.format(data['season'],data['episode'],data['title']),
                        "2": lambda data: ''.join(i+', ' for i in data['genre'])[:-2],
                        "3": lambda data: None
                    }

                },

            }

def base_activity():
    activity = {
        'assets': {'large_image': 'default',
                   'large_text': 'Kodi'},
    }
    return activity

def get_data():
    data  = json.loads(xbmc.executeJSONRPC('{"command": "Player.GetItem", "jsonrpc": "2.0", "method": "Player.GetItem", "id": 1, "params": {"playerid": 1, "properties": ["title", "season", "showtitle", "episode", "genre"]}}'))['result']

    act = base_activity()
    if data:
        data = data['item']
        data2 = json.loads(xbmc.executeJSONRPC('{"command": "Player.GetProperties", "jsonrpc": "2.0", "method": "Player.GetProperties", "id": 1, "params": {"playerid": 1, "properties": ["speed", "time", "totaltime"]}}'))['result']

        if data['type'] in SUPPORTED_TYPES:

            for pres in SETT:
                setting = getsetting[data['type']][pres][xbmcaddon.Addon().getSetting(data['type']+'_'+pres)](data)
                if setting:
                    act[pres] = setting

            if data['type'] == 'episode':
                act['assets']['large_text'] = data['showtitle']
                act['assets']['large_image'] = 'default'
                
            elif data['type'] == 'movie':
                act['assets']['large_text'] = data['title']
                act['assets']['large_image'] = 'default'

            if data2['speed'] == 0:
                act['assets']['small_image'] = 'paused'
                # Works for
                #   xx:xx/xx:xx
                #   xx:xx/xx:xx:xx
                #   xx:xx:xx/xx:xx:xx
                # If you watch something longer than 24h or shorter than one minute make it yourself
                act['assets']['small_text'] = "{}{:02}:{:02}/{}{:02}:{:02}".format('{}:'.format(data2['time']['hours']) if data2['time']['hours']>0 else '',
                                                           data2['time']['minutes'],
                                                           data2['time']['seconds'],
                                                           '{}:'.format(data2['totaltime']['hours']) if data2['totaltime']['hours']>0 else '',
                                                           data2['totaltime']['minutes'],
                                                           data2['totaltime']['seconds']
                            )
            else:
                currenttime = data2['time']['hours'] * 3600 + data2['time']['minutes'] * 60 + data2['time']['seconds']
                fulltime = data2['totaltime']['hours'] * 3600 + data2['totaltime']['minutes'] * 60 + data2['totaltime']['seconds']
                remainingtime = fulltime - currenttime
                remainingtime /= data2['speed']
                act['timestamps'] = {}
                act['timestamps']['end'] =  int(time.time() + remainingtime)
            return act

    if xbmcaddon.Addon().getSetting('inmenu') == 'false':
        return False
    act['state'] = "In menu"
    return act

ipc = None
monitor = xbmc.Monitor()

while ipc == None and not monitor.abortRequested():
    try:
        ipc = discordpresence.DiscordIpcClient.for_platform(DISCORD_CLIENT_ID)
        break
    except Exception as e:
        ipc = None
        xbmc.log("[Discord RP] Could not connect to Discord. Retry in 15s")
        xbmc.log("[Discord RP] [Error] "+str(e))
    if monitor.waitForAbort(15):
        ipc = None
        break

while ipc and not monitor.abortRequested():
    try:
        rpdata = get_data()
        if rpdata:
            ipc.set_activity(rpdata)
        else:
            ipc.clear_activity()
        xbmc.log("[Discord RP] Updated")
    except:
        xbmc.log("[Discord RP] Discord disconnected")
        ipc = None
        while ipc == None and not monitor.abortRequested():
            try:
                ipc = discordpresence.DiscordIpcClient.for_platform(DISCORD_CLIENT_ID)
                xbmc.log("[Discord RP] Reconnected")
                rpdata = get_data()
                if rpdata:
                    ipc.set_activity(rpdata)
                else:
                    ipc.clear_activity()
                xbmc.log("[Discord RP] Updated")
                break
            except Exception as e:
                ipc = None
                xbmc.log("[Discord RP] Could not connect to Discord. Retry in 15s")
                xbmc.log("[Discord RP] [Error] "+str(e))
            if monitor.waitForAbort(15):
                xbmc.log("[Discord RP] Abort")
                ipc = None
                break
    if monitor.waitForAbort(15):
        xbmc.log("[Discord RP] Abort")
        break


xbmc.log("[Discord RP] Exiting...")
if ipc:
    ipc.clear_activity()
    ipc.close()