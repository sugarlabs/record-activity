#!/usr/bin/env python

import gtk
import gobject

from sugar.activity import activity

from glive import LiveVideoSlot
from gplay import PlayVideoSlot
from image_display import Image_Display
from controller import Controller
from thumbnails import Thumbnails
from menubar import MenuBar


class CameraActivity(activity.Activity):
	def __init__(self, handle):
		activity.Activity.__init__(self, handle)
		self.set_title( "Camera" )

		#wait a moment so that our debug console capture mistakes
		gobject.idle_add( self._initme, None )


	def _initme( self, userdata=None ):
		#sizing
		self.c = Controller()
		self.c._frame = self
		self.c.initMesh()

		self.menuBarHt = 75
		self.thumbTrayHt = 150
		imgDisHt = self.c._h-(self.thumbTrayHt+self.menuBarHt)
		self.vidX = ((self.c._w/2)-(self.c.polSvg.props.width/2)) + 15 + 2
		self.vidY = self.menuBarHt + ( (imgDisHt/2) - (self.c.polSvg.props.height/2) ) + 15
		self.set_default_size( self.c._w, self.c._h )

		#layout
		self.fix = gtk.Fixed( )
		self.add( self.fix )

		#menubar
		MenuBar( self.c )
		self.c._mb.set_size_request( self.c._w, self.menuBarHt )

		#self._toolbar = XbookToolbar(self._view)
		#self._toolbar.connect('open-document', self._open_document_cb)
		#self._toolbar.connect('open-document', self._open_document_cb)

		#photos
		Image_Display( self.c )
		self.c._id.set_size_request( self.c._w, imgDisHt )
		#thumbnails
		Thumbnails( self.c, self.c.THUMB_PHOTO )
		self.c._thuPho.set_size_request( self.c._w, self.thumbTrayHt )
		Thumbnails( self.c, self.c.THUMB_VIDEO )
		self.c._thuVid.set_size_request( self.c._w, self.thumbTrayHt )
		#self.c.setup()

		#pack
		self.fix.put(self.c._mb, 0, 0)
		self.fix.put(self.c._id, 0, self.menuBarHt)
		self.fix.put(self.c._thuPho, 0, self.c._h-self.thumbTrayHt)
		self.fix.put(self.c._thuVid, 0, self.c._h-self.thumbTrayHt)
		self.newGlive(False, False)
		self.newGplay()

		self.show_all()
		self.c._thuVid.hide()
		self.c._thuPho.show()
		self.c._playvideo.hide()

		#turn on the live camera
		self.c._livevideo.playa.play()
		self.c.setup()

		self.connect("destroy", self.destroy)
		#self.connect("focus-in-event", self.c.inFocus)
		#self.connect("focus-out-event", self.c.outFocus)
		
		#wrapped up and heading off to play ball
		return False

	def newGlive( self, record, sound ):
		LiveVideoSlot(self.c)
		self.c._livevideo.set_size_request(640, 480)
		self.fix.put(self.c._livevideo, self.vidX, self.vidY)

	def newGplay( self ):
		PlayVideoSlot(self.c)
		self.c._playvideo.set_size_request(640, 480)
		self.fix.put(self.c._playvideo, self.vidX, self.vidY)

	#camera button has gone the way of the dodo
	#def execute(self, command, args):
	#	if (command == "camera"):
	#		self.c.cameraButton()
	#		return True
	#	else:
	#		return False

	def destroy( self, *args ):
		#self.c.outFocus()
		gtk.main_quit()

	def setWaitCursor( self ):
		self.window.set_cursor( gtk.gdk.Cursor(gtk.gdk.WATCH) )

	def setDefaultCursor( self ):
		self.window.set_cursor( None )
