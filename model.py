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
		self.ca = pca
		self.setConstants()

		self.mediaTypes = {}
		self.mediaTypes[self.TYPE_PHOTO] = {"name":"photo"}
		self.mediaTypes[self.TYPE_VIDEO] = {"name":"video"}
		self.mediaTypes[self.TYPE_AUDIO] = {"name":"audio"}

		self.mediaHashs = {}
		#for i in range(0, len(self.mediaTypes)):
		#for item in self.mediaTypes.keys():
		for key,value in self.mediaTypes.items():
			self.mediaHashs[ key ] = []


	def fillMediaHash( self, index ):
		print("fillMediaHash 1")
		if (os.path.exists(index)):
			print("fillMediaHash 2")
			doc = parse( os.path.abspath(index) )

			#todo: use an array/dictionary here
			photos = doc.documentElement.getElementsByTagName('photo')
			for each in photos:
				self.loadMedia( each, self.mediaHashs[self.TYPE_PHOTO] )

			videos = doc.documentElement.getElementsByTagName('video')
			for each in videos:
				self.loadMedia( each, self.mediaHashs[self.TYPE_VIDEO] )

			audios = doc.documentElement.getElementsByTagName('audio')
			for each in audios:
				self.loadMedia( each, self.mediaHashs[self.TYPE_AUDIO] )


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

		recd.type = int(el.getAttribute('type'))
		recd.title = el.getAttribute('title')
		recd.time = int(el.getAttribute('time'))
		recd.photographer = el.getAttribute('photographer')
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
		recd.mediaBytes = int( el.getAttribute('mediaBytes') )
		recd.thumbBytes = int( el.getAttribute('thumbBytes') )

		recd.datastoreNode = el.getAttributeNode("datastoreId")
		if (recd.datastoreNode != None):
			print("loadMedia a")
			recd.datastoreId = recd.datastoreNode.nodeValue
			#quickly check, if you have a datastoreId, that the file hasn't been deleted, thus we need to flag your removal
			#todo: find better method here (e.g., datastore.exists(id))
			self.loadMediaFromDatastore( recd )
			if (recd.datastoreOb == None):
				print("~~> recd.datastoreId", recd.datastoreId )
				addToHash = False
			else:
				#name might have been changed in the journal, so reflect that here
				recd.title = recd.datastoreOb.metadata['title']
			recd.datastoreOb == None


		bt = el.getAttributeNode('buddyThumb')
		if (not bt == None):
			print("loadMedia b")
			#todo: consolidate this code into a function...
			pbl = gtk.gdk.PixbufLoader()
			import base64
			data = base64.b64decode( bt.nodeValue )
			pbl.write(data)
			pbl.close()
			thumbImg = pbl.get_pixbuf()

			thumbPath = os.path.join(self.ca.journalPath, "datastoreThumb.jpg")
			thumbPath = self.getUniqueFilepath( thumbPath, 0 )
			thumbImg.save(thumbPath, "jpeg", {"quality":"85"} )

			recd.thumbFilename = os.path.basename(thumbPath)

		ai = el.getAttributeNode('audioImage')
		if (not ai == None):
			print("loadMedia c")
			#todo: consolidate this code into a function...
			pbl = gtk.gdk.PixbufLoader()
			import base64
			data = base64.b64decode( ai.nodeValue )
			pbl.write(data)
			pbl.close()
			audioImg = pbl.get_pixbuf()

			audioImagePath = os.path.join(self.ca.journalPath, "audioImage.jpg")
			audioImagePath = self.getUniqueFilepath( audioImagePath, 0 )
			#todo: use lossless since multiple savings?
			audioImg.save(audioImagePath, "jpeg", {"quality":"85"} )

			recd.audioImageFilename = os.path.basename(audioImagePath)


		print("addToHash:", addToHash )
		if (addToHash):
			hash.append( recd )


	def selectLatestThumbs( self, type ):
		p_mx = len(self.mediaHashs[type])
		p_mn = max(p_mx-self.ca.ui.numThumbs, 0)
		#gobject.idle_add(self.setupThumbs, type, p_mn, p_mx)
		self.setupThumbs( type, p_mn, p_mx )


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
				self.stopRecordingVideo()
		elif (self.MODE == self.MODE_AUDIO):
			if (not self.RECORDING):
				self.startRecordingAudio()
			else:
				self.stopRecordingAudio()





	def stopRecordingAudio( self ):
		self.setUpdating( True )
		self.ca.glive.stopRecordingAudio( )
		self.setRecording( False )


	def saveAudio( self, tempPath, pixbuf ):
		print("save audio")
		self.setUpdating( True )
		#todo: necc?
		self.ca.ui.hideLiveWindows()
		self.ca.ui.hidePlayWindows()

		recd = self.createNewRecorded( self.TYPE_AUDIO )

		oggPath = os.path.join(self.ca.journalPath, recd.mediaFilename)

		#todo: need to save the fullpixbuf to the xml only for display (for now, thumbnail)
		thumbPath = os.path.join(self.ca.journalPath, recd.thumbFilename)
		thumbImg = self.generateThumbnail(pixbuf, float(0.1671875))

		print( "ok...")
		thumbImg.write_to_png(thumbPath)

		imagePath = os.path.join(self.ca.journalPath, "audioPicture.png")
		print( "ip1", imagePath )
		imagePath = self.getUniqueFilepath( imagePath, 0 )
		print( "ip2", imagePath )
		pixbuf.save( imagePath, "png", {} )
		recd.audioImageFilename = imagePath

		#todo: unneccassary to move to oggpath? or temp should *be* oggpath
		shutil.move(tempPath, oggPath)

		#at this point, we have both audio and thumb sapath, so we can save the recd
		self.createNewRecordedMd5Sums( recd )

		audioHash = self.mediaHashs[self.TYPE_AUDIO]
		audioHash.append( recd )
		self.thumbAdded( self.TYPE_AUDIO )

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
		self.meshShareRecd( recd )



	def meshShareRecd( self, recd ):
		#hey, i just took a cool video.audio.photo!  let me show you!
		if (self.ca.meshClient != None):
			self.ca.meshClient.notifyBudsOfNewPhoto( recd )


	def cannotSaveVideo( self ):
		print("bad recorded video")
		self.doPostSaveVideo()


	def doPostSaveVideo( self ):
		#resume live video from the camera (if the activity is active)
		if (self.ca.ACTIVE):
			self.ca.ui.updateVideoComponents()
			self.ca.glive.play()

		self.setRecording( False )
		self.setUpdating( False )


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
		self.addRecd( recd )

		self.meshShareRecd( recd )



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
		print( "1 adding recd... ", recd.type, recd )

		#todo: sort on time-taken, not on their arrival time over the mesh (?)
		self.mediaHashs[recd.type].append( recd )

		#updateUi
		self.thumbAdded( recd.type )

		self.setUpdating( False )
		print( "2 adding recd... ", self.mediaHashs[recd.type] )

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
		titleStarter = ""
		if (type == self.TYPE_PHOTO):
			mediaFilename = mediaFilename + ".jpg"
			titleStarter = "Photo"
		if (type == self.TYPE_VIDEO):
			mediaFilename = mediaFilename + ".ogv"
			titleStarter = "Video"
		if (type == self.TYPE_AUDIO):
			mediaFilename = mediaFilename + ".ogg"
			titleStarter = "Audio"
		mediaFilename = self.getUniqueFilepath( mediaFilename, 0 )
		recd.mediaFilename = mediaFilename

		thumbFilename = mediaThumbFilename + "_thumb.jpg"
		thumbFilename = self.getUniqueFilepath( thumbFilename, 0 )
		recd.thumbFilename = thumbFilename

		recd.photographer = self.ca.nickName
		recd.title = titleStarter + " by " + str(recd.photographer)

		recd.colorStroke = self.ca.ui.colorStroke
		recd.colorFill = self.ca.ui.colorFill

		return recd


	def getUniqueFilepath( self, path, i ):
		pathOb = os.path.abspath( path )
		if (os.path.exists(pathOb)):
			i = i+1
			newPath = os.path.join( os.path.dirname(pathOb), str( str(i) + os.path.basename(pathOb) ) )
			path = self.getUniqueFilepath( str(newPath), i )
		else:
			return path


	def createNewRecordedMd5Sums( self, recd ):
		#load the thumbfile
		thumbFile = os.path.join(self.ca.journalPath, recd.thumbFilename)
		thumbMd5 = self.md5File( thumbFile )
		recd.thumbMd5 = thumbMd5
		#t = os.open( thumbFile, os.O_RDONLY )
		tBytes = os.stat(thumbFile)[7]
		recd.thumbBytes = tBytes
		#t.close()

		#load the mediafile
		mediaFile = os.path.join(self.ca.journalPath, recd.mediaFilename)
		mediaMd5 = self.md5File( mediaFile )
		recd.mediaMd5 = mediaMd5
		#m = os.open( mediaFile, os.O_RDONLY )
		mBytes = os.stat(mediaFile)[7]
		recd.mediaBytes = mBytes
		#m.close()


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

		#update your own ui
		self.setupThumbs(recd.type, mn, mn+self.ca.ui.numThumbs)


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