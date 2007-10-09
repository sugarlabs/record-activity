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
import operator

from recorded import Recorded
from color import Color

from sugar import util
from sugar.datastore import datastore

import _camera


class Model:
	def __init__( self, pca ):
		self.ca = pca
		self.setConstants()

		self.mediaTypes = {}
		self.mediaTypes[self.TYPE_PHOTO] = {self.ca.keyName:"photo", self.ca.keyMime:"image/jpeg", self.ca.keyExt:"jpg"}
		self.mediaTypes[self.TYPE_VIDEO] = {self.ca.keyName:"video", self.ca.keyMime:"video/ogg", self.ca.keyExt:"ogg"}
		self.mediaTypes[self.TYPE_AUDIO] = {self.ca.keyName:"audio", self.ca.keyMime:"audio/x-wav", self.ca.keyExt:"wav"}

		self.mediaHashs = {}
		for key,value in self.mediaTypes.items():
			self.mediaHashs[ key ] = []


	def fillMediaHash( self, index ):
		if (os.path.exists(index)):
			doc = parse( os.path.abspath(index) )

		for key,value in self.mediaTypes.items():
			recdEl = doc.documentElement.getElementsByTagName(value[self.ca.keyName])
			for each in recdEl:
				self.loadMedia( each, self.mediaHashs[key] )


	def getByMd5( self, md5 ):
		for mh in range (0, len(self.mediaHashs)):
			for r in range (0, len(self.mediaHashs[mh])):
				recd = self.mediaHashs[mh][r]
				if (recd.thumbMd5 == md5):
					return recd
				elif (recd.mediaMd5 == md5):
					return recd

		return None


	def loadMedia( self, el, hash ):
		recd = Recorded( self.ca )
		addToHash = True

		recd.type = int(el.getAttribute(self.ca.recdType))
		recd.title = el.getAttribute(self.ca.recdTitle)
		recd.time = int(el.getAttribute(self.ca.recdTime))
		recd.photographer = el.getAttribute(self.ca.recdPhotographer)
		colorStrokeHex = el.getAttribute(self.ca.recdColorStroke)
		colorStroke = Color()
		colorStroke.init_hex( colorStrokeHex )
		recd.colorStroke = colorStroke
		colorFillHex = el.getAttribute(self.ca.recdColorFill)
		colorFill = Color()
		colorFill.init_hex( colorFillHex )
		recd.colorFill = colorFill

		recd.buddy = (el.getAttribute(self.ca.recdBuddy) == "True")
		recd.hashKey = el.getAttribute(self.ca.recdHashKey)
		recd.mediaMd5 = el.getAttribute(self.ca.recdMediaMd5)
		recd.thumbMd5 = el.getAttribute(self.ca.recdThumbMd5)
		recd.mediaBytes = int( el.getAttribute(self.ca.recdMediaBytes) )
		recd.thumbBytes = int( el.getAttribute(self.ca.recdThumbBytes) )

		recd.datastoreNode = el.getAttributeNode(self.ca.recdDatastoreId)
		if (recd.datastoreNode != None):
			recd.datastoreId = recd.datastoreNode.nodeValue
			#quickly check, if you have a datastoreId, that the file hasn't been deleted, thus we need to flag your removal
			#todo: find better method here (e.g., datastore.exists(id))
			self.loadMediaFromDatastore( recd )
			if (recd.datastoreOb == None):
				addToHash = False
			else:
				#name might have been changed in the journal, so reflect that here
				recd.title = recd.datastoreOb.metadata['title']
			recd.datastoreOb == None


		bt = el.getAttributeNode(self.ca.recdBuddyThumb)
		if (not bt == None):
			#todo: consolidate this code into a function...
			pbl = gtk.gdk.PixbufLoader()
			import base64
			data = base64.b64decode( bt.nodeValue )
			pbl.write(data)
			pbl.close()
			thumbImg = pbl.get_pixbuf()

			thumbPath = os.path.join(self.ca.tempPath, "datastoreThumb.jpg")
			thumbPath = self.getUniqueFilepath( thumbPath, 0 )
			thumbImg.save(thumbPath, "jpeg", {"quality":"85"} )

			recd.thumbFilename = os.path.basename(thumbPath)

		ai = el.getAttributeNode(self.ca.recdAudioImage)
		if (not ai == None):
			#todo: consolidate this code into a function...
			pbl = gtk.gdk.PixbufLoader()
			import base64
			data = base64.b64decode( ai.nodeValue )
			pbl.write(data)
			pbl.close()
			audioImg = pbl.get_pixbuf()

			audioImagePath = os.path.join(self.ca.tempPath, "audioImage.png")
			audioImagePath = self.getUniqueFilepath( audioImagePath, 0 )
			audioImg.save(audioImagePath, "png", {} )

			recd.audioImageFilename = os.path.basename(audioImagePath)

		if (addToHash):
			hash.append( recd )


	def isVideoMode( self ):
		return self.MODE == self.MODE_VIDEO


	def isPhotoMode( self ):
		return self.MODE == self.MODE_PHOTO


	def setupThumbs( self, type ):
		if (not type == self.MODE):
			return

		self.setUpdating( True )
		hash = self.mediaHashs[type]
		if (len(hash) > 0):
			self.ca.ui.addThumb( hash[len(hash)-1] )

		self.setUpdating( False )


	def showNextThumb( self, shownRecd ):
		print("showNext")
		if (shownRecd == None):
			self.showLastThumb()
		else:
			if (len(hash) > 0):
				hash = self.mediaHashs[self.MODE]
				i = operator.indexOf( hash, shownRecd )
				i = i-1
				if (i<0):
					i = len(hash)-1
				self.ca.ui.showThumbSelection( hash[i] )



	def showPrevThumb( self, shownRecd ):
		print("showPrev")
		if (shownRecd == None):
			self.showLastThumb()
		else:
			if (len(hash) > 0):
				hash = self.mediaHashs[self.MODE]
				i = operator.indexOf( hash, shownRecd )
				i = i-1
				if (i<0):
					i = len(hash)-1
				self.ca.ui.showThumbSelection( hash[i] )


	def showLastThumb( self ):
		print("showLast")
		hash = self.mediaHashs[self.MODE]
		if (len(hash) > 0):
			self.ca.ui.showThumbSelection( hash[len(hash)-1] )


	def getHash( self ):
		type = -1
		if (self.MODE == self.MODE_PHOTO):
			type = self.TYPE_PHOTO
		if (self.MODE == self.MODE_VIDEO):
			type = self.TYPE_VIDEO
		if (self.MODE == self.MODE_AUDIO):
			type = self.TYPE_AUDIO

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
				#post-processing begins now, so queue up this gfx
				self.ca.ui.showPostProcessGfx(True)
				self.stopRecordingVideo()
		elif (self.MODE == self.MODE_AUDIO):
			if (not self.RECORDING):
				self.startRecordingAudio()
			else:
				self.stopRecordingAudio()


	def stopRecordingAudio( self ):
		print("stop recording audio")
		gobject.source_remove( self.ca.ui.UPDATE_RECORDING_ID )
		self.ca.ui.progressWindow.updateProgress( 0, "" )
		self.ca.ui.TRANSCODING = True
		self.setUpdating( True )
		self.setRecording( False )
		self.ca.ui.updateVideoComponents()

		self.ca.glive.stopRecordingAudio( )


	def saveAudio( self, tempPath, pixbuf ):
		print("save audio")
		self.setUpdating( True )

		recd = self.createNewRecorded( self.TYPE_AUDIO )
		os.rename( tempPath, os.path.join(self.ca.tempPath,recd.mediaFilename))

		thumbPath = os.path.join(self.ca.tempPath, recd.thumbFilename)
		thumbImg = self.generateThumbnail(pixbuf, float(0.1671875))
		thumbImg.write_to_png(thumbPath)

		imagePath = os.path.join(self.ca.tempPath, "audioPicture.png")
		imagePath = self.getUniqueFilepath( imagePath, 0 )
		pixbuf.save( imagePath, "png", {} )
		recd.audioImageFilename = os.path.basename(imagePath)

		#at this point, we have both audio and thumb sapath, so we can save the recd
		self.createNewRecordedMd5Sums( recd )

		audioHash = self.mediaHashs[self.TYPE_AUDIO]
		audioHash.append( recd )
		self.thumbAdded( self.TYPE_AUDIO )

#		SJ KLEIN AUDIO SAVE TO DISK BEGIN
#		audioPath = os.path.join(os.path.expanduser("~"), "Journal", "Audio")
#		if (not os.path.exists(audioPath)):
#			os.makedirs(audioPath)

#		whoWhen = self.ca.nickName + "_" + str(strftime( "%a_%b_%d__%I:%M:%S_%p", time.localtime(recd.time) ))
#		audioFilepath = os.path.join( audioPath, whoWhen + ".wav" )
#		audioFilepath = self.getUniqueFilepath(audioFilepath, 0)
#		shutil.copy( os.path.join(self.ca.tempPath,recd.mediaFilename), audioFilepath )
#		audioImageFilepath = os.path.join( audioPath, whoWhen + ".png" )
#		audioImageFilepath = self.getUniqueFilepath(audioImageFilepath, 0)
#		shutil.copy( imagePath, audioImageFilepath )
#		SJ KLEIN AUDIO SAVE TO DISK END

		self.doPostSaveVideo()
		self.meshShareRecd( recd )


	def startRecordingVideo( self ):
		print("start recording video")
		self.setUpdating( True )
		self.setRecording( True )

		self.ca.ui.recordVideo()

		self.setUpdating( False )


	def startRecordingAudio( self ):
		print("start recording audio")
		self.setUpdating( True )
		self.setRecording( True )
		self.ca.ui.recordAudio()
		self.setUpdating( False )


	def setUpdating( self, upd ):
		self.UPDATING = upd
		self.ca.ui.updateButtonSensitivities()


	def setRecording( self, rec ):
		self.RECORDING = rec
		self.ca.ui.updateButtonSensitivities()


	def stopRecordingVideo( self ):
		gobject.source_remove( self.ca.ui.UPDATE_RECORDING_ID )
		self.ca.ui.progressWindow.updateProgress( 0, "" )
		self.setUpdating( True )
		self.ca.ui.TRANSCODING = True
		self.ca.ui.updateVideoComponents()
		self.ca.glive.stopRecordingVideo()


	def saveVideo( self, pixbuf, tempPath ):
		recd = self.createNewRecorded( self.TYPE_VIDEO )
		os.rename( tempPath, os.path.join(self.ca.tempPath,recd.mediaFilename))

		thumbPath = os.path.join(self.ca.tempPath, recd.thumbFilename)
		thumbImg = self.generateThumbnail(pixbuf, float(.66875) ) #todo: dynamic creation of this ratio
		thumbImg.write_to_png(thumbPath)

		self.createNewRecordedMd5Sums( recd )

		videoHash = self.mediaHashs[self.TYPE_VIDEO]
		videoHash.append( recd )
		self.thumbAdded( self.TYPE_VIDEO )

		self.doPostSaveVideo()
		self.meshShareRecd( recd )


	def meshShareRecd( self, recd ):
		#hey, i just took a cool video.audio.photo!  let me show you!
		if (self.ca.meshClient != None):
			self.ca.meshClient.notifyBudsOfNewPhoto( recd )


	def cannotSaveVideo( self ):
		print("bad recorded video")
		self.doPostSaveVideo()


	def doPostSaveVideo( self ):
		self.ca.ui.showPostProcessGfx(False)

		#prep the ui for your return
		self.ca.ui.LAST_MODE = -1
		self.ca.ui.HIDE_ON_UPDATE = False
		self.ca.ui.TRANSCODING = False
		self.ca.ui.updateVideoComponents()

		#resume live video from the camera (if the activity is active)
		if (self.ca.props.active):
			self.ca.glive.play()

		self.ca.ui.progressWindow.updateProgress( 0, "" )
		self.setRecording( False )
		self.setUpdating( False )


	def stoppedRecordingVideo( self ):
		self.setUpdating( False )


	def startTakingPhoto( self ):
		self.setUpdating( True )
		self.ca.glive.takePhoto()


	def savePhoto( self, pixbuf ):
		recd = self.createNewRecorded( self.TYPE_PHOTO )

		imgpath = os.path.join(self.ca.tempPath, recd.mediaFilename)
		pixbuf.save( imgpath, "jpeg" )

		thumbpath = os.path.join(self.ca.tempPath, recd.thumbFilename)
		#todo: generate this dynamically
		thumbImg = self.generateThumbnail(pixbuf, float(0.1671875))
		thumbImg.write_to_png(thumbpath)

		#now that we've saved both the image and its pixbuf, we get their md5s
		self.createNewRecordedMd5Sums( recd )
		self.addRecd( recd )

		self.meshShareRecd( recd )


	def removeMediaFromDatastore( self, recd ):
		#before this method is called, the media are removed from the file
		if (recd.datastoreId == None):
			return

		try:
			recd.datastoreOb.destroy()
			datastore.delete( recd.datastoreId )

			del recd.datastoreId
			recd.datastoreId = None

			del recd.datastoreOb
			recd.datastoreOb = None

		finally:
			#todo: add error message here
			pass


	def loadMediaFromDatastore( self, recd ):
		if (recd.datastoreId == None):
			print("RecordActivity error -- request for recd from datastore with no datastoreId")
			return

		if (recd.datastoreOb != None):
			return

		mediaObject = None
		try:
			mediaObject = datastore.get( recd.datastoreId )
		finally:
			if (mediaObject == None):
					print("RecordActivity error -- request for recd from datastore returning None")
					return

		recd.datastoreOb = mediaObject


	def addRecd( self, recd ):
		#todo: sort on time-taken, not on their arrival time over the mesh (?)
		self.mediaHashs[recd.type].append( recd )

		#updateUi
		#todo: gobject idle?
		self.thumbAdded( recd.type )


	def createNewRecorded( self, type ):
		recd = Recorded( self.ca )
		recd.hashKey = self.ca.hashedKey

		#to create a file, use the hardware_id+time *and* check if available or not
		nowtime = int(time.time())
		recd.time = nowtime
		recd.type = type

		mediaThumbFilename = str(recd.hashKey) + "_" + str(recd.time)
		mediaFilename = mediaThumbFilename
		mediaFilename = mediaFilename + "." + self.mediaTypes[type][self.ca.keyExt]
		mediaFilepath = os.path.join( self.ca.tempPath, mediaFilename )
		mediaFilepath = self.getUniqueFilepath( mediaFilepath, 0 )
		recd.mediaFilename = os.path.basename( mediaFilepath )

		thumbFilename = mediaThumbFilename + "_thumb.jpg"
		thumbFilepath = os.path.join( self.ca.tempPath, thumbFilename )
		thumbFilepath = self.getUniqueFilepath( thumbFilepath, 0 )
		recd.thumbFilename = os.path.basename( thumbFilepath )

		recd.photographer = self.ca.nickName
		recd.title = self.mediaTypes[type][self.ca.keyName] + " by " + str(recd.photographer)

		recd.colorStroke = self.ca.ui.colorStroke
		recd.colorFill = self.ca.ui.colorFill

		return recd


	def getUniqueFilepath( self, path, i ):
		pathOb = os.path.abspath( path )
		if (os.path.exists(pathOb)):
			i = i+1
			newPath = os.path.join( os.path.dirname(pathOb), str( str(i) + os.path.basename(pathOb) ) )
			return self.getUniqueFilepath( str(newPath), i )
		else:
			return os.path.abspath( path )


	def createNewRecordedMd5Sums( self, recd ):
		#load the thumbfile
		thumbFile = os.path.join(self.ca.tempPath, recd.thumbFilename)
		thumbMd5 = self.md5File( thumbFile )
		recd.thumbMd5 = thumbMd5
		tBytes = os.stat(thumbFile)[7]
		recd.thumbBytes = tBytes

		#load the mediafile
		mediaFile = os.path.join(self.ca.tempPath, recd.mediaFilename)
		mediaMd5 = self.md5File( mediaFile )
		recd.mediaMd5 = mediaMd5
		mBytes = os.stat(mediaFile)[7]
		recd.mediaBytes = mBytes


	def md5File( self, filepath ):
		md = md5()
		f = file( filepath, 'rb' )
		md.update( f.read() )
		digest = md.hexdigest()
		hash = util.printable_hash(digest)
		return hash


	def generateThumbnail( self, pixbuf, scale ):
		#outdated?
		#need to generate thumbnail version here
		thumbImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.ca.ui.tw, self.ca.ui.th)
		tctx = cairo.Context(thumbImg)
		img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)

		tctx.scale(scale, scale)
		tctx.set_source_surface(img, 0, 0)
		tctx.paint()
		return thumbImg


	def deleteRecorded( self, recd ):
		#remove files from the filesystem if not on the datastore
		if (recd.datastoreId == None):
			mediaFile = recd.getMediaFilepath( False )
			if (os.path.exists(mediaFile)):
				os.remove(mediaFile)

			thumbFile = recd.getThumbFilepath( False )
			if (os.path.exists(thumbFile)):
				os.remove(thumbFile)
		else:
			#remove from the datastore here, since once gone, it is gone...
			self.removeMediaFromDatastore( recd )

		#clear the index
		hash = self.mediaHashs[recd.type]
		index = hash.index(recd)
		hash.remove( recd )


	def thumbAdded( self, type ):
		#to avoid Xlib: unexpected async reply error when taking a picture on a gst callback
		#this happens b/c this might get called from a gstreamer callback
		gobject.idle_add(self.setupThumbs, type)


	def doVideoMode( self ):
		if (self.MODE == self.MODE_VIDEO):
			return

		self.setUpdating(True)
		self.MODE = self.MODE_VIDEO
		gobject.idle_add( self.setupThumbs, self.MODE )
		#todo: move these into the setupThumbs call for the idle call
		self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def doPhotoMode( self ):
		if (self.MODE == self.MODE_PHOTO):
			return

		self.setUpdating(True)
		self.MODE = self.MODE_PHOTO
		gobject.idle_add( self.setupThumbs, self.MODE )
		self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def doAudioMode( self ):
		if (self.MODE == self.MODE_AUDIO):
			return

		self.setUpdating(True)
		self.MODE = self.MODE_AUDIO
		gobject.idle_add( self.setupThumbs, self.MODE )
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