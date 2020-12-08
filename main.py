#!/usr/bin/env python3 -W ignore::DeprecationWarning
import signal, gi, os, json, requests, subprocess
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GObject,GdkPixbuf, GLib
from threading import Thread
from datetime import datetime, timedelta
import numpy as np
from time import sleep
from graph import Graph

#todo:
# add "fetch now"-button
# add timer to next fetch
# add color to text
# add alarm at (very) high levels
# make next update happen 5 minutes after last data 
# compatible timezone automatically
# make get_month_start_time_from_datfile function use regex
dt_timezone = 1 # how many hours ahead your timezone is of GMT


class Data:
	def __init__(self, indicator, val=None, time=None):
		self.IC = indicator
		self.val = val 
		self.time = time
		
	
	def __eq__(self, other):
		try:
			if self.val == other.val:
				if np.abs((self.time - other.time).seconds) < 10:
					return True 
		except:
			return False
		return False
	
	def extract(self, **kwargs):
		# kwargs must contain "idx" or "time"
		# if "idx" is passed, the data stored -idx up the data list is retrieved
		# if "time" is passed, the value at the closest time (within 1 minute) is returned
		logpath = self.IC.logpath
		with open(logpath, "r+") as file:
			lines = file.readlines()
		
		if "idx" in kwargs.keys():
			idx = int(kwargs["idx"])
			try:
				dat = lines[-idx].split(" ")
				month_start = self.IC.get_month_start_time_from_datfile(logpath)
				time = month_start + timedelta(seconds = int(dat[0]),hours=dt_timezone)
				self.time = time
				self.val = float(dat[-1])
				return self
				
			except IndexError:
				self.time = datetime.utcfromtimestamp(0)
				self.val = 0
				return False
		else:
			return False



class Indicator():
	base_path = os.path.dirname(os.path.abspath(__file__))
	def __init__(self):
		self.app = 'BrorBS'
		
		self.last_update = "−−  "
		self.delta = "−−"
		self.last_update_menu = None
		self.delta_menu = None
		self.base_path = os.path.dirname(os.path.realpath(__file__))
		self.indicator = AppIndicator3.Indicator.new(self.app, "...",AppIndicator3.IndicatorCategory.OTHER)
		self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)	   
		self.indicator.set_menu(self.create_menu())
		self.indicator.set_label("booting ...", self.app)

		self.update()
		GLib.timeout_add_seconds(5, self.update)



	def update(self):
		self.update_bs()
		self.graph.update()

		return True


	def create_menu(self):
		menu = Gtk.Menu()
		
		last_update_item= Gtk.MenuItem(label=f'Last update: {self.last_update}')
		self.last_update_menu = last_update_item
		menu.append(last_update_item)

		delta_item= Gtk.MenuItem(label=f'Delta: {self.delta}')
		self.delta_menu = delta_item
		menu.append(delta_item)
	
		self.graph = Graph(self,72,40)
		
		
		graph_menu_item = Gtk.MenuItem(label=str(self.graph))
		self.graph_menu_item = graph_menu_item
		menu.append(self.graph_menu_item)
		
		for num in ["⁸", "⁶",  "²"]:
			foo_menu_item = Gtk.MenuItem(label=num)
			menu.append(foo_menu_item)
	

		menu.show_all()
		return menu
	
	@property
	def logpath(self):
		now = datetime.now()
		try:
			logpath = f"{self.base_path}/logs/{now.year}/{now.month}.dat"
			assert os.path.exists(logpath) # to raise evt. error
			return logpath
		except AssertionError:
			if not os.path.exists(self.base_path +f"/logs/{now.year}"):
				subprocess.run(["mkdir", f"{self.base_path}/logs/{now.year}"])
			if not os.path.exists(self.base_path +f"/logs/{now.year}/{now.month}.dat"):
				subprocess.run(["touch", f"{self.base_path}/logs/{now.year}/{now.month}.dat"])
			return self.logpath
		
	@property
	def prev_val(self):
		#returns previous stored bs val
		with open(self.logpath, "r+") as file:
			lines = file.readlines()
		try:
			lastval = lines[-1].split(" ")
			lasttime = datetime.strptime(lastval[0], r"%H:%M:%S")
			lasttime = datetime.now().replace(hour=lasttime.hour, minute=lasttime.minute, second=lasttime.second, microsecond=0)
			return lasttime, float(lastval[-1])
		except IndexError:
			return None

	def get_month_start_time_from_datfile(self, datfile):
		# returns the EPOCH time of the start of the month for datafile
		stripped = datfile[:datfile.rindex(".dat")]
		month = int(stripped[stripped.rindex("/")+1:])
		stripped = stripped[:stripped.rindex("/")]
		year = int(stripped[-4:])
		month_start_time = datetime.strptime(f"{year}:{month}", r"%Y:%m")
		return month_start_time

	def log_write(self, msg, time):
		# write to log
		epoch = datetime.utcfromtimestamp(0)
		month_start = datetime.now().replace(day=1, hour = 0,minute=0, second=0, microsecond=0)
		month_start_seconds = int(round((month_start-epoch).total_seconds()))
		sec_since_month_start = time -month_start_seconds
		with open(self.logpath, "a+") as file:
			file.write(f"{sec_since_month_start} {msg}\n")

		


	def update_bs(self):
		# checks json file for when last data was read from transmitter and creates a timed schedule accordingly
		try:
			response = requests.get("https://sugarmate.io/api/v1/qajqju/latest.json")
			resp = json.loads(response.text)
		except:
			return
		
		timestamp = resp["timestamp"]
		timestamp = datetime.strptime(timestamp[:timestamp.rindex(".")], r"%Y-%m-%dT%H:%M:%S")
		timestamp = timestamp + timedelta(hours = dt_timezone)
		x = resp["x"]
		reading = resp["reading"]
		bsval = resp["mmol"]
		trend_symbol = str(resp["trend_symbol"])

		# Udpate Delta label
		try:
			delta = str(resp["delta_mmol"]).replace("-","−")
			if not delta.startswith("-"):
				delta = " +" + delta
		except Exception as e:
			delta = " −−"
		self.delta_menu.set_label(f"Delta: {delta}")
		sleep(0.01) #multithread needs time to update

		# Update "last update" label
		self.last_update_menu.set_label(f"Last update:  {resp['time']}   ") 

		bsstr = str(bsval)+" mmol/L " + trend_symbol  #blood sugar string to fill the main label
		
		read_data = Data(self, val=float(bsval), time=timestamp)
		prev_stored_data = Data(self).extract(idx=1)
		
		if bsval >= 8:
			icon = "orange.png"
		elif 3.9<= bsval < 8:
			icon = "green.png"
		else:
			icon = "red.png"

		try:
			if not (read_data == prev_stored_data):
				self.log_write(bsval, x)
		except AttributeError:
			self.log_write(bsval, x)
		
		try:
			dt = (datetime.now()-prev_stored_data.time).seconds
		except AttributeError:
			dt = 0
		if reading.endswith("[OLD]") or dt >= 60*20:
			icon = "X" + icon
		
		GLib.idle_add(self.indicator.set_label,bsstr, self.app,priority=GLib.PRIORITY_DEFAULT) #update top label
		self.indicator.set_icon(self.base_path+"/media/"+icon)
		del read_data, prev_stored_data #free memory

		

	

	def ASCII_loader(self, boot=False):
		self.loader_frames = ['▁','▃','▄','▅','▆','▇','█','▇','▆','▅','▄','▃',"▁", " "]		
		return True
	
			

	def stop(self, source):
		Gtk.main_quit()

Indicator()
signal.signal(signal.SIGINT, signal.SIG_DFL)
Gtk.main()
