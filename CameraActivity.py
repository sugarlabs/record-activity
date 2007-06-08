#!/usr/bin/env python

import gtk
import gobject

from sugar.activity import activity

from controller import Controller
from ui import UI
from mesh import MeshClient
from mesh import MeshXMLRPCServer
from mesh import HttpServer

class CameraActivity(activity.Activity):
	def __init__(self, handle):
		activity.Activity.__init__(self, handle)
		self.name = "camera";
		self.set_title( self.name )
		#wait a moment so that our debug console capture mistakes
		gobject.idle_add( self._initme, None )

	def _initme( self, userdata=None ):
		self.basePath = activity.get_bundle_path()
		self.gfxPath = os.path.join(self.basePath, "gfx")
		self.journalPath = os.path.join(os.path.expanduser("~"), "Journal", self.name)
		if (not os.path.exists(self.journalPath)):
			os.makedirs(self.journalPath)

		self.c = Controller( self )
		self.ui = UI( self )

		#listen for meshins
		self.connect( "shared", self._shared_cb )
		self.connect( "destroy", self.destroy)
		#todo: proper focus listeners to turn camera on / off
		#self.connect("focus-in-event", self.c.inFocus)
		#self.connect("focus-out-event", self.c.outFocus)

		#share, share alike
		#if the prsc knows about an act with my id on the network...
		if self._shared_activity:
			#have you joined or shared this activity yourself?
			if self.get_shared():
				print("in get_shared() 1")
				self.startMesh()
				print("in get_shared() 2")
			else:
				print("! in get_shared() 1")
				# Wait until you're at the door of the party...
				self.connect("joined", self._joined_cb)
				print("! in get_shared() 2")

		print("leaving constructor")
		self.c.initPostUI()
		return False

	def _shared_cb( self, activity ):
		print("1 i am shared")
		self.startMesh()
		print("2 i am shared")

	def _joined_cb( self, activity ):
		print("1 i am joined")
		self.startMesh()
		print("2 i am joined")

	def startMesh( self ):
		print( "1 startMesh" );
		self.httpServer = HttpServer(self)
		print( "2 startMesh" );
		self.meshClient = MeshClient(self)
		print( "3 startMesh" );
		self.meshXMLRPCServer = MeshXMLRPCServer(self)
		print( "4 startMesh" );

#	def inFocus( self, widget, event ):
#		if (self.SHOW == self.SHOW_LIVE):
#			self._livevideo.playa.play()
#		if (self.SHOW == self.SHOW_PLAY):
#			self._playvideo.playa.play()

#	def outFocus( self, widget, event ):
#		if (self.SHOW == self.SHOW_LIVE):
#			self._livevideo.playa.stop()
#		if (self.SHOW == self.SHOW_PLAY):
#			self._playvideo.playa.stop()

	def destroy( self, *args ):
		#self.c.outFocus()
		gtk.main_quit()

	#filestore, etc.
