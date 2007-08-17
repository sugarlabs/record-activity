#Copyright (c) 2007, Media Modifications Ltd.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import gtk
import gobject
import os
import shutil

import xml.dom.minidom

from sugar import util
from sugar.activity import activity
from sugar import profile
from sugar.datastore import datastore

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
		self.ACTIVE = True

		self.nickName = profile.get_nick_name()
		self.basePath = activity.get_bundle_path()
		self.gfxPath = os.path.join(self.basePath, "gfx")
		self.topJournalPath = os.path.join(os.path.expanduser("~"), "Journal", self.activityName)
		if (not os.path.exists(self.topJournalPath)):
			os.makedirs(self.topJournalPath)
		self.journalPath = os.path.join(self.topJournalPath, self.instanceId)
		if (not os.path.exists(self.journalPath)):
			os.makedirs(self.journalPath)
		self.recreateTemp()

		#whoami?
		key = profile.get_pubkey()
		keyHash = util._sha_data(key)
		self.hashedKey = util.printable_hash(keyHash)

		#todo: replace this code to avoid conflicts between multiple instances (tubes?)
		#xmlRpcPort = 8888
		#httpPort = 8889
		h = hash(self.instanceId)
		self.xmlRpcPort = 1024 + (h%32255) * 2
		self.httpPort = self.xmlRpcPort + 1

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


	def read_file(self, file):
		print("read file")
		self.m.fillMediaHash(file)


	def write_file(self, file):
		print("write_file")
		#todo: just pass the file over to the method in m
		f = open( file, "w" )
		album = self.m.updateMediaIndex( True )
		album.writexml(f)
		f.close()


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
		print("active?", self.props.active, self.ACTIVE )
		if (not self.props.active and self.ACTIVE):
			self.stopPipes()
		elif (self.props.active and not self.ACTIVE):
			self.restartPipes()

		self.ACTIVE = self.props.active



	def stopPipes(self):
		#todo: if recording a movie when you leave, stop.  also make sure not to put the video back on display when done.
		print("stop pipes")
		self.gplay.stop()

		if (self.m.RECORDING):
			self.m.stopRecordingVideo()
		else:
			self.glive.stop()


	def restartPipes(self):
		print("restart pipes")
		if (not self.m.UPDATING):
			self.ui.updateModeChange()


	def recreateTemp( self ):
		self.tempPath = os.path.join(self.topJournalPath, "temp")
		if (os.path.exists(self.tempPath)):
			shutil.rmtree( self.tempPath )
		os.makedirs(self.tempPath)


	def close( self ):
		#extend the sugar close method for rapid shutdown that doesn't litter the
		activity.Activity.close( self )
		self.destroyCb( None )


	def destroyCb( self, *args ):
		self.ui.hideLiveWindows()
		self.ui.hidePlayWindows()
		self.gplay.stop()
		self.glive.stop()
		#todo: clean up / throw away any video you might be recording when you quit the activity
		self.recreateTemp()

		if (os.path.exists(self.journalPath)):
			shutil.rmtree( self.journalPath )

		gtk.main_quit()