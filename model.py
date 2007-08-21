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


import urllib
import string
import fnmatch
import os
import random
import cairo
import gtk
import pygtk
pygtk.require('2.0')
import shutil

import math
import gtk.gdk
import sugar.env
import random
import time
from time import strftime
import gobject
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse
from hashlib import md5

from recorded import Recorded
from color import Color

from sugar import util
from sugar.datastore import datastore

import _camera


class Model:
	def __init__( self, pca ):
		#todo: this might all need to be relocated b/c of datastore
		self.ca = pca
		self.setConstants()

		self.mediaHashs = {}
		self.mediaHashs[self.TYPE_PHOTO] = []
		self.mediaHashs[self.TYPE_VIDEO] = []


	def fillMediaHash( self, index ):
		print("fillMediaHash 1")
		if (os.path.exists(index)):
			print("fillMediaHash 2")
			doc = parse( os.path.abspath(index) )
			photos = doc.documentElement.getElementsByTagName('photo')
			for each in photos:
				print("getting photo")
				self.loadMedia( each, self.mediaHashs[self.TYPE_PHOTO] )
				print("got photo")

			videos = doc.documentElement.getElementsByTagName('video')
			for each in videos:
				self.loadMedia( each, self.mediaHashs[self.TYPE_VIDEO] )


	def loadMedia( self, el, hash ):
		recd = Recorded( self.ca )
		addToHash = True

		recd.type = int(el.getAttribute('type'))
		recd.title = el.getAttribute('title')
		recd.time = int(el.getAttribute('time'))
		recd.photographer = el.getAttribute('photographer')
		recd.mediaFilename = el.getAttribute('mediaFilename')
		recd.thumbFilename = el.getAttribute('thumbFilename')

		colorStrokeHex = el.getAttribute('colorStroke')
		colorStroke = Color()
		colorStroke.init_hex( colorStrokeHex )
		recd.colorStroke = colorStroke
		colorFillHex = el.getAttribute('colorFill')
		colorFill = Color()
		colorFill.init_hex( colorFillHex )
		recd.colorFill = colorFill

		recd.buddy = (el.getAttribute('buddy') == "True")
		recd.hashKey = el.getAttribute('hashKey')
		recd.mediaMd5 = el.getAttribute('mediaMd5')
		recd.thumbMd5 = el.getAttribute('thumbMd5')

		recd.datastoreId = el.getAttribute('datastoreId')

		if (not recd.datastoreId == None):
			recd.datastoreId = el.getAttribute('datastoreId')
			#quickly check, if you have a datastoreId, that the file hasn't been deleted, thus we need to flag your removal
			#todo: find better method here (e.g., datastore.exists(id))
			self.loadMediaFromDatastore( recd )
			if (recd.datastoreOb == None):
				addToHash = False
			else:
				#name might have been changed in the journal, so reflect that here
				recd.title = recd.datastoreOb.metadata['title']
			recd.datastoreOb == None

		#buddyThumbString = el.getAttribute('buddyThumb')
		#print("buddyThumbString...", buddyThumbString )
		bt = el.getAttributeNode('buddyThumb')
		print( "bt", bt )
		if (not bt == None):
			#todo: consolidate this code into a function...
			pbl = gtk.gdk.PixbufLoader()
			import base64
			print( "bt.nodeValue:", bt.nodeValue )
			data = base64.b64decode( bt.nodeValue )
			pbl.write(data)
			thumbImg = pbl.get_pixbuf()
			#todo: add check for what to do if there is no thumbFilename!
			thumbPath = os.path.join(self.ca.journalPath, recd.thumbFilename)
			print("thumbPath:", thumbPath, "img:", thumbImg )
			thumbImg.write_to_png(thumbPath)
			print( "buddyThumbString: ", buddyThumbString )

		if (addToHash):
			hash.append( recd )


	def saveMedia( self, el, recd, type ):
		doDatastoreMedia = True
		if ( (recd.buddy == True) and (recd.datastoreId == None) and (recd.mediaFilename == None) ):
			datastoreMedia = False

		if (doDatastoreMedia):
			#this gets us a datatoreId we need later to serialize the data
			self.saveMediaToDatastore( recd )
		else:
			buddyThumb = str( self._get_base64_pixbuf_data(pixbuf) )
			print( "buddyThumb", buddyThumb )
			el.setAttribute("buddyThumb", buddyThumb )

		el.setAttribute("type", str(type))
		el.setAttribute("title", recd.title)
		el.setAttribute("time", str(recd.time))
		el.setAttribute("photographer", recd.photographer)
		el.setAttribute("mediaFilename", recd.mediaFilename)
		el.setAttribute("thumbFilename", recd.thumbFilename)
		el.setAttribute("colorStroke", str(recd.colorStroke.hex) )
		el.setAttribute("colorFill", str(recd.colorFill.hex) )
		el.setAttribute("hashKey", str(recd.hashKey))
		el.setAttribute("buddy", str(recd.buddy))
		el.setAttribute("mediaMd5", str(recd.mediaMd5))
		el.setAttribute("thumbMd5", str(recd.thumbMd5))
		if (recd.datastoreId != None):
			el.setAttribute("datastoreId", str(recd.datastoreId))


	def selectLatestThumbs( self, type ):
		p_mx = len(self.mediaHashs[type])
		p_mn = max(p_mx-self.ca.ui.numThumbs, 0)
		gobject.idle_add(self.setupThumbs, type, p_mn, p_mx)


	def isVideoMode( self ):
		return self.MODE == self.MODE_VIDEO


	def isPhotoMode( self ):
		return self.MODE == self.MODE_PHOTO


	def setupThumbs( self, type, mn, mx ):

		if (not type == self.MODE):
			return

		self.setUpdating( True )

		hash = self.mediaHashs[type]

		#don't load more than you possibly need by accident
		if (mx>mn+self.ca.ui.numThumbs):
			mx = mn+self.ca.ui.numThumbs
		mx = min( mx, len(hash) )

		if (mn<0):
			mn = 0

		if (mx == mn):
			mn = mx-self.ca.ui.numThumbs

		if (mn<0):
			mn = 0

		#
		#	UI
		#
		#at which # do the left and right buttons begin?
		left = -1
		rigt = -1
		if (mn>0):
			left = max(0, mn-self.ca.ui.numThumbs)
		rigt = mx
		if (mx>=len(hash)):
			rigt = -1

		#get these from the hash to send over
		addToTray = []
		for i in range (mn, mx):
			addToTray.append( hash[i] )

		self.ca.ui.updateThumbs( addToTray, left, mn, rigt  )
		self.setUpdating( False )


	def getHash( self ):
		type = -1
		if (self.ca.m.MODE == self.ca.m.MODE_PHOTO):
			type = self.ca.m.TYPE_PHOTO
		if (self.ca.m.MODE == self.ca.m.MODE_VIDEO):
			type = self.ca.m.TYPE_VIDEO

		if (type != -1):
			return self.mediaHashs[type]
		else:
			return None


	def doShutter( self ):
		if (self.UPDATING):
			return

		if (self.MODE == self.MODE_PHOTO):
			self.startTakingPhoto()
		elif (self.MODE == self.MODE_VIDEO):
			if (not self.RECORDING):
				self.startRecordingVideo()
			else:
				self.stopRecordingVideo()


	def startRecordingVideo( self ):
		print("start recording video")
		self.setUpdating( True )
		self.setRecording( True )

		self.ca.ui.recordVideo()

		self.setUpdating( False )


	def setUpdating( self, upd ):
		self.UPDATING = upd
		self.ca.ui.updateButtonSensitivities()


	def setRecording( self, rec ):
		self.RECORDING = rec
		self.ca.ui.updateButtonSensitivities()


	def stopRecordingVideo( self ):
		print("stop recording video")
		self.setUpdating( True )

		self.ca.ui.hideLiveWindows()
		self.ca.ui.hidePlayWindows()

		self.ca.glive.stopRecordingVideo()


	def saveVideo( self, pixbuf, tempPath ):
		recd = self.createNewRecorded( self.TYPE_VIDEO )

		oggPath = os.path.join(self.ca.journalPath, recd.mediaFilename)
		thumbPath = os.path.join(self.ca.journalPath, recd.thumbFilename)

		#todo: dynamic creation of this ratio
		thumbImg = self.generateThumbnail(pixbuf, float(.66875) )
		thumbImg.write_to_png(thumbPath)
		#thumb = pixbuf.scale_simple( self._thuPho.tw, self._thuPho.th, gtk.gdk.INTERP_BILINEAR )
		#thumb.save( thumbpath, "jpeg", {"quality":"85"} )

		#todo: unneccassary to move to oggpath? or temp should *be* oggpath
		shutil.move(tempPath, oggPath)

		#at this point, we have both video and thumb path, so we can save the recd
		self.createNewRecordedMd5Sums( recd )

		videoHash = self.mediaHashs[self.TYPE_VIDEO]
		videoHash.append( recd )
		self.thumbAdded( self.TYPE_VIDEO )

		self.doPostSaveVideo()


	def cannotSaveVideo( self ):
		print("bad recorded video")
		self.doPostSaveVideo()


	def doPostSaveVideo( self ):
		#resume live video from the camera (if the activity is active)
		if (self.ca.ACTIVE):
			self.ca.ui.updateVideoComponents()
			self.ca.glive.play()

		self.setRecording( False )


	def stoppedRecordingVideo( self ):
		print("stoppedRecordingVideo")
		self.setUpdating( False )


	def startTakingPhoto( self ):
		self.setUpdating( True )
		self.ca.glive.takePhoto()


	def savePhoto( self, pixbuf ):
		recd = self.createNewRecorded( self.TYPE_PHOTO )

		imgpath = os.path.join(self.ca.journalPath, recd.mediaFilename)
		pixbuf.save( imgpath, "jpeg" )

		thumbpath = os.path.join(self.ca.journalPath, recd.thumbFilename)
		#todo: generate this dynamically
		thumbImg = self.generateThumbnail(pixbuf, float(0.1671875))
		thumbImg.write_to_png(thumbpath)
		#todo: use this code...?
		#thumb = pixbuf.scale_simple( self._thuPho.tw, self._thuPho.th, gtk.gdk.INTERP_BILINEAR )
		#thumb.save( thumbpath, "jpeg", {"quality":"85"} )

		#now that we've saved both the image and its pixbuf, we get their md5s
		self.createNewRecordedMd5Sums( recd )
		self.addPhoto( recd )

		#hey, i just took a cool picture!  let me show you!
		if (self.ca.meshClient != None):
			#todo: md5?
			self.ca.meshClient.notifyBudsOfNewPhoto( recd )



	def saveMediaToDatastore( self, recd ):

		if (recd.datastoreId != None):
			#already saved to the datastore, don't need to re-rewrite the file since the mediums are immutable
			#todo: HOWEVER, they might have changed the name of the file
			if (recd.titleChange):
				self.loadMediaFromDatastore( recd )
				try:
					if (recd.datastoreOb.metadata['title'] != recd.title):
						recd.datastoreOb.metadata['title'] = recd.title
						datastore.write(recd.datastoreOb)
						if (recd.datastoreOb != None):
							recd.datastoreOb.destroy()
							del recd.datastoreOb
				finally:
					if (recd.datastoreOb != None):
						recd.datastoreOb.destroy()
						del recd.datastoreOb
			return

		#this will remove the media from being accessed on the local disk since it puts it away into cold storage
		#therefore this is only called when write_file is called by the activity superclass
		try:
			mediaObject = datastore.create()
			try:
				#todo: what other metadata to set?
				mediaObject.metadata['title'] = recd.title
				#jobject.metadata['keep'] = '0'
				#jobject.metadata['buddies'] = ''

				pixbuf = recd.getThumbPixbuf()
				thumbData = self._get_base64_pixbuf_data(pixbuf)
				mediaObject.metadata['preview'] = thumbData

				colors = str(recd.colorStroke.hex) + "," + str(recd.colorFill.hex)
				mediaObject.metadata['icon-color'] = colors

				if (recd.type == self.TYPE_PHOTO):
					mediaObject.metadata['mime_type'] = 'image/jpeg'
				elif (recd.type == self.TYPE_VIDEO):
					mediaObject.metadata['mime_type'] = 'video/ogg'
				elif (recd.type == self.TYPE_AUDIO):
					mediaObject.metadata['mime_type'] = 'audio/ogg'

				mediaFile = os.path.join(self.ca.journalPath, recd.mediaFilename)
				mediaObject.file_path = mediaFile

				datastore.write(mediaObject)
				recd.datastoreId = mediaObject.object_id

			finally:
				if (mediaObject != None):
					mediaObject.destroy()
					del mediaObject

		finally:
			pass
			#don't really need to do this here, since we delete our temp before shutdown
			#os.remove(file_path)


	def _get_base64_pixbuf_data(self, pixbuf):
		data = [""]
		pixbuf.save_to_callback(self._save_data_to_buffer_cb, "png", {}, data)

		import base64
		return base64.b64encode(str(data[0]))


	def _save_data_to_buffer_cb(self, buf, data):
		data[0] += buf
		return True


	def removeMediaFromDatastore( self, recd ):
		print("removeMediaFromDatastore 1")
		#before this method is called, the media are removed from the file
		if (recd.datastoreId == None):
			return

		try:
			recd.datastoreOb.destroy()
			print("removeMediaFromDatastore 2")
			datastore.delete( recd.datastoreId )

			del recd.datastoreId
			recd.datastoreId = None

			del recd.datastoreOb
			recd.datastoreOb = None

			print("removeMediaFromDatastore 3")
		finally:
			#todo: add error message here
			print("removeMediaFromDatastore 4")
			pass


	def loadMediaFromDatastore( self, recd ):
		#todo: make sure methods calling this handle None as a response

		if (recd.datastoreId == None):
			print("RecordActivity error -- request for recd from datastore with no datastoreId")
			return None

		mediaObject = None
		try:
			mediaObject = datastore.get( recd.datastoreId )
		finally:
			if (mediaObject == None):
					print("RecordActivity error -- request for recd from datastore returning None")
					return None

		recd.datastoreOb = mediaObject


	def addPhoto( self, recd ):
		#todo: sort on time-taken, not on their arrival time over the mesh (?)
		self.mediaHashs[self.TYPE_PHOTO].append( recd )

		#updateUi
		self.thumbAdded(self.TYPE_PHOTO)

		self.setUpdating( False )


	#assign a better name here (name_0.jpg)
	def createNewRecorded( self, type ):
		recd = Recorded( self.ca )
		recd.hashKey = self.ca.hashedKey

		#to create a file, use the hardware_id+time *and* check if available or not
		nowtime = int(time.time())
		recd.time = nowtime

		mediaThumbFilename = str(recd.hashKey) + "_" + str(recd.time)
		mediaFilename = mediaThumbFilename

		recd.type = type
		if (type == self.TYPE_PHOTO):
			mediaFilename = mediaFilename + ".jpg"
		if (type == self.TYPE_VIDEO):
			mediaFilename = mediaFilename + ".ogv"
		mediaFilename = self.getUniqueFilepath( mediaFilename, 0 )
		recd.mediaFilename = mediaFilename

		thumbFilename = mediaThumbFilename + "_thumb.jpg"
		thumbFilename = self.getUniqueFilepath( thumbFilename, 0 )
		recd.thumbFilename = thumbFilename

		recd.photographer = self.ca.nickName

		#todo: better title here
		recd.title = str(recd.photographer) + ", " + strftime( "%a, %b %d, %I:%M:%S %p", time.localtime(recd.time) )

		recd.colorStroke = self.ca.ui.colorStroke
		recd.colorFill = self.ca.ui.colorFill

		return recd


	def getUniqueFilepath( self, path, i ):
		pathOb = os.path.abspath( path )
		if (os.path.exists(pathOb)):
			i = i+1
			newPath = os.path.join( os.path.dirname(pathOb), str( str(i) + os.path.basename(pathOb) ) )
			path = getUniqueFilepath( str(newPath), i )
		else:
			return path


	def createNewRecordedMd5Sums( self, recd ):
		#load the thumbfile
		thumbFile = os.path.join(self.ca.journalPath, recd.thumbFilename)
		print( thumbFile, os.path.exists(thumbFile))
		thumbMd5 = self.md5File( thumbFile )
		recd.thumbMd5 = thumbMd5

		#load the mediafile
		mediaFile = os.path.join(self.ca.journalPath, recd.mediaFilename)
		mediaMd5 = self.md5File( mediaFile )
		recd.mediaMd5 = mediaMd5


	def md5File( self, filepath ):
		md = md5()
		f = file( filepath, 'rb' )
		md.update( f.read() )
		digest = md.hexdigest()
		hash = util.printable_hash(digest)
		return hash


	#outdated?
	def generateThumbnail( self, pixbuf, scale ):
#		#need to generate thumbnail version here
		thumbImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.ca.ui.tw, self.ca.ui.th)
		tctx = cairo.Context(thumbImg)
		img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)

		tctx.scale(scale, scale)
		tctx.set_source_surface(img, 0, 0)
		tctx.paint()
		return thumbImg


	def deleteRecorded( self, recd, mn ):
		print("deleteRecorded 1")

		#remove files from the filesystem if not on the datastore
		if (recd.datastoreId == None):
			print("deleteRecorded 2")
			mediaFile = os.path.join(self.ca.journalPath, recd.mediaFilename)
			if (os.path.exists(mediaFile)):
				os.remove(mediaFile)

			thumbFile = os.path.join(self.ca.journalPath, recd.thumbFilename)
			if (os.path.exists(thumbFile)):
				os.remove(thumbFile)
		else:
			print("deleteRecorded 3")
			#remove from the datastore here, since once gone, it is gone...
			self.removeMediaFromDatastore( recd )

		#clear the index
		hash = self.mediaHashs[recd.type]
		index = hash.index(recd)
		hash.remove( recd )

		#update your own ui
		self.setupThumbs(recd.type, mn, mn+self.ca.ui.numThumbs)
		print("deleteRecorded 4")



	def updateMediaIndex( self ):
		print("updateMediaIndex")
		impl = getDOMImplementation()
		album = impl.createDocument(None, "album", None)
		root = album.documentElement
		photoHash = self.mediaHashs[self.TYPE_PHOTO]
		for i in range (0, len(photoHash)):
			recd = photoHash[i]

			photo = album.createElement('photo')
			root.appendChild(photo)
			self.saveMedia(photo, recd, self.TYPE_PHOTO )
			print("saved photo")

		videoHash = self.mediaHashs[self.TYPE_VIDEO]
		for i in range (0, len(videoHash)):
			recd = videoHash[i]

			video = album.createElement('video')
			root.appendChild(video)
			self.saveMedia(video, recd, self.TYPE_VIDEO )

		return album


	#todo: if you are not at the end of the list, do we want to force you to the end?
	def thumbAdded( self, type ):
		mx = len(self.mediaHashs[type])
		mn = max(mx-self.ca.ui.numThumbs, 0)
		self.setupThumbs(type, mn, mx)


	def doVideoMode( self ):
		if (self.MODE == self.MODE_VIDEO):
			return

		self.setUpdating(True)
		#assign your new mode
		self.MODE = self.MODE_VIDEO
		self.selectLatestThumbs(self.TYPE_VIDEO)

		self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def doPhotoMode( self ):
		if (self.MODE == self.MODE_PHOTO):
			return

		self.setUpdating(True)
		#assign your new mode
		self.MODE = self.MODE_PHOTO
		self.selectLatestThumbs(self.TYPE_PHOTO)

		self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def doAudioMode( self ):
		if (self.MODE == self.MODE_AUDIO):
			return

		self.setUpdating(True)
		self.MODE = self.MODE_AUDIO
		self.selectLatestThumbs(self.TYPE_AUDIO)

		self.ca.ui.updateModeChange()
		self.setUpdating(False)

	def setConstants( self ):
		#pics or vids?
		self.MODE_PHOTO = 0
		self.MODE_VIDEO = 1
		self.MODE_AUDIO = 2
		self.MODE = self.MODE_PHOTO

		self.TYPE_PHOTO = 0
		self.TYPE_VIDEO = 1
		self.TYPE_AUDIO = 2

		self.UPDATING = True
		self.RECORDING = False