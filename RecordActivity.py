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

import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse

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

		self.I_AM_CLOSING = False
		self.I_AM_SAVED = False

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
		self.connect( "shared", self._sharedCb )
		self.connect( "notify::active", self._activeCb )

		#share, share alike
		#if the prsc knows about an act with my id on the network...
		if self._shared_activity:
			#have you joined or shared this activity yourself?
			if self.get_shared():
				self.startMesh()
			else:
				self.connect("joined", self._meshJoinedCb)

		self.m.selectLatestThumbs(self.m.TYPE_PHOTO)

		return False


	def read_file(self, file):
		print("read file 1")
		self.m.fillMediaHash(file)
		print("read file 2")

	def write_file(self, file):
		print("write_file 1")
		self.I_AM_SAVED = False
		SAVING_AT_LEAST_ONE = False

		xmlFile = open( file, "w" )
		impl = getDOMImplementation()
		album = impl.createDocument(None, "album", None)
		root = album.documentElement

		for type,value in self.m.mediaTypes.items():
			typeName = value["name"]
			hash = self.m.mediaHashs[type]

			for i in range (0, len(hash)):
				recd = hash[i]
				mediaEl = album.createElement( typeName )
				root.appendChild( mediaEl )
				recd.savedXml = False
				recd.savedMedia = False
				self.save( xmlFile, mediaEl, recd )



	def save( self, xmlFile, el, recd ):
		print("save 1")

		#presume we don't need to serialize...
		needToDatastoreMedia = False

		if ( (recd.buddy == True) and (recd.datastoreId == None) and (not recd.downloadedFromBuddy) ):
			pixbuf = recd.getThumbPixbuf( )
			buddyThumb = str( self._get_base64_pixbuf_data(pixbuf) )
			el.setAttribute("buddyThumb", buddyThumb )
			recd.savedMedia = True
			self.saveXml( xmlFile, el, recd )
		else:
			recd.savedMedia = False
			needToDatastoreMedia = self.saveMedia( xmlFile, el, recd )


	def saveXml( self, xmlFile, el, recd ):
		print( "1 saveXML" )

		el.setAttribute("type", str(recd.type))

		if (recd.type == self.m.TYPE_AUDIO):
			aiPixbuf = recd.getAudioImagePixbuf( )
			aiPixbufString = str( self._get_base64_pixbuf_data(aiPixbuf) )
			el.setAttribute("audioImage", aiPixbufString)

		el.setAttribute("title", recd.title)
		el.setAttribute("time", str(recd.time))
		el.setAttribute("photographer", recd.photographer)
		el.setAttribute("colorStroke", str(recd.colorStroke.hex) )
		el.setAttribute("colorFill", str(recd.colorFill.hex) )
		el.setAttribute("hashKey", str(recd.hashKey))
		el.setAttribute("buddy", str(recd.buddy))
		el.setAttribute("mediaMd5", str(recd.mediaMd5))
		el.setAttribute("thumbMd5", str(recd.thumbMd5))
		el.setAttribute("mediaBytes", str(recd.mediaBytes))
		el.setAttribute("thumbBytes", str(recd.thumbBytes))
		if (recd.datastoreId != None):
			el.setAttribute("datastoreId", str(recd.datastoreId))

		recd.savedXml = True
		self.checkDestroy( el.ownerDocument, xmlFile )
		print("2 saveXML" )


	def saveMedia( self, xmlFile, el, recd ):
		print("saveMedia 1")
		#note that we update the recds that go through here to how they would
		#look on a fresh load from file since this won't just happen on close()

		if (recd.datastoreId != None):
			#already saved to the datastore, don't need to re-rewrite the file since the mediums are immutable
			#However, they might have changed the name of the file
			if (recd.titleChange):
				#todo: fix!  this doesn't work as of 556...
#				self.loadMediaFromDatastore( recd )
#				#todo: handle none mediaOb
#				if (recd.datastoreOb.metadata['title'] != recd.title):
#					recd.datastoreOb.metadata['title'] = recd.title
#					datastore.write(recd.datastoreOb)
#					if (self.I_AM_CLOSING):
#						recd.datastoreOb.destroy()
#						del recd.datastoreOb
				pass

				#reset for the next title change if not closing...
				recd.titleChange = False
				#save the title to the xml
				recd.savedMedia = True
				self.saveXml( xmlFile, el, recd )

			return

		#this will remove the media from being accessed on the local disk since it puts it away into cold storage
		#therefore this is only called when write_file is called by the activity superclass
		print("saveMedia 2")
		mediaObject = datastore.create()
		print("saveMedia 3")
		#todo: what other metadata to set?
		mediaObject.metadata['title'] = recd.title
		#jobject.metadata['keep'] = '0'
		#jobject.metadata['buddies'] = ''

		pixbuf = recd.getThumbPixbuf()
		thumbData = self._get_base64_pixbuf_data(pixbuf)
		mediaObject.metadata['preview'] = thumbData

		colors = str(recd.colorStroke.hex) + "," + str(recd.colorFill.hex)
		mediaObject.metadata['icon-color'] = colors

		#todo: use dictionary here
		if (recd.type == self.m.TYPE_PHOTO):
			mediaObject.metadata['mime_type'] = 'image/jpeg'
		elif (recd.type == self.m.TYPE_VIDEO):
			mediaObject.metadata['mime_type'] = 'video/ogg'
		elif (recd.type == self.m.TYPE_AUDIO):
			mediaObject.metadata['mime_type'] = 'audio/ogg'

		#todo: make sure the file is still available before you ever get to this point...
		mediaFile = recd.getMediaFilepath(False)
		mediaObject.file_path = mediaFile

		print("saveMedia 4")
#		dcbw:
#		datastore.write(mediaObject, 	reply_handler=lambda *args: self._mediaSaveCb(recd, *args),
#										error_handler=lambda *args: self._mediaSaveErrorCb(recd, *args) );

#		jedierikb:
#		datastore.write(mediaObject, 	reply_handler=(lambda: self._mediaSaveCb(recd)),
#										error_handler=(lambda: self._mediaSaveErrorCb(recd))	);

		datastore.write( mediaObject )
		self.doPostMediaSave( xmlFile, el, recd, mediaObject )


	def _get_base64_pixbuf_data(self, pixbuf):
		data = [""]
		pixbuf.save_to_callback(self._save_data_to_buffer_cb, "png", {}, data)

		import base64
		return base64.b64encode(str(data[0]))


	def _save_data_to_buffer_cb(self, buf, data):
		data[0] += buf
		return True


	def _mediaSaveCb( self, recd ):
		self.doPostMediaSave( recd )


	def _mediaSaveErrorCb( self, recd ):
		self.doPostMediaSave( recd )


	def doPostMediaSave( self, xmlFile, el, recd, mediaObject ):
		print("doPostMediaSave 1")

		recd.datastoreId = mediaObject.object_id
		recd.mediaFilename = None
		recd.thumbFilename = None

		self.saveXml( xmlFile, el, recd )

		if (self.I_AM_CLOSING):
			mediaObject.destroy()
			del mediaObject

		recd.savedMedia = True
		self.checkDestroy( el.ownerDocument, xmlFile )


	def _sharedCb( self, activity ):
		self.startMesh()


	def _meshJoinedCb( self, activity ):
		self.startMesh()


	def startMesh( self ):
		self.httpServer = HttpServer(self)
		self.meshClient = MeshClient(self)
		self.meshXMLRPCServer = MeshXMLRPCServer(self)


	def _activeCb( self, widget, pspec ):
		print("active?", self.props.active, self.ACTIVE )
		if (not self.props.active and self.ACTIVE):
			self.stopPipes()
		elif (self.props.active and not self.ACTIVE):
			self.restartPipes()
			print("should restart pipes")

		self.ACTIVE = self.props.active


	def stopPipes(self):
		#todo: also make sure not to put the video back on display when done.
		print("stop pipes")
		self.gplay.stop()
		self.ui.doMouseListener( False )

		if (self.m.RECORDING):
			self.m.setUpdating( False )
			self.m.doShutter()
		else:
			self.glive.stop()


	def restartPipes(self):
		print("restart pipes")
		if (not self.m.UPDATING):
			self.ui.updateModeChange( )
			self.doMouseListener( True )


	def recreateTemp( self ):
		self.tempPath = os.path.join(self.topJournalPath, "temp")
		if (os.path.exists(self.tempPath)):
			shutil.rmtree( self.tempPath )
		os.makedirs(self.tempPath)


	def close( self ):
		print("close 1")
		self.I_AM_CLOSING = True
		#quicker we look like we're gone, the better
		self.hide()

		self.m.UPDATING = False
		self.ui.updateButtonSensitivities( )
		self.ui.doMouseListener( False )
		self.ui.hideLiveWindows( )
		self.ui.hidePlayWindows( )
		self.gplay.stop( )
		self.glive.setPipeType( self.glive.PIPETYPE_SUGAR_JHBUILD )
		self.glive.stop( )

		print("close 2")
		#this calls write_file
		activity.Activity.close( self )
		print("close 3")


	def checkDestroy( self, album, xmlFile ):
		print("checkDestroy 0")
		allDone = True

		for h in range (0, len(self.m.mediaHashs)):
			mhash = self.m.mediaHashs[h]
			for i in range (0, len(mhash)):
				recd = mhash[i]
				if ( (not recd.savedMedia) or (not recd.savedXml) ):
					allDone = False

		if (allDone):
			album.writexml(xmlFile)
			xmlFile.close()
			self.I_AM_SAVED = True

		#todo: reset all the saved flags or just let them take care of themselves on the next save?
		print("checkDestroy 1; I_AM_SAVED: ", self.I_AM_SAVED )
		if (self.I_AM_SAVED and self.I_AM_CLOSING):
			print("checkDestroy 2 -- pre destroy()")
			self.destroy()
			print("checkDestroy 3 -- post destroy()")


	def destroy( self ):
		print( "destroy and I_AM_CLOSING:", self.I_AM_CLOSING, "I_AM_SAVED:", self.I_AM_SAVED, "self._updating_jobject:", self._updating_jobject )

		if self.I_AM_CLOSING:
			self.hide()

		if self.I_AM_SAVED:
			print("total Destruction 1")

			#todo: why recreate temp and destroy journalpath?
			#todo: clean up / throw away any video you might be recording when you quit the activity
			self.recreateTemp()
			if (os.path.exists(self.journalPath)):
				shutil.rmtree( self.journalPath )

			print("total Destruction 2")
			activity.Activity.destroy( self )
			print("total Destruction 3")