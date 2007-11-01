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

import os
import gtk
from gtk import gdk

from constants import Constants
from instance import Instance
import utils
import serialize
import record

class Recorded:

	def __init__( self ):
		self.type = -1
		self.time = None
		self.recorderName = None
		self.recorderHash = None
		self.title = None
		self.colorStroke = None
		self.colorFill = None
		self.mediaMd5 = None
		self.thumbMd5 = None
		self.mediaBytes = None
		self.thumbBytes = None

		#flag to alert need to re-datastore the title
		self.titleChange = False

		#when you are datastore-serialized, you get one of these ids...
		self.datastoreId = None
		self.datastoreOb = None

		#if not from the datastore, then your media is here...
		self.mediaFilename = None
		self.thumbFilename = None
		self.audioImageFilename = None

		#for flagging when you are being saved to the datastore for the first time...
		#and just because you have a datastore id, doesn't mean you're saved
		self.savedMedia = False
		self.savedXml = False

		#assume you took the picture
		self.buddy = False
		self.downloadedFromBuddy = False
		self.triedMeshBuddies = []
		self.meshDownloading = False
		self.meshDownloadingFrom = ""
		self.meshDownlodingPercent = 0.0
		self.meshDownloadingProgress = False
		#if someone is downloading this, then hold onto it
		self.meshUploading = False
		self.meshReqCallbackId = 0

		self.deleted = False


	def setTitle( self, newTitle ):
		self.title = newTitle
		self.titleChange = True


	def isClipboardCopyable( self ):
		copyme = True
		if (self.buddy):
			if (not self.downloadedFromBuddy):
				return False
		return copyme


	#scenarios:
	#launch, your new thumb    -- Journal/session
	#launch, your new media    -- Journal/session
	#launch, their new thumb   -- Journal/session/buddy
	#launch, their new media   -- ([request->]) Journal/session/buddy
	#relaunch, your old thumb  -- metadataPixbuf on request (or save to Journal/session..?)
	#relaunch, your old media  -- datastoreObject->file (hold onto the datastore object, delete if deleted)
	#relaunch, their old thumb -- metadataPixbuf on request (or save to Journal/session..?)
	#relaunch, their old media -- datastoreObject->file (hold onto the datastore object, delete if deleted) | ([request->]) Journal/session/buddy

	def getThumbPixbuf( self ):
		if (self.datastoreId == None):
			#just taken, so it is in the tempSessionDir
			#so load file, convert to pixbuf, and return it here...
			thumbPixbuf = None
			thumbFilepath = os.path.join(Instance.tmpPath, self.thumbFilename)
			if ( os.path.isfile(thumbFilepath) ):
				thumbPixbuf = gtk.gdk.pixbuf_new_from_file(thumbFilepath)
			return thumbPixbuf
		else:
			#todo: handle possible corruption of the preview into some other format

			if (self.datastoreOb == None):
				self.datastoreOb = serialize.getMediaFromDatastore( self )
			if (self.datastoreOb == None):
				print("RecordActivity error -- unable to get datastore object in getThumbPixbuf")
				return None

			return utils.getPixbufFromString( self.datastoreOb.metadata['preview'] )


	def getThumbFilepath( self ):
		if (self.datastoreId == None):
			#just taken, so it is in the tempSessionDir
			#so load file, convert to pixbuf, and return it here...
			thumbPixbuf = None
			thumbFilepath = os.path.join(Instance.tmpPath, self.thumbFilename)
			if ( os.path.isfile(thumbFilepath) ):
				return thumbFilepath
		else:
			if (self.datastoreOb == None):
				self.datastoreOb = serialize.getMediaFromDatastore( self )
			if (self.datastoreOb == None):
				print("RecordActivity error -- unable to get datastore object in getThumbPixbuf")
				return None

			img = utils.getPixbufFromString( self.datastoreOb.metadata['preview'] )
			thumbFilepath = os.path.join( Instance.tmpPath, "thumb.png")
			thumbFilepath = utils.getUniqueFilepath(thumbFilepath, 0)
			img.save(thumbFilepath, "png", {} )
			return thumbFilepath

		return None


	def getAudioImagePixbuf( self ):
		audioPixbuf = None

		if (self.audioImageFilename == None):
			audioPixbuf = self.getThumbPixbuf()
		else:
			audioFilepath = self._getAudioImageFilepath()
			if (audioFilepath != None):
				audioPixbuf = gtk.gdk.pixbuf_new_from_file(audioFilepath)

		return audioPixbuf


	def _getAudioImageFilepath( self ):
		if (self.audioImageFilename != None):
			audioFilepath = os.path.join(Instance.tmpPath, self.audioImageFilename)
			return os.path.abspath(audioFilepath)
		else:
			return self.getThumbFilepath()


	def getMediaFilepath(self):
		if (self.datastoreId == None):
			if (not self.buddy):
				#just taken by you, so it is in the tempSessionDir
				mediaFilepath = os.path.join(Instance.tmpPath, self.mediaFilename)
				return os.path.abspath(mediaFilepath)
			else:
				if (self.downloadedFromBuddy):
					#the user has requested the high-res version, and it has downloaded
					mediaFilepath = os.path.join(Instance.tmpPath, self.mediaFilename)
					return os.path.abspath(mediaFilepath)
				else:
					if self.mediaFilename == None:
						#creating a new filepath, probably just got here from the mesh
						ext = Constants.mediaTypes[self.type][Constants.keyExt]
						recdPath = os.path.join(Instance.tmpPath, "recdFile_"+self.mediaMd5+"."+ext)
						recdPath = utils.getUniqueFilepath(recdPath, 0)
						self.mediaFilename = os.path.basename(recdPath)
						mediaFilepath = os.path.join(Instance.tmpPath, self.mediaFilename)
						return os.path.abspath(mediaFilepath)
					else:
						mediaFilepath = os.path.join(Instance.tmpPath, self.mediaFilename)
						return os.path.abspath(mediaFilepath)

		else: #pulling from the datastore, regardless of who took it, cause we got it
			#first, get the datastoreObject and hold the reference in this Recorded instance
			if (self.datastoreOb == None):
				self.datastoreOb = serialize.getMediaFromDatastore( self )
			if (self.datastoreOb == None):
				print("RecordActivity error -- unable to get datastore object in getMediaFilepath")
				return None

			return self.datastoreOb.file_path