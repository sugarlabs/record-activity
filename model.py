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
import gtk.gdk
import pygtk
pygtk.require('2.0')
import gc
import math
import time
from time import strftime
import gobject
import operator

import sugar.env

from constants import Constants
from instance import Instance
from recorded import Recorded
from color import Color
from ui import UI
import utils
import record
import serialize


class Model:
	def __init__( self, pca ):
		self.ca = pca
		self.MODE = Constants.MODE_PHOTO
		self.UPDATING = True
		self.RECORDING = False

		self.mediaHashs = {}
		for key,value in Constants.mediaTypes.items():
			self.mediaHashs[key] = []


	def getRecdByMd5( self, md5 ):
		for mh in range (0, len(self.mediaHashs)):
			for r in range (0, len(self.mediaHashs[mh])):
				recd = self.mediaHashs[mh][r]
				if (recd.thumbMd5 == md5):
					return recd
				elif (recd.mediaMd5 == md5):
					return recd

		return None


	def isVideoMode( self ):
		return self.MODE == Constants.MODE_VIDEO


	def isPhotoMode( self ):
		return self.MODE == Constants.MODE_PHOTO


	def displayThumb( self, type, forceUpdating ):
		#to avoid Xlib: unexpected async reply error when taking a picture on a gst callback, always call with idle_add
		#this happens b/c this might get called from a gstreamer callback

		if (not type == self.MODE):
			return

		if (forceUpdating):
			self.setUpdating( True )
		hash = self.mediaHashs[type]
		if (len(hash) > 0):
			self.ca.ui.addThumb( hash[len(hash)-1] )
		if (forceUpdating):
			self.setUpdating( False )


	def setupMode( self, type, update ):
		if (not type == self.MODE):
			return

		self.setUpdating( True )
		self.ca.ui.removeThumbs()
		hash = self.mediaHashs[type]
		for i in range (0, len(hash)):
			self.ca.ui.addThumb( hash[i] )
		if (update):
			self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def showNextThumb( self, shownRecd ):
		if (shownRecd == None):
			self.showLastThumb()
		else:
			hash = self.mediaHashs[self.MODE]
			if (len(hash) > 0):
				hash = self.mediaHashs[self.MODE]
				i = operator.indexOf( hash, shownRecd )
				i = i+1
				if (i>=len(hash)):
					i = 0
				self.ca.ui.showThumbSelection( hash[i] )


	def showPrevThumb( self, shownRecd ):
		if (shownRecd == None):
			self.showLastThumb()
		else:
			hash = self.mediaHashs[self.MODE]
			if (len(hash) > 0):
				hash = self.mediaHashs[self.MODE]
				i = operator.indexOf( hash, shownRecd )
				i = i-1
				if (i<0):
					i = len(hash)-1
				self.ca.ui.showThumbSelection( hash[i] )


	def showLastThumb( self ):
		hash = self.mediaHashs[self.MODE]
		if (len(hash) > 0):
			self.ca.ui.showThumbSelection( hash[len(hash)-1] )


	def doShutter( self ):
		if (self.UPDATING):
			return

		if (self.MODE == Constants.MODE_PHOTO):
			self.startTakingPhoto()
		elif (self.MODE == Constants.MODE_VIDEO):
			if (not self.RECORDING):
				self.startRecordingVideo()
			else:
				#post-processing begins now, so queue up this gfx
				self.ca.ui.showPostProcessGfx(True)
				self.stopRecordingVideo()
		elif (self.MODE == Constants.MODE_AUDIO):
			if (not self.RECORDING):
				self.startRecordingAudio()
			else:
				#post-processing begins now, so queue up this gfx
				self.ca.ui.showPostProcessGfx(True)
				self.stopRecordingAudio()


	def stopRecordingAudio( self ):
		gobject.source_remove( self.ca.ui.UPDATE_DURATION_ID )
		self.ca.ui.progressWindow.updateProgress( 0, "" )
		self.setUpdating( True )
		self.setRecording( False )
		self.ca.ui.TRANSCODING = True
		self.ca.ui.FULLSCREEN = False
		self.ca.ui.updateVideoComponents()

		self.ca.glive.stopRecordingAudio( )


	def saveAudio( self, tmpPath, pixbuf ):
		self.setUpdating( True )

		recd = self.createNewRecorded( Constants.TYPE_AUDIO )
		os.rename( tmpPath, os.path.join(Instance.tmpPath,recd.mediaFilename))

		thumbPath = os.path.join(Instance.tmpPath, recd.thumbFilename)
		scale = float((UI.dim_THUMB_WIDTH+0.0)/(pixbuf.get_width()+0.0))
		thumbImg = utils.generateThumbnail(pixbuf, scale, UI.dim_THUMB_WIDTH, UI.dim_THUMB_HEIGHT)
		thumbImg.write_to_png(thumbPath)

		imagePath = os.path.join(Instance.tmpPath, "audioPicture.png")
		imagePath = utils.getUniqueFilepath( imagePath, 0 )
		pixbuf.save( imagePath, "png", {} )
		recd.audioImageFilename = os.path.basename(imagePath)

		#at this point, we have both audio and thumb sapath, so we can save the recd
		self.createNewRecordedMd5Sums( recd )

		audioHash = self.mediaHashs[Constants.TYPE_AUDIO]
		audioHash.append( recd )
		gobject.idle_add(self.displayThumb, Constants.TYPE_AUDIO, True)
		self.doPostSaveVideo()
		self.meshShareRecd( recd )


	def startRecordingVideo( self ):
		self.setUpdating( True )
		self.setRecording( True )
		#let the red eye kick in before we start the video underway
		gobject.idle_add( self.beginRecordingVideo )


	def beginRecordingVideo( self ):
		self.ca.ui.recordVideo()
		self.setUpdating( False )


	def startRecordingAudio( self ):
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
		self.ca.glive.stopRecordingVideo()
		gobject.source_remove( self.ca.ui.UPDATE_DURATION_ID )
		self.ca.ui.progressWindow.updateProgress( 0, "" )
		self.setUpdating( True )
		self.ca.ui.TRANSCODING = True
		self.ca.ui.FULLSCREEN = False
		self.ca.ui.updateVideoComponents()


	def saveVideo( self, pixbuf, tmpPath, wid, hit ):
		recd = self.createNewRecorded( Constants.TYPE_VIDEO )
		os.rename( tmpPath, os.path.join(Instance.tmpPath,recd.mediaFilename))

		thumbPath = os.path.join(Instance.tmpPath, recd.thumbFilename)
		scale = float((UI.dim_THUMB_WIDTH+0.0)/(wid+0.0))
		thumbImg = utils.generateThumbnail(pixbuf, scale, UI.dim_THUMB_WIDTH, UI.dim_THUMB_HEIGHT)
		thumbImg.write_to_png(thumbPath)

		self.createNewRecordedMd5Sums( recd )

		videoHash = self.mediaHashs[Constants.TYPE_VIDEO]
		videoHash.append( recd )
		gobject.idle_add(self.displayThumb, Constants.TYPE_VIDEO, True)

		self.doPostSaveVideo()
		self.meshShareRecd( recd )


	def meshShareRecd( self, recd ):
		record.Record.log.debug('meshShareRecd')
		#hey, i just took a cool video.audio.photo!  let me show you!
		if (self.ca.recTube != None):
			record.Record.log.debug('meshShareRecd: we have a recTube')
			recdXml = serialize.getRecdXmlMeshString(recd)
			record.Record.log.debug('meshShareRecd: created XML: ' + str(recdXml) )
			self.ca.recTube.notifyBudsOfNewRecd( Instance.keyHashPrintable, recdXml )
			record.Record.log.debug('meshShareRecd: notifyBuds')


	def cannotSaveVideo( self ):
		Record.log.debug("bad recorded video")
		self.doPostSaveVideo()


	def doPostSaveVideo( self ):
		self.ca.ui.showPostProcessGfx(False)

		#prep the ui for your return
		self.ca.ui.LAST_MODE = -1
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
		recd = self.createNewRecorded( Constants.TYPE_PHOTO )

		imgpath = os.path.join(Instance.tmpPath, recd.mediaFilename)
		pixbuf.save( imgpath, "jpeg" )

		thumbpath = os.path.join(Instance.tmpPath, recd.thumbFilename)
		scale = float((UI.dim_THUMB_WIDTH+0.0)/(pixbuf.get_width()+0.0))
		thumbImg = utils.generateThumbnail(pixbuf, scale, UI.dim_THUMB_WIDTH, UI.dim_THUMB_HEIGHT)
		thumbImg.write_to_png(thumbpath)
		gc.collect()
		#now that we've saved both the image and its pixbuf, we get their md5s
		self.createNewRecordedMd5Sums( recd )

		photoHash = self.mediaHashs[Constants.TYPE_PHOTO]
		photoHash.append( recd )
		gobject.idle_add(self.displayThumb, Constants.TYPE_PHOTO, True)

		self.meshShareRecd( recd )


	def addMeshRecd( self, recd ):
		#todo: sort on time-taken, not on their arrival time over the mesh (?)
		self.mediaHashs[recd.type].append( recd )

		#updateUi, but don't lock up the buttons if they're recording or whatever
		gobject.idle_add(self.displayThumb, recd.type, False)


	def createNewRecorded( self, type ):
		recd = Recorded( )

		recd.recorderName = Instance.nickName
		recd.recorderHash = Instance.keyHashPrintable

		#to create a file, use the hardware_id+time *and* check if available or not
		nowtime = int(time.time())
		recd.time = nowtime
		recd.type = type

		mediaThumbFilename = str(recd.recorderHash) + "_" + str(recd.time)
		mediaFilename = mediaThumbFilename
		mediaFilename = mediaFilename + "." + Constants.mediaTypes[type][Constants.keyExt]
		mediaFilepath = os.path.join( Instance.tmpPath, mediaFilename )
		mediaFilepath = utils.getUniqueFilepath( mediaFilepath, 0 )
		recd.mediaFilename = os.path.basename( mediaFilepath )

		thumbFilename = mediaThumbFilename + "_thumb.jpg"
		thumbFilepath = os.path.join( Instance.tmpPath, thumbFilename )
		thumbFilepath = utils.getUniqueFilepath( thumbFilepath, 0 )
		recd.thumbFilename = os.path.basename( thumbFilepath )

		stringType = Constants.mediaTypes[type][Constants.keyIstr]
		recd.title = Constants.istrBy % {"1":stringType, "2":str(recd.recorderName)}

		recd.colorStroke = Instance.colorStroke
		recd.colorFill = Instance.colorFill

		return recd


	def createNewRecordedMd5Sums( self, recd ):
		#load the thumbfile
		thumbFile = os.path.join(Instance.tmpPath, recd.thumbFilename)
		thumbMd5 = utils.md5File( thumbFile )
		recd.thumbMd5 = thumbMd5
		tBytes = os.stat(thumbFile)[7]
		recd.thumbBytes = tBytes

		#load the mediafile
		mediaFile = os.path.join(Instance.tmpPath, recd.mediaFilename)
		mediaMd5 = utils.md5File( mediaFile )
		recd.mediaMd5 = mediaMd5
		mBytes = os.stat(mediaFile)[7]
		recd.mediaBytes = mBytes



	def deleteRecorded( self, recd ):
		recd.deleted = True

		#clear the index
		hash = self.mediaHashs[recd.type]
		index = hash.index(recd)
		hash.remove( recd )

		if (not recd.meshUploading):
			self.doDeleteRecorded( recd )


	def doDeleteRecorded( self, recd ):
		#remove files from the filesystem if not on the datastore
		if (recd.datastoreId == None):
			mediaFile = recd.getMediaFilepath()
			if (os.path.exists(mediaFile)):
				os.remove(mediaFile)

			thumbFile = recd.getThumbFilepath( )
			if (os.path.exists(thumbFile)):
				os.remove(thumbFile)
		else:
			#remove from the datastore here, since once gone, it is gone...
			serialize.removeMediaFromDatastore( recd )


	def doVideoMode( self ):
		if (self.MODE == Constants.MODE_VIDEO):
			return

		self.MODE = Constants.MODE_VIDEO
		self.setUpdating(True)
		gobject.idle_add( self.setupMode, self.MODE, True )


	def doPhotoMode( self ):
		if (self.MODE == Constants.MODE_PHOTO):
			return

		self.MODE = Constants.MODE_PHOTO
		self.setUpdating(True)
		gobject.idle_add( self.setupMode, self.MODE, True )


	def doAudioMode( self ):
		if (self.MODE == Constants.MODE_AUDIO):
			return

		self.MODE = Constants.MODE_AUDIO
		self.setUpdating(True)
		gobject.idle_add( self.setupMode, self.MODE, True )