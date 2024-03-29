#!/usr/bin/env python3 -W ignore::DeprecationWarning
import configparser
import threading
import requests
import time
import os
import json
from datetime import datetime
import numpy as np

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import AppIndicator3, Gtk


utcOffset = time.localtime().tm_gmtoff
currpath = os.path.dirname(os.path.realpath(__file__))


class Datapoint:
    # converts from a json data format from nightscout format to a class instance. This makes it MUCH easier to work with the data
    bsFormat = "mmol/L"
    oldThreshold = 15  # minutes. How old the reading can be before it is categorized as "old". 
    arrowToUnicode = {"Flat": "🢂", "FortyFiveDown": "🢆", "FortyFiveUp": "🢅", "SingleUp":"🢁", "SingleDown":"🢃", "DoubleUp":"🢁🢁", "DoubleDown":"🢃🢃", "NONE":"•"}  # 🠨 🠪 🠩 🠫 ⭦ ⭧ ⭨ ⭩ 🢀 🢂 🢁 🢃 🢄 🢅 🢆 🢇

    def __init__(self, data):
        # assumes data is dict from json
        self.time = datetime.fromtimestamp(data["date"]//1000)
        # print(data)
        try:
            self.direction = data["direction"]
        except:
            self.direction = "NONE"
        
        try:
            self.bs = float(data["sgv"])
        except:
            self.bs = np.nan

        # handle different bs value units
        try:
            self.delta = float(data["delta"])
        except KeyError:
            self.delta = 0

        if self.bsFormat.strip(" ") in ["mmol/L", "mmol/l", "mmoll", "mmolL"]:
            self.bs = round(self.bs/18, 1)
            self.delta = round(self.delta/18, 1)
        else:
            self.delta = int(self.delta)

    def __str__(self):
        deltaPrefix = ""
        
        if self.delta >= 0:
            if str(self.delta).startswith("-"):
                # python quirk allows -0.0 >= 0
                self.delta = np.abs(self.delta)
            deltaPrefix = "+"
        try:
            return f"{self.bs} {self.bsFormat} {deltaPrefix}{self.delta} {self.arrowToUnicode[self.direction]}"
        except KeyError:
            return f"{self.bs} {self.bsFormat} {deltaPrefix}{self.delta} {self.direction}"

    def __eq__(self, other):
        return self.time == other.time

class DataCollector:
    threads = []
    yourSite = ""
    url = ""

    def __init__(self):
        self.onBootData = self.fetch_data(self.url)

        self.data = self.onBootData[::-1]
        # self.run_collector()
        collectorThread = threading.Thread(target=self.run_collector)
        graphThread = threading.Thread(target=self.start_graph)
        self.threads = [collectorThread, graphThread]
        for t in self.threads:
            t.start()

    def start_graph(self):
        # self.graph = Graph(self.data) #graph is disabled for now

        self.menu = Indicator()#self.graph)
        self.menu.update_label(str(self.data[-1]))
        self.menu.update_icon(self.data[-1])
        self.menu.update_last_updated(self.data[-1])
        Gtk.main()

    def fetch_data(self, url):
        # fetches all data from the passed url and takes care of error handling.
        request_results = json.loads(requests.get(url).text)
        

        res = []
        for val in request_results:
            res.append(Datapoint(val))
        return res

    def purge_old_data(self):
        # checks the list of datapoints and purges old values (data that is outside of graph width)
        # we keep values that are 5 minutes too old to be displayed, just for safety in case something messes up
        now = datetime.now()
        for data in self.data:
            if (now - data.time).seconds > 15:#5*60*(Graph.width+1):
                #print(f"deleted {data}, {data.time}")
                del data

    def run_collector(self):
        while True:
            time.sleep(10)  # sleep between each api request
            self.purge_old_data()
            # url = self.url_request_constructor()
            try:
                data_temp = self.fetch_data(self.url)
                data = data_temp
            except requests.exceptions.ConnectionError:
                self.menu.set_error_icon()
                continue

            if data:
                data = data[0]
                if data != self.data[-1]:
                    # make sure the data found is not just the same value as the previous data point
                    self.data.append(data)
                    
            else:
                # this gets called if the request did not retrieve any data point in the requested time window
                # aka, there have been no new data updates in the time window
                pass
            self.menu.update_icon(self.data[-1])
            self.menu.update_label(str(self.data[-1]))
            self.menu.update_last_updated(self.data[-1])
            #self.menu.update_graph()


class Indicator():
    def __init__(self, graph=None):

        #self.graph = graph
        self.app = 'SugarDaddy.app'
        iconpath = currpath+"/media/yellow.png"

        self.indicator = AppIndicator3.Indicator.new(self.app, iconpath,AppIndicator3.IndicatorCategory.OTHER)

        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.create_menu())
        self.indicator.set_label("booting ...", self.app)

    # def update_graph(self):
    #     self.item_graph.set_label(str(self.graph))

    def update_label(self, string):
        self.indicator.set_label(string, self.app)

    def update_icon(self, data):
        # sets the appropriate icon for the given data point
        now = datetime.now()
        filename = ""
        dataPointAge = (now-data.time).seconds/60
        if dataPointAge > Datapoint.oldThreshold:
            filename += "X"
        if data.bs >= HIGH:
            filename += "yellow.png"
        elif HIGH > data.bs > LOW:
            filename += "green.png"
        else:
            filename += "red.png"

        self.indicator.set_icon(currpath+f"/media/{filename}")

    def update_last_updated(self, data):
        time_of_update = data.time.strftime(r"%H:%M:%S")
        time_delta = int(round((datetime.now()-data.time).seconds/60))
        min_suffix = ""
        if time_delta > 1 or time_delta == 0:
            min_suffix = "s"
        self.item_last_update.set_label(
            f"Last update: {time_of_update}, {time_delta} minute{min_suffix} ago")

    def set_error_icon(self):
        icon = str(self.indicator.get_icon())
        for colour in ["green.png", "yellow.png", "red.png"]:
            if icon.endswith(colour):
                self.indicator.set_icon(icon.rstrip(colour)+"X"+colour)
                return 

        # print(self.indicator.get_icon(), self.indicator.get_icon_desc())

    def create_menu(self):
        menu = Gtk.Menu()

       
        self.item_last_update = Gtk.MenuItem(label="Last update:")
        menu.append(self.item_last_update)
        menu.show_all()
        return menu

    def green(self, source):
        self.indicator.set_icon(currpath+"/media/green.png")

    def purple(self, source):
        self.indicator.set_icon(currpath+"/media/red.png")


def setup_config():
    global HIGH, LOW
    configParser = configparser.RawConfigParser()
    configFilePath = currpath + "/setup.conf"
    configParser.read(configFilePath)

    HIGH = float(configParser.get('SugarDaddy-config', 'HIGH'))
    LOW = float(configParser.get('SugarDaddy-config', 'LOW'))
    Datapoint.bsFormat = configParser.get('SugarDaddy-config', 'UNITS')
    DataCollector.url = f"https://{configParser.get('SugarDaddy-config', 'YOUR-SITE')}/api/v1/entries.json?count=1"
    Datapoint.oldThreshold = float(configParser.get(
        'SugarDaddy-config', 'OLD-THRESHOLD'))
   
if __name__ == "__main__":
    setup_config()
    try:
        DataCollector()
    except KeyboardInterrupt:
        for t in DataCollector.threads:
            t.join()
