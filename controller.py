#!/usr/bin/env python

import string
import fnmatch
import os
import random
import cairo
import gtk
import pygtk
pygtk.require('2.0')
import rsvg
import re
import math
import gtk.gdk
import sugar.env
import random
import _sugar
import time
from sugar import profile
from sugar.activity import activity

from color import Color
from polygon import Polygon

class Controller:

	def __init__(self, w, h):
		#our dirs
		#self._basepath = os.path.dirname(os.path.abspath(__file__))
		self._basepath = activity.get_bundle_path()
		pic_path = sugar.env.get_profile_path()
		self.pic_path = os.path.join(os.path.dirname(pic_path), 'camera_stuff')
		if (not os.path.exists( self.pic_path )):
			os.mkdir( self.pic_path )

		self._colBlack = Color( 0, 0, 0, 255 )
		self._colWhite = Color( 255, 255, 255, 255 )
		self._colThumbTray = Color( 224, 224, 224, 255 )

		self._w = w
		self._h = h

		#the current image
		self._img = None

		#container
		self._frame = None
		#img display
		self._id = None
		#video slot for live video
		self._livevideo = None
		#thumbs
		self._thumbs = None

		#load svgs
		polSvg_f = open( os.path.join(self._basepath, 'polaroid.svg'), 'r' )
		polSvg_d = polSvg_f.read()
		polSvg_f.close()
		self.polSvg = self.loadSvg( polSvg_d, None, None )

		camSvg_f = open( os.path.join(self._basepath, 'shutter_button.svg'), 'r' )
		camSvg_d = camSvg_f.read()
		camSvg_f.close()
		self.camSvg = self.loadSvg( camSvg_d, None, None )
		
		camInvSvg_f = open( os.path.join(self._basepath, 'shutter_button_invert.svg'), 'r' )
		camInvSvg_d = camInvSvg_f.read()
		camInvSvg_f.close()
		self.camInvSvg = self.loadSvg( camInvSvg_d, None, None )

		butSvg_f = open( os.path.join(self._basepath, 'thumb_polaroid.svg'), 'r' )
		butSvg_d = butSvg_f.read()
		color = profile.get_color()
		fill = color.get_fill_color()
		stroke = color.get_stroke_color()
		self.thumbSvg = self.loadSvg( butSvg_d, stroke, fill )
		butSvg_f.close()

		closeSvg_f = open( os.path.join(self._basepath, 'thumb_close.svg'), 'r' )
		closeSvg_d = closeSvg_f.read()
		self.closeSvg = self.loadSvg( closeSvg_d, "#515151", fill )
		closeSvg_f.close()


	def loadSvg( self, data, stroke, fill ):
		if ((stroke == None) or (fill == None)):
			return rsvg.Handle( data=data )

		entity = '<!ENTITY fill_color "%s">' % fill
		data = re.sub('<!ENTITY fill_color .*>', entity, data)

		entity = '<!ENTITY stroke_color "%s">' % stroke
		data = re.sub('<!ENTITY stroke_color .*>', entity, data)

		return rsvg.Handle( data=data )


	def getBasePath( self ):
		return self._basepath


	def takeSnapshot( self ):
		self._livevideo.takeSnapshot()


	def setPic( self, pixbuf ):
		nowtime = int(time.time())
		nowtime_s = str(nowtime)
		nowtime_fn = nowtime_s + ".jpg"
		imgpath = os.path.join( self.pic_path, nowtime_fn )
		pixbuf.save( imgpath, "jpeg" )

		img = _sugar.cairo_surface_from_gdk_pixbuf(pixbuf)
		self._thumbs.addThumb( img, imgpath )


	def showImg(self, imgPath):
		if (self._img == None):
			sx = (self._id._w/2)-(self.camSvg.props.width/2)
			sy = ((self._id._h/2)-(self.polSvg.props.height/2)) + 15 + 480 + 15
			self._frame.fix.move( self._livevideo, sx, sy )
			self._livevideo.set_size_request( 160, 120 )
			self._livevideo.hide()

		pixbuf = gtk.gdk.pixbuf_new_from_file( imgPath )
		self._img = _sugar.cairo_surface_from_gdk_pixbuf(pixbuf)
		self._id.redraw()


	def showVid(self):
		lv_x = ((self._w/2)-(self.polSvg.props.width/2))+15+1
		lv_y = (((self._h-self._frame.thumbTrayHt)/2)-(self.polSvg.props.height/2))+15
		self._frame.fix.move( self._livevideo, lv_x, lv_y )
		self._livevideo.set_size_request( 640, 480 )
		self._livevideo.show()
		self._img = None
		self._id.redraw()