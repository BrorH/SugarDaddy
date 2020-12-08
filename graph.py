import numpy as np
from datetime import datetime, timedelta
import time
import scipy.interpolate as pol
dt_timezone = 1
class Graph:
	def __init__(self, indicator, width, height,bs_max=10, bs_min=1):
		self.IC = indicator
		self.width = width
		self.height = height
		self.data = np.zeros([width, height])
		self.bs_max = bs_max 
		self.bs_min = bs_min
	
	def __setitem__(self, idx, val):
		self.data[idx] = val 
	
	def __getitem__(self, idx):
		return self.data[idx]
	
	def __str__(self):
		result = "¹º"
		for col in range(self.width):
			string = "."
			for val in self.data[::-1][col]:
				if not val:
					string += u"\u0323"
				else:
					string += u"\u033B"
				
			result += string[::-1]
		return result
	
	

	def get_dt(self, string, logpath):
		#returns a list of time intervals (in sizes of 5 minutes) since data points were logged
		string = string[2:-1] #convert from bytes to string
		now = datetime.now()
		month_start = self.IC.get_month_start_time_from_datfile(logpath)
		data_read_time = month_start +timedelta(seconds = int(string), hours=dt_timezone) 
		dt = int( round(( (now - data_read_time).seconds)//300) )		
		
		return dt
	
	


	def update(self):
		self.data = np.zeros([self.width, self.height]) # clean data
		
		logpath = self.IC.logpath
		data = np.loadtxt(logpath, delimiter=" ", converters={0:lambda s: self.get_dt(str(s),logpath)})
		bsdata = np.zeros(self.width)
		if len(data.shape) == 1:
			bsdata[int(data[0])] = data[1]

		else:
			for i,(dt,bs) in enumerate(zip(data[:,0][::-1], data[:,1][::-1])):
				dt = int(dt)
				if i >= len(bsdata): break
				try: bsdata[dt] = bs
				except: pass
		
		
		for x,bs in enumerate(bsdata):
			y = int(bs*self.height/(self.bs_max-self.bs_min))
			self[x,y] = bs

		self.IC.graph_menu_item.set_label(str(self))	
		time.sleep(0.05)