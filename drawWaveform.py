#! /usr/bin/python

#todo: credit and license from arjun & olpc

import pygst
pygst.require("0.10")
import pygtk
import gtk
import cairo
import gobject
from time import *
from struct import *
import pango

import os

import config  	#This has all the globals

import audioop

from Numeric import *
from FFT import *

#Waveform drawing area dimensions
WINDOW_W=1050.0
WINDOW_H=800.0

#In milliseconds, the delay interval after which the waveform draw function will be queued"
REFRESH_TIME = 30

#Multiplied with width and height to set placement of text
TEXT_X_M = 0.55
TEXT_Y_M = 0.83


class DrawWaveform(gtk.DrawingArea):
	def __init__(self):
		gtk.DrawingArea.__init__(self)

		self.connect("expose_event", self.expose)
		self.buffers = []
		self.str_buffer=''
		self.buffers_temp=[]
		self.integer_buffer=[]

		#grabber.connect("new-buffer", self._new_buffer)

		self.peaks = []
		self.main_buffers = []

		self.rms=''
		self.avg=''
		self.pp=''
		self.count=0

		self.param1= config.WINDOW_H/65536.0
		self.param2= config.WINDOW_H/2.0

		self.y_mag = 0.7
		self.freq_range=50
		self.draw_interval = 10
		self.num_of_points = 6200

		self.details_show = False
		self.logging_status=False

		self.stop=False

		self.fft_show = False
		self.fftx = []

		self.y_mag_bias_multiplier = 1	#constant to multiply with self.param2 while scaling values


	def queueDisplayOfNewAudioBuffer( self, buf ):
		self.str_buffer = buf
		self.integer_buffer = list(unpack( str(int(len(buf))/2)+'h' , buf))
		if(len(self.main_buffers)>=24600):
			del self.main_buffers[0:(len(self.main_buffers)-12601)]
		self.main_buffers += self.integer_buffer


	def startWaveformDraws( self ):
		self.WAVEFORM_TIMEOUT_ID = gobject.timeout_add(config.REFRESH_TIME, self.waveform_refresh)


	def stopWaveformDraws( self ):
		#todo: remove the timeout here...
		pass


	def waveformRefresh( self ):
		self.queue_draw()
		return True

	#######################################################################
	# This function is the "expose" event handler and does all the drawing
	#######################################################################
	def expose(self, widget, event):

		###############REAL TIME DRAWING##########################################
		if(self.logging_status==False):
			if(self.stop==False):

				if(self.fft_show==False):

					######################filtering####################
					if(self.logging_status==False):		#we dont want to apply filtering on the values read from a file
						weights = [1,2,3,4,3,2,1]
						weights_sum = 16.0

						for i in range(3,len(self.integer_buffer)-3):
							self.integer_buffer[i] = (self.integer_buffer[(i-3)]+2*self.integer_buffer[(i-2)] + 3*self.integer_buffer[(i-1)] + 4*self.integer_buffer[(i)]+3*self.integer_buffer[(i+1)] + 2*self.integer_buffer[(i+2)]  + self.integer_buffer[(i+3)]) / weights_sum
					###################################################

					self.y_mag_bias_multiplier=1
					self.draw_interval=10
					#50hz
					if(self.freq_range==20):
						self.spacing = 120
						self.num_of_points=12600

					#100hz
					elif(self.freq_range==30):
						self.spacing = 60
						self.num_of_points=6300

					#500hz
					elif(self.freq_range==40):
						self.spacing = 12
						self.num_of_points=1260

					#1khz
					elif(self.freq_range==50):
						self.spacing = 6
						self.num_of_points=630

					#2khz
					elif(self.freq_range==60):
						self.spacing = 2
						self.num_of_points=210

					#4khz
					elif(self.freq_range==70):
						self.spacing = 1
						self.num_of_points = 105

					if(len(self.main_buffers)>=self.num_of_points):
						del self.main_buffers[0:len(self.main_buffers)-(self.num_of_points+1)]
						self.buffers=[]
						i=0
						while i<self.num_of_points:
							self.buffers.append(self.main_buffers[i])
							i+=self.spacing

				else:
					###############fft################
					Fs = 48000
					nfft= 65536
					self.integer_buffer=self.integer_buffer[0:256]
					self.fftx = fft(self.integer_buffer, 256,-1)

					self.fftx=self.fftx[0:self.freq_range*2]
					self.draw_interval=config.WINDOW_W/(self.freq_range*2)

					NumUniquePts = ceil((nfft+1)/2)
					self.buffers=abs(self.fftx)*0.02
					self.y_mag_bias_multiplier=0.1
					##################################

		if(len(self.buffers)==0):
			return False


		###############Scaling the values################
		val=[]
		for i in self.buffers:
			temp_val_float = float(self.param1*i*self.y_mag) + self.y_mag_bias_multiplier * self.param2

			if(temp_val_float>=config.WINDOW_H):
				temp_val_float= config.WINDOW_H
			if(temp_val_float<=0):
				temp_val_float= 0
			val.append( temp_val_float  )

		self.peaks=val
		#################################################

		#Create context, disable antialiasing
		self.context = widget.window.cairo_create()
		self.context.set_antialias(cairo.ANTIALIAS_NONE)

		#set a clip region for the expose event. This reduces redrawing work (and time)
		self.context.rectangle(event.area.x, event.area.y,event.area.width, event.area.height)
		self.context.clip()


		#self.context.set_source_surface(self.overlay_surface,0,0)
		#self.context.paint()

		###########background#######################
		self.context.set_source_rgb(0,0,0)
		self.context.rectangle(0,0,config.WINDOW_W ,config.WINDOW_H)
		self.context.fill()
		#############################################


		############grid#############################
		self.context.set_line_width(0.4)
		self.context.set_source_rgb(0.2,0.2,0.2)

		x=0
		y=0
		for j in range(1,22):
			self.context.move_to(x,y)
			self.context.rel_line_to(0,config.WINDOW_H)
			x=x+50

		self.context.set_line_width(1.0)
		x=0
		y=0
		for j in range(1,17):
			self.context.move_to(x,y)
			self.context.rel_line_to(config.WINDOW_W,0)
			y=y+50


		self.context.stroke()
		#############################################


		############Draw the waveform##############
		count = 0
		for peak in self.peaks:
			self.context.line_to(count,config.WINDOW_H - peak)
			count=count + self.draw_interval
		self.context.set_line_width(2.0)
		self.context.set_source_rgb(0, 1, 0)
		self.context.stroke()
		############################################


		###########Text Display#####################
		if (self.details_show == True):
			if(self.count%65==0):
				self.rms=str( audioop.rms( self.str_buffer,2) )
				self.avg=str(audioop.avg( self.str_buffer,2))
				self.pp=str(audioop.avgpp(self.str_buffer,2))
			self.count+=1
			if(self.count==65536):
				self.count=0

			self.pango_context = self.create_pango_context()
			font_desc = pango.FontDescription('Serif 8')
			layout = pango.Layout(self.pango_context)
			layout.set_font_description(font_desc)

			self.context.move_to((int)(config.TEXT_X_M*config.WINDOW_W), (int)(config.TEXT_Y_M*config.WINDOW_H))
			layout.set_text("RMS: "+ self.rms +"  AVG: "+ self.avg + "  PK-PK: " + self.pp)

			self.context.set_source_rgb(0,0,1)
			self.context.show_layout(layout)
		############################################

		return True

