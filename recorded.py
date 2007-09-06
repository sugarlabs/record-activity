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

class Recorded:

	def __init__( self, pca ):
		self.ca = pca

		self.type = -1
		self.time = None
		self.photographer = None
		self.title = None
		self.colorStroke = None
		self.colorFill = None
		self.hashKey = None
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

		#assume you took the picture
		self.buddy = False
		self.downloadedFromBuddy = False

		#for flagging when you are being saved to the datastore for the first time...
		#and just because you have a datastore id, doesn't mean you're saved
		self.savedMedia = False
		self.savedXml = False



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
			thumbFilepath = os.path.join(self.ca.journalPath, self.thumbFilename)
			if ( os.path.isfile(thumbFilepath) ):
				thumbPixbuf = gtk.gdk.pixbuf_new_from_file(thumbFilepath)
			return thumbPixbuf
		else:
			if (self.datastoreOb == None):
				self.ca.m.loadMediaFromDatastore( self )
			if (self.datastoreOb == None):
				print("RecordActivity error -- unable to get datastore object in getThumbPixbuf")
				return None
			pbl = gtk.gdk.PixbufLoader()
			import base64
			data = base64.b64decode(self.datastoreOb.metadata['preview'])
			pbl.write(data)
			pbl.close()
			return pbl.get_pixbuf()


	def getThumbFilepath( self, meshReq ):
		#todo: make sure this is used everywhere
		if (self.datastoreId == None):
			#just taken, so it is in the tempSessionDir
			#so load file, convert to pixbuf, and return it here...
			thumbPixbuf = None
			thumbFilepath = os.path.join(self.ca.journalPath, self.thumbFilename)
			if ( os.path.isfile(thumbFilepath) ):
				return thumbFilepath
		else:
			if (self.datastoreOb == None):
				self.ca.m.loadMediaFromDatastore( self )
			if (self.datastoreOb == None):
				print("RecordActivity error -- unable to get datastore object in getThumbPixbuf")
				return None
			pbl = gtk.gdk.PixbufLoader()
			import base64
			data = base64.b64decode(self.datastoreOb.metadata['preview'])
			pbl.write(data)
			pbl.close()

			#todo: write to tmp (rainbow?) and random unused filename...
			thumbFilepath = os.path.join(self.ca.journalPath, "thumb.png")
			pbl.get_pixbuf().save(thumbFilepath, "png", {} )

			return thumbFilepath

		return None


	def getAudioImagePixbuf( self ):
		audioPixbuf = None

		if (self.audioImageFilename == None):
			audioPixbuf = self.getThumbPixbuf()
		else:
			audioFilepath = self.getAudioImageFilepath()
			if (audioFilepath != None):
				audioPixbuf = gtk.gdk.pixbuf_new_from_file(audioFilepath)

		return audioPixbuf


	def getAudioImageFilepath( self ):
		if (self.audioImageFilename != None):
			audioFilepath = os.path.join(self.ca.journalPath, self.audioImageFilename)
			return os.path.abspath(audioFilepath)
		else:
			return self.getThumbFilepath()


	def getMediaFilepath( self, meshReq ):
		print("getMediaFilepath 1")
		if (self.datastoreId == None):
			if (not self.buddy):
				#just taken by you, so it is in the tempSessionDir
				print("getMediaFilepath 3")
				mediaFilepath = os.path.join(self.ca.journalPath, self.mediaFilename)
				return os.path.abspath(mediaFilepath)
			else:
				if (self.downloadedFromBuddy):
					print("getMediaFilepath 4")
					#the user has requested the high-res version, and it has downloaded
					mediaFilepath = os.path.join(self.ca.journalPath, self.mediaFilename)
					return os.path.abspath(mediaFilepath)
				else:
					print("getMediaFilepath 5")
					#you should request it from someone and return None for the request to handle...
					#e.g., thumbs for pics, or "coming attractions" for videos ;-)
					#todo: always re-request?
					#todo: notify to the user that the request is underway or not possible...
					if ( (self.ca.meshClient != None) and meshReq):
						print("getMediaFilepath 6")
						self.ca.meshClient.requestMediaBits( self )
						print("getMediaFilepath 7")
					return None

		else:
			#pulling from the datastore, regardless of who took it
			print("getMediaFilepath 8")

			#first, get the datastoreObject and hold the reference in this Recorded instance
			if (self.datastoreOb == None):
				self.ca.m.loadMediaFromDatastore( self )
			if (self.datastoreOb == None):
				print("RecordActivity error -- unable to get datastore object in getMediaFilepath")
				return None

			#if this is a buddy's media and you only ever got a thumbnail, then return null and query for the real deal...

			print("getMediaFilepath 9")
			return self.datastoreOb.file_path