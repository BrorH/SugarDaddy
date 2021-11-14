#!/usr/bin/env python3 -W ignore::DeprecationWarning
import configparser
import threading
import requests
import time
import os
import json
from datetime import datetime, timedelta
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
    arrowToUnicode = {"Flat": "🢂"}  # 🠨 🠪 🠩 🠫 ⭦ ⭧ ⭨ ⭩ 🢀 🢂 🢁 🢃 🢄 🢅 🢆 🢇

    def __init__(self, data):
        # assumes data is dict from json
        self.time = datetime.fromtimestamp(data["date"]//1000)
        self.direction = data["direction"]
        self.bs = float(data["sgv"])

        # handle different bs value units
        try:
            self.delta = float(data["delta"])
        except KeyError:
            self.delta = 0

        if self.bsFormat == "mmol/L":
            self.bs = round(self.bs/18, 1)
            self.delta = round(self.delta/18, 1)
        else:
            self.delta = int(self.delta)

    def __str__(self):
        deltaPrefix = ""
        if self.delta >= 0:
            deltaPrefix = "+"
        try:
            return f"{self.bs} {self.bsFormat} {deltaPrefix}{self.delta} {self.arrowToUnicode[self.direction]}"
        except KeyError:
            return f"{self.bs} {self.bsFormat} {deltaPrefix}{self.delta} {self.direction}"

    def __eq__(self, other):
        return self.time == other.time


class Graph:
    width = 70
    columnHeight = 35
    maxBS = 10 
    minBS = 1 

    def __init__(self, data):
        self.data = np.array(data)

    def __setitem__(self, idx, val):
        self.data[idx] = val

    def __getitem__(self, idx):
        return self.data[idx]

    def __str__(self):
        # generates the layered string which displays the BS graph

        # WIP
        res = "¹º"
        i = 0
        for j in range(self.width):
            val = self.data[i].bs
            #timestamp = self.data[i].time 

            #earliest_time = datetime.now()+timedelta(minutes=5*(-self.width+j))
            #latest_time = earliest_time + timedelta(minutes=6)
            #print(f"\n{j}: {earliest_time.strftime(r'%H:%M:%S')}. {i}: {timestamp.strftime(r'%H:%M:%S')} ",end ="")
            # print(timestamp, earliest_time, latest_time)

            column = [u"\u0323"]*self.columnHeight
            # Finds the corresponding column index of the data value.
            # But only if the measurement time, timestamp, was within the 
            # corresponding time window which the graph point corresponds to
            if True:#earliest_time <= timestamp <= latest_time:
                i += 1
                if self.minBS <= val <= self.maxBS:
                    idx = int(round((val-self.minBS) *
                                    self.columnHeight/(self.maxBS-self.minBS)))
                    column[idx] = u"\u033B"
            res += "".join(column[::-1]) + u"\u2005"
        return res


class DataCollector:
    threads = []
    yourSite = ""

    def __init__(self):
        # on boot, gather enough data to backfill log
        onBootURL = self.url_request_constructor(
            count=Graph.width, dt=5*(Graph.width + 5))
        self.onBootData = self.fetch_data(onBootURL)

        self.data = self.onBootData[::-1]

        collectorThread = threading.Thread(target=self.run_collector)
        graphThread = threading.Thread(target=self.start_graph)
        self.threads = [collectorThread, graphThread]
        for t in self.threads:
            t.start()

    def start_graph(self):
        self.graph = Graph(self.data)

        self.menu = Indicator(self.graph)
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
            if (now - data.time).seconds > 5*60*(Graph.width+1):
                print(f"deleted {data}, {data.time}")
                del data

    def url_request_constructor(self, count=1, dt=6):
        # constructs the url which appropriately sends a request to the api for a datapoint within a given time window, dt
        # the time window is dt in minutes
        now = datetime.now() - timedelta(seconds=utcOffset)

        nowStr = now.strftime(r"%Y-%m-%dT%H:%M:%S")
        thenStr = (now-timedelta(minutes=dt)).strftime(r"%Y-%m-%dT%H:%M:%S")
        res = rf"https://{self.yourSite}/api/v1/entries.json?count={count}&find[dateString][$gte]={thenStr}&find[dateString][$lte]={nowStr}"
        return res

    def run_collector(self):
        while True:
            time.sleep(10)  # sleep between each api request
            self.purge_old_data()
            url = self.url_request_constructor()
            data = self.fetch_data(url)

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
            self.menu.update_graph()


class Indicator():
    def __init__(self, graph):

        self.graph = graph
        self.app = 'SugarDaddy.app'
        iconpath = currpath+"/media/yellow.png"

        self.indicator = AppIndicator3.Indicator.new(self.app, iconpath,AppIndicator3.IndicatorCategory.OTHER)

        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.create_menu())
        self.indicator.set_label("booting ...", self.app)

    def update_graph(self):
        self.item_graph.set_label(str(self.graph))

    def update_label(self, string):
        self.indicator.set_label(string, self.app)

    def update_icon(self, data):
        # sets the appropriate icon for the passed data point
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

    def create_menu(self):
        menu = Gtk.Menu()

        # create the graph bar
        self.item_graph = Gtk.MenuItem(label=str(self.graph))
        menu.append(self.item_graph)

        # create a couple empty dummy bars
        for i in range(3):
            menu.append(Gtk.MenuItem(label=""))

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
    DataCollector.yourSite = configParser.get('SugarDaddy-config', 'YOUR-SITE')
    print(DataCollector.yourSite)
    Datapoint.oldThreshold = float(configParser.get(
        'SugarDaddy-config', 'OLD-THRESHOLD'))
    Graph.maxBS = float(configParser.get('SugarDaddy-config', 'GRAPH-MAX'))
    Graph.minBS = float(configParser.get('SugarDaddy-config', 'GRAPH-MIN'))


if __name__ == "__main__":
    setup_config()
    try:
        DataCollector()
    except KeyboardInterrupt:
        for t in DataCollector.threads:
            t.join()
