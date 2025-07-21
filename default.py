import xbmc, xbmcaddon
import json
import time
import re
import requests
import urllib.parse

from lib import discordpresence

def log(msg):
    xbmc.log("[Discord RP] " + msg)

DISCORD_CLIENT_ID = '0'
CLIENT_ID = ['570950300446359552','1267115234674348135','1267115677337256057']

IMAGES_URL = ""

def removeKodiTags(text):
    log("Removing tags for: " + text)

    validTags = ["I", "B", "LIGHT", "UPPERCASE", "LOWERCASE", "CAPITALIZE", "COLOR"]
    
    for tag in validTags:
        r = re.compile("\[\s*/?\s*"+tag+"\s*?\]")
        text = r.sub("", text)

    r = re.compile("\[\s*/?\s*CR\s*?\]")
    text = r.sub(" ", text)

    r = re.compile("\[\s*/?\s*COLOR\s*?.*?\]")
    text = r.sub("", text)

    log("Removed tags. Result: " + text)

    return text

class UnsupportedVideoType:
    def __init__(self, title):
        self.title = title.split("\\")[-1].split("/")[-1]

    def getTitle(self):
        return self.title

    def getMediaType(self):
        return 'Unknown'


class ServiceRichPresence:
    def __init__(self):
        self.presence = None
        self.settings = {}
        self.paused = True
        self.connected = False

        self.updateSettings()
        self.clientId = self.settings['client_id']

    def setPauseState(self, state):
        self.paused = state

    def connectToDiscord(self, client_id=None):
        self.connected = False
        self.presence = None
        while not self.presence:
            try:
                if client_id == None:
                    client_id = self.settings['client_id']
                    if client_id == 3:
                        client_id = 0
                self.presence = discordpresence.DiscordIpcClient.for_platform(CLIENT_ID[client_id])
            except Exception as e:
                log("Could not connect to discord: "+str(e))
                self.presence = None
                monitor.waitForAbort(5)
                # update every 5s just in case

        self.connected = True
        try:
            self.updatePresence()
        except Exception as e:
            log("Error while updating: " + str(e))


    def updateSettings(self):
        self.settings = {}
        self.settings['large_text'] = "Kodi"

        addon = xbmcaddon.Addon()
        
        self.settings['episode_state'] = addon.getSettingInt('episode_state')
        self.settings['episode_details'] = addon.getSettingInt('episode_details')
        self.settings['movie_state'] = addon.getSettingInt('movie_state')
        self.settings['movie_details'] = addon.getSettingInt('movie_details')

        self.settings['inmenu'] = addon.getSettingBool('inmenu')
        self.settings['auto_client_id'] = False
        self.settings['client_id'] = addon.getSettingInt('client_id')
        if self.settings['client_id'] == 3:
            self.settings['auto_client_id'] = True
        self.settings['use_id_lookup'] = addon.getSettingBool('use_id_lookup')

        self.settings['display_time'] = addon.getSettingBool('display_time')

        # get setting
        log(str(self.settings))

    def gatherData(self):
        player = xbmc.Player()
        if player.isPlayingVideo():
            data = player.getVideoInfoTag()
            if data.getTitle() == "":
                data = UnsupportedVideoType(player.getPlayingFile())
            return data
            
        return None

    def craftNoVideoState(self, data):
        if self.settings['inmenu']:
            activity = {'assets' : {'large_image' : 'default',
                                  'large_text' : self.settings['large_text']},
                        'state' : (self.settings['inmenu'] and 'In menu' or '')
                        }
            return activity
        else:
            return None

    def getEpisodeState(self, data):
        if self.settings['episode_state'] == 0:
            return removeKodiTags(data.getTitle())
        if self.settings['episode_state'] == 1:
            return data.getTVShowTitle()
        if self.settings['episode_state'] == 2:
            return data.getGenre()
        if self.settings['episode_state'] == 3:
            directors = data.getDirectors()
            if directors:
                return ", ".join(directors)
        return None

    def getEpisodeDetails(self, data):
        if self.settings['episode_details'] == 0:
            return data.getTVShowTitle()
        if self.settings['episode_details'] == 1:
            return '{}x{:02} {}'.format(data.getSeason(),data.getEpisode(),removeKodiTags(data.getTitle()))
        if self.settings['episode_details'] == 2:
            return data.getGenre()
        if self.settings['episode_details'] == 3:
            directors = data.getDirectors()
            if directors:
                return ", ".join(directors)
        return None

    def craftEpisodeState(self, data):
        activity = {}

        activity['assets'] = {'large_image' : IMAGES_URL != "" and (IMAGES_URL + "?name=" + urllib.parse.quote(data.getTVShowTitle()) + "&id=" + urllib.parse.quote(data.getIMDBNumber() if self.settings["use_id_lookup"] else "") + "&type=tv") or "default",
                              'large_text': 'Season {:02}, Episode {:02}'.format(data.getSeason(), data.getEpisode())}

        state = self.getEpisodeState(data)
        if state:
            activity['state'] = state

        details = self.getEpisodeDetails(data)
        if details:
            activity['details'] = details
        return activity

    def getMovieState(self, data):
        if self.settings['movie_state'] == 0:
            return data.getGenre()
        if self.settings['movie_state'] == 1:
            return removeKodiTags(data.getTitle())
        if self.settings['movie_state'] == 2:
            directors = data.getDirectors()
            if directors:
                return ", ".join(directors)
        return None

    def getMovieDetails(self, data):
        if self.settings['movie_details'] == 0:
            return removeKodiTags(data.getTitle())
        if self.settings['movie_details'] == 1:
            return data.getGenre()
        if self.settings['movie_details'] == 3:
            directors = data.getDirectors()
            if directors:
                return ", ".join(directors)
        return None

    def craftMovieState(self, data):
        activity = {}
        activity['assets'] = {'large_image' : IMAGES_URL != "" and (IMAGES_URL + "?name=" + urllib.parse.quote(data.getTitle()) + "&id=" + urllib.parse.quote(data.getIMDBNumber() if self.settings["use_id_lookup"] else "") + "&type=movie") or "default",
                              'large_text' : removeKodiTags(data.getTitle())}

        state = self.getMovieState(data)
        if state:
            activity['state'] = state

        details = self.getMovieDetails(data)
        if details:
            activity['details'] = details 
        return activity

    def craftVideoState(self, data):
        activity = {}

        log("Crafting video state")
        title = data.getTitle()
        title = removeKodiTags(title)

        activity['assets'] = {'large_image' : 'default',
                              'large_text' : title }

        activity['details'] = title

        return activity

    def mainLoop(self):
        while True:
            monitor.waitForAbort(5)
            if monitor.abortRequested():
                break
            self.updatePresence()
        log("Abort called. Exiting...")
        if self.connected:
            try:
                self.presence.close()
            except IOError as e:
                self.connected = False
                log("Error closing connection: " + str(e))

    def updatePresence(self):
        if self.connected:
            data = self.gatherData()

            activity = None
            used_client_id = self.settings['client_id']

            if not data:
                # no video playing
                log("Setting default")
                if self.settings['inmenu']:
                    activity = self.craftNoVideoState(data)
                    if self.settings['auto_client_id']:
                        used_client_id = 0
            else:
                if data.getMediaType() == 'episode':
                    activity = self.craftEpisodeState(data)
                    if self.settings['auto_client_id']:
                        used_client_id = 2
                elif data.getMediaType() == 'movie':
                    activity = self.craftMovieState(data)
                    if self.settings['auto_client_id']:
                        used_client_id = 1
                elif data.getMediaType() == 'video':
                    activity = self.craftVideoState(data)
                    if self.settings['auto_client_id']:
                        used_client_id = 0
                else:
                    activity = self.craftVideoState(data)
                    if self.settings['auto_client_id']:
                        used_client_id = 0
                    log("Unsupported media type: "+str(data.getMediaType()))
                    log("Using workaround")
                    
                activity['status_display_type'] = 2

                if self.settings['display_time']:
                    currentTime = player.getTime()
                    fullTime = player.getTotalTime()
                    if fullTime is not None and currentTime is not None and currentTime > 0 and fullTime > 0:
                        if self.paused:
                            activity['assets']['small_image'] = 'paused'
                            # Works for
                            #   xx:xx/xx:xx
                            #   xx:xx/xx:xx:xx
                            #   xx:xx:xx/xx:xx:xx
                            hours = int(currentTime/3600)
                            minutes = int(currentTime/60) - hours*60
                            seconds = int(currentTime) - minutes*60 - hours*3600

                            fhours = int(fullTime/3600)
                            fminutes = int(fullTime/60) - fhours*60
                            fseconds = int(fullTime) - fminutes*60 - fhours*3600
                            activity['assets']['small_text'] = "{}{:02}:{:02}/{}{:02}:{:02}".format('{}:'.format(hours) if hours>0 else '',
                                                                    minutes,
                                                                    seconds,
                                                                    '{}:'.format(fhours) if fhours>0 else '',
                                                                    fminutes,
                                                                    fseconds
                                        )

                        else:
                            remainingTime = fullTime - currentTime
                            activity['timestamps'] = {'start': int(time.time()-currentTime ), 'end' : int(time.time()+remainingTime)}

            if activity == None:
                try:
                    self.presence.clear_activity()
                except Exception as e:
                    log("Error while clearing: " + str(e))
            else:
                if used_client_id != self.clientId:
                    self.clientId = used_client_id
                    self.presence.close()
                    self.presence = None
                    self.connected = False
                    self.connectToDiscord(used_client_id)
                    self.updatePresence()
                else:
                    log("Activity set: " + str(activity))
                    activity['type'] = 3
                    try:
                        self.presence.set_activity(activity)
                    except IOError:
                        log("Activity set failed. Reconnecting to Discord")
                        self.connected = False
                        self.connectToDiscord(used_client_id)
                        self.presence.set_activity(activity)

class MyPlayer(xbmc.Player):
    def __init__(self):
        xbmc.Player.__init__(self)

    def onPlayBackPaused(self):
        drp.setPauseState(True)
        drp.updatePresence()

    def onAVChange(self):
        drp.updatePresence()

    def onAVStarted(self):
        drp.setPauseState(False)
        drp.updatePresence()

    def onPlayBackEnded(seld):
        drp.setPauseState(True)
        drp.updatePresence()

    def onPlayBackResumed(self):
        drp.setPauseState(False)
        drp.updatePresence()

    def onPlayBackError(self):
        drp.setPauseState(True)
        drp.updatePresence()

    def onPlayBackSeek(self, *args):
        drp.updatePresence()

    def onPlayBackSeekChapter(self, *args):
        drp.updatePresence()

    def onPlayBackStarted(self):
        drp.setPauseState(False)
        # media might not be loaded
        drp.updatePresence()

    def onPlayBackStopped(self):
        drp.setPauseState(True)
        drp.updatePresence()


class MyMonitor(xbmc.Monitor):
    def __init__(self):
        xbmc.Monitor.__init__(self)
        log("Monitor initialized")

    def onSettingsChanged(self):
        drp.updateSettings()
        drp.updatePresence()

try:
    IMAGES_URL = requests.get("https://hiumee.github.io/kodi/images_url").text.strip()
except Exception:
    pass

monitor = MyMonitor()
player = MyPlayer()

drp = ServiceRichPresence()
drp.connectToDiscord()
drp.updatePresence()
drp.mainLoop()