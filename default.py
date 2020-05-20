import xbmc, xbmcaddon
import json
import time

from lib import discordpresence

def log(msg):
    xbmc.log("[Discord RP] " + msg)

DISCORD_CLIENT_ID = '0'
CLIENT_ID = ['544620244014989312',
             '570950300446359552']


class ServiceRichPresence:
    def __init__(self):
        self.presence = None
        self.settings = {}
        self.lastActivity = None
        self.paused = True

        self.updateSettings()
        self.clientId = self.settings['client_id']
        self.connectToDiscord()
        self.updatePresence()

    def setPauseState(self, state):
        self.paused = state

    def connectToDiscord(self):
        while not self.presence:
            try:
                self.presence = discordpresence.DiscordIpcClient.for_platform(CLIENT_ID[self.clientId])
            except Exception as e:
                log("Could not connect to discord - "+str(e))
                monitor.waitForAbort(30)
                # update every 30s just in case

    def updateSettings(self):
        self.settings = {}
        self.settings['large_text'] = "Kodi"

        addon = xbmcaddon.Addon()
        
        self.settings['episode_state'] = addon.getSettingInt('episode_state')
        self.settings['episode_details'] = addon.getSettingInt('episode_details')
        self.settings['movie_state'] = addon.getSettingInt('movie_state')
        self.settings['movie_details'] = addon.getSettingInt('movie_details')

        self.settings['inmenu'] = addon.getSettingBool('inmenu')
        self.settings['client_id'] = addon.getSettingInt('client_id')

        # get setting
        log(str(self.settings))

    def gatherData(self):
        player = xbmc.Player()
        if player.isPlayingVideo():
            return player.getVideoInfoTag()
            
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
            return '{}x{:02} {}'.format(data.getSeason(),data.getEpisode(),data.getTitle())
        if self.settings['episode_state'] == 1:
            return data.getTVShowTitle()
        if self.settings['episode_state'] == 2:
            return data.getGenre()
        return None

    def getEpisodeDetails(self, data):
        if self.settings['episode_details'] == 0:
            return data.getTVShowTitle()
        if self.settings['episode_details'] == 1:
            return '{}x{:02} {}'.format(data.getSeason(),data.getEpisode(),data.getTitle())
        if self.settings['episode_details'] == 2:
            return data.getGenre()
        return None

    def craftEpisodeState(self, data):
        activity = {}
        activity['assets'] = {'large_image' : 'default',
                              'large_text' : data.getTVShowTitle()}

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
            return data.getTitle()
        return None

    def getMovieDetails(self, data):
        if self.settings['movie_details'] == 0:
            return data.getTitle()
        if self.settings['movie_details'] == 1:
            return data.getGenre()
        return None

    def craftMovieState(self, data):
        activity = {}
        activity['assets'] = {'large_image' : 'default',
                              'large_text' : data.getTitle()}

        state = self.getMovieState(data)
        if state:
            activity['state'] = state

        details = self.getMovieDetails(data)
        if details:
            activity['details'] = details 
        return activity

    def mainLoop(self):
        while not monitor.abortRequested():
            if monitor.waitForAbort(5):
                log("Abort called. Exiting...")
                break
            self.updatePresence()
        if self.presence:
            self.presence.close()

    def updatePresence(self):
        data = self.gatherData()

        activity = None
        #activity['assets'] = {'large_image' : 'default',
        #                        'large_text' : self.settings['large_text']}

        if not data:
            # no video playing
            log("Setting default")
            if self.settings['inmenu']:
                activity = self.craftNoVideoState(data)
        else:
            if data.getMediaType() == 'episode':
                activity = self.craftEpisodeState(data)
            elif data.getMediaType() == 'movie':
                activity = self.craftMovieState(data)

            if self.paused:
                activity['assets']['small_image'] = 'paused'
                # Works for
                #   xx:xx/xx:xx
                #   xx:xx/xx:xx:xx
                #   xx:xx:xx/xx:xx:xx
                currentTime = player.getTime()
                hours = int(currentTime/3600)
                minutes = int(currentTime/60) - hours*60
                seconds = int(currentTime) - minutes*60 - hours*3600

                fullTime = player.getTotalTime()
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
                currentTime = player.getTime()
                fullTime = player.getTotalTime()
                remainingTime = fullTime - currentTime
                activity['timestamps'] = {'end' : int(time.time()+remainingTime)}


        if activity != self.lastActivity:
            self.lastActivity = activity
            if activity == None:
                self.presence.clear_activity()
            else:
                if self.settings['client_id'] != self.clientId:
                    self.clientId = self.settings['client_id']
                    self.presence.close()
                    self.presence = None
                    self.connectToDiscord()
                    self.updatePresence()
                else:
                    log("Activity set: " + str(activity))
                    self.presence.set_activity(activity)


class MyPlayer(xbmc.Player):
    def __init__(self):
        xbmc.Player.__init__(self)

    def onPlayBackPaused(self):
        drp.setPauseState(True)
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

monitor = MyMonitor()
player = MyPlayer()

drp = ServiceRichPresence()
drp.mainLoop()
