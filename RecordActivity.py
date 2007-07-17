#!/usr/bin/env python

import gtk
import gobject
import os
from sugar import util

from sugar.activity import activity
from sugar import profile

from model import Model
from ui import UI
from mesh import MeshClient
from mesh import MeshXMLRPCServer
from mesh import HttpServer
from glive import Glive
from gplay import Gplay

class RecordActivity(activity.Activity):
	def __init__(self, handle):
		activity.Activity.__init__(self, handle)
		self.activityName = "Record"
		self.set_title( self.activityName )
		#wait a moment so that our debug console capture mistakes
		gobject.idle_add( self._initme, None )

	def _initme( self, userdata=None ):
		self.instanceId = self._activity_id

		self.nickName = profile.get_nick_name()
		self.basePath = activity.get_bundle_path()
		self.gfxPath = os.path.join(self.basePath, "gfx")
		self.topJournalPath = os.path.join(os.path.expanduser("~"), "Journal", self.activityName)
		if (not os.path.exists(self.topJournalPath)):
			os.makedirs(self.topJournalPath)
		self.journalPath = os.path.join(self.topJournalPath, self.instanceId)
		if (not os.path.exists(self.journalPath)):
			os.makedirs(self.journalPath)

		#whoami?
		key = profile.get_pubkey()
		key_hash = util._sha_data(key)
		self.hashed_key = util.printable_hash(key_hash)

		self.httpServer = None
		self.meshClient = None
		self.meshXMLRPCServer = None
		self.glive = Glive( self )
		self.gplay = Gplay( self )
		self.m = Model( self )
		self.ui = UI( self )

		#listen for meshins
		self.connect( "shared", self.sharedCb )
		self.connect( "destroy", self.destroyCb)

		#todo: proper focus listeners to turn camera on / off
		#self.connect("focus-in-event", self.c.inFocus)
		#self.connect("focus-out-event", self.c.outFocus)
		self.connect( "notify::active", self.activeCb )

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
				self.connect("joined", self.meshJoinedCb)
				print("! in get_shared() 2")

		print("leaving constructor")
		self.m.selectLatestThumbs(self.m.TYPE_PHOTO)
		return False


	def sharedCb( self, activity ):
		print("1 i am shared")
		self.startMesh()
		print("2 i am shared")

	def meshJoinedCb( self, activity ):
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

	def activeCb( self, widget, pspec ):
		print("active?", self.props.active )

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

	def destroyCb( self, *args ):
		#self.m.outFocus()
		#close all pipelines, otherwise they linger when the rest of the activity is long gone
		self.gplay.stop()
		self.glive.stop()
		#todo: clean up / throw away any video you might be recording when you quit the activity
		gtk.main_quit()