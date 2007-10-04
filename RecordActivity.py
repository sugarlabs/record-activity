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

from gettext import gettext as _

import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse

class RecordActivity(activity.Activity):

	def __init__(self, handle):
		activity.Activity.__init__(self, handle)
		#handle the initial notify::active callback differently
		self.JUST_LAUNCHED = True
		#connect these right away
		self.connect( "shared", self._sharedCb )
		self.connect( "notify::active", self._activeCb )
		#wait a moment so that our debug console capture mistakes
		gobject.idle_add( self._initme, None )


	def _initme( self, userdata=None ):
		#todo: all other international strings here
		self.activityName = _('Record')
		self.recdTitle = "title"
		self.recdTime = "time"
		self.recdPhotographer = "photographer"
		self.recdColorStroke = "colorStroke"
		self.recdColorFill = "colorFill"
		self.recdHashKey = "hashKey"
		self.recdBuddy = "buddy"
		self.recdMediaMd5 = "mediaMd5"
		self.recdThumbMd5 = "thumbMd5"
		self.recdMediaBytes = "mediaBytes"
		self.recdThumbBytes = "thumbBytes"
		self.recdDatastoreId = "datastoreId"
		self.recdAudioImage = "audioImage"
		self.recdAlbum = "album"
		self.recdType = "type"
		self.recdBuddyThumb = "buddyThumb"
		self.keyName = "name"
		self.keyMime = "mime"
		self.keyExt = "ext"

		self.set_title( self.activityName )

		#flags for controlling the writing to the datastore
		self.I_AM_CLOSING = False
		self.I_AM_SAVED = False

		#paths
		self.basePath = activity.get_bundle_path()
		self.gfxPath = os.path.join(self.basePath, "gfx")
		self.recreateTemp()

		#whoami?
		key = profile.get_pubkey()
		keyHash = util._sha_data(key)
		self.hashedKey = util.printable_hash(keyHash)
		self.instanceId = self._activity_id
		self.nickName = profile.get_nick_name()

		#todo: also tubes
		h = hash(self.instanceId)
		self.xmlRpcPort = 1024 + (h%32255) * 2
		self.httpPort = self.xmlRpcPort + 1
		self.httpServer = None
		self.meshClient = None
		self.meshXMLRPCServer = None

		#the main classes
		self.glive = Glive( self )
		self.gplay = Gplay( self )
		self.m = Model( self )
		self.ui = UI( self )

		#CSCL
		if self._shared_activity:
			#have you joined or shared this activity yourself?
			if self.get_shared():
				self.startMesh()
			else:
				self.connect("joined", self._meshJoinedCb)

		#initialize the app with the default thumbs
		self.setupThumbs( self.m.MODE )

		return False


	def read_file(self, file):
		self.m.fillMediaHash(file)


	def write_file(self, file):
		self.I_AM_SAVED = False
		SAVING_AT_LEAST_ONE = False

		xmlFile = open( file, "w" )
		impl = getDOMImplementation()
		album = impl.createDocument(None, self.recdAlbum, None)
		root = album.documentElement

		atLeastOne = False

		#flag everything for saving...
		for type,value in self.m.mediaTypes.items():
			typeName = value[self.keyName]
			hash = self.m.mediaHashs[type]
			for i in range (0, len(hash)):
				recd = hash[i]
				recd.savedXml = False
				recd.savedMedia = False
				atLeastOne = True

		#and if there is anything to save, save it
		if (atLeastOne):
			for type,value in self.m.mediaTypes.items():
				typeName = value[self.keyName]
				hash = self.m.mediaHashs[type]

				for i in range (0, len(hash)):
					recd = hash[i]
					mediaEl = album.createElement( typeName )
					root.appendChild( mediaEl )
					self.saveIt( xmlFile, mediaEl, recd )

		#otherwise, clear it out
		if (not atLeastOne):
			self.checkDestroy( album, xmlFile )


	def saveIt( self, xmlFile, el, recd ):
		#presume we don't need to serialize...
		needToDatastoreMedia = False

		if ( (recd.buddy == True) and (recd.datastoreId == None) and (not recd.downloadedFromBuddy) ):
			pixbuf = recd.getThumbPixbuf( )
			buddyThumb = str( self._get_base64_pixbuf_data(pixbuf) )
			el.setAttribute(self.recdBuddyThumb, buddyThumb )
			recd.savedMedia = True
			self.saveXml( xmlFile, el, recd )
		else:
			recd.savedMedia = False
			self.saveMedia( xmlFile, el, recd )


	def saveXml( self, xmlFile, el, recd ):
		el.setAttribute(self.recdType, str(recd.type))

		if (recd.type == self.m.TYPE_AUDIO):
			aiPixbuf = recd.getAudioImagePixbuf( )
			aiPixbufString = str( self._get_base64_pixbuf_data(aiPixbuf) )
			el.setAttribute(self.recdAudioImage, aiPixbufString)

		el.setAttribute(self.recdTitle, recd.title)
		el.setAttribute(self.recdTime, str(recd.time))
		el.setAttribute(self.recdPhotographer, recd.photographer)
		el.setAttribute(self.recdColorStroke, str(recd.colorStroke.hex) )
		el.setAttribute(self.recdColorFill, str(recd.colorFill.hex) )
		el.setAttribute(self.recdHashKey, str(recd.hashKey))
		el.setAttribute(self.recdBuddy, str(recd.buddy))
		el.setAttribute(self.recdMediaMd5, str(recd.mediaMd5))
		el.setAttribute(self.recdThumbMd5, str(recd.thumbMd5))
		el.setAttribute(self.recdMediaBytes, str(recd.mediaBytes))
		el.setAttribute(self.recdThumbBytes, str(recd.thumbBytes))
		if (recd.datastoreId != None):
			el.setAttribute(self.recdDatastoreId, str(recd.datastoreId))

		recd.savedXml = True
		self.checkDestroy( el.ownerDocument, xmlFile )


	def saveMedia( self, xmlFile, el, recd ):
		#note that we update the recds that go through here to how they would
		#look on a fresh load from file since this won't just happen on close()

		if (recd.datastoreId != None):
			#already saved to the datastore, don't need to re-rewrite the file since the mediums are immutable
			#However, they might have changed the name of the file
			if (recd.titleChange):
				self.m.loadMediaFromDatastore( recd )
				if (recd.datastoreOb.metadata['title'] != recd.title):
					recd.datastoreOb.metadata['title'] = recd.title
					datastore.write(recd.datastoreOb)

				#reset for the next title change if not closing...
				recd.titleChange = False
				#save the title to the xml
				recd.savedMedia = True

				self.saveXml( xmlFile, el, recd )
			else:
				recd.savedMedia = True
				self.saveXml( xmlFile, el, recd )

		else:
			#this will remove the media from being accessed on the local disk since it puts it away into cold storage
			#therefore this is only called when write_file is called by the activity superclass
			mediaObject = datastore.create()
			#todo: what other metadata to set?
			mediaObject.metadata['title'] = recd.title
			#jobject.metadata['keep'] = '0'
			#jobject.metadata['buddies'] = ''

			pixbuf = recd.getThumbPixbuf()
			thumbData = self._get_base64_pixbuf_data(pixbuf)
			mediaObject.metadata['preview'] = thumbData

			colors = str(recd.colorStroke.hex) + "," + str(recd.colorFill.hex)
			mediaObject.metadata['icon-color'] = colors

			mtype = self.m.mediaTypes[recd.type]
			mmime = mtype[self.ca.typeMime]
			mediaObject.metadata['mime_type'] = mmime

			#todo: make sure the file is still available before you ever get to this point...
			mediaFile = recd.getMediaFilepath(False)
			mediaObject.file_path = mediaFile

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
		if (self.JUST_LAUNCHED):
			self.JUST_LAUNCHED = False
			return

		if (not self.props.active):
			self.stopPipes()
		elif (self.props.active):
			self.restartPipes()


	def stopPipes(self):
		self.gplay.stop()
		self.ui.doMouseListener( False )

		if (self.m.RECORDING):
			self.m.setUpdating( False )
			self.m.doShutter()
		else:
			self.glive.stop()


	def restartPipes(self):
		if (not self.m.UPDATING):
			self.ui.updateModeChange( )
			self.ui.doMouseListener( True )


	def recreateTemp( self ):
		#todo: rainbow
		self.tempPath = os.path.join("tmp", "Record_"+str(self.instanceId))
		if (os.path.exists(self.tempPath)):
			shutil.rmtree( self.tempPath )
		os.makedirs(self.tempPath)


	def close( self ):
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

		#this calls write_file
		activity.Activity.close( self )


	def checkDestroy( self, album, xmlFile ):
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
		if (self.I_AM_SAVED and self.I_AM_CLOSING):
			self.destroy()


	def destroy( self ):
		if self.I_AM_CLOSING:
			self.hide()

		if self.I_AM_SAVED:
			self.recreateTemp()
			activity.Activity.destroy( self )