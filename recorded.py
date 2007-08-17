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
		self.name = None
		self.colorStroke = None
		self.colorFill = None
		self.hashKey = None
		self.mediaMd5 = None
		self.thumbMd5 = None

		#when you are datastore-serialized, you get one of these ids...
		self.datastoreId = None
		#todo: and we need to hold onto a reference to the datastore ob, since once we let that go, so goes the file too
		self.datastoreOb = None

		#transient... when just taken or taken out of the datastore you get these guys...  also, these should be put away
		#when they are not being displayed...  also, give these useful names, since some of them are cairo canvases, for example
		#self.media = None
		#self.thumb = None #this is a cairo canvas
		self.mediaFilename = None
		self.thumbFilename = None
		#self.thumbPixbuf = None

		#assume you took the picture
		self.buddy = False



	#todo: for getting files back from one of these, all is dependent on if the file is local or in the datastore
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
			return pbl.get_pixbuf()


	def getMediaFilepath( self ):
		if (self.datastoreId == None):
			if (not self.buddy):
				#just taken by you, so it is in the tempSessionDir
				mediaFilepath = os.path.join(self.ca.journalPath, self.mediaFilename)
				return os.path.abspath(mediaFilepath)
			else:
				if (self.mediaFilename != None):
					#maybe it is here, if it is, it has a filename
					#todo: drop the buddy filepath nonsense and use md5
					mediaFilepath = os.path.join(self.ca.journalPath, "buddies", self.mediaFilename)
					return os.path.abspath(mediaFilepath)
				else:
					#you should request it from someone and return None for the request to handle...
					#todo: always re-request?
					#notify to the user that the request is underway or not possible...
					if (self.ca.meshClient != None):
						self.ca.meshClient.requestPhotoBits( recd )
					return None

		else:
			#pulling from the datastore, regardless of who took it

			#first, get the datastoreObject and hold the reference in this Recorded instance
			if (self.datastoreOb == None):
				self.ca.m.loadMediaFromDatastore( self )

			#if, for some reason, the file is not accessible...
			#todo: get it from the mesh?
			if (self.datastoreOb == None):
				print("RecordActivity error -- unable to get datastore object in getMediaFilepath")
				return None

			return self.datastoreOb.file_path