#!/usr/bin/env python

import urllib
import string
import fnmatch
import os
import random
import cairo
import gtk
import pygtk
pygtk.require('2.0')
import rsvg
import re
import math
import gtk.gdk
import sugar.env
import random
import time
import shutil
import time
import gobject
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse
from sugar import profile
from sugar import util
from sugar.activity import activity

import _camera

class Controller:
	def __init__( self, pca ):
		self.ca = pca
		self.setConstants()
		self.journalIndex = os.path.join(self.ca.journalPath, 'camera_index.xml')
		self.fillPhotoHash( self.journalIndex )

	def initPostUI( self ):
		self.setup()

	def fillPhotoHash( self, index ):
		self.photoHash = []
		self.movieHash = []
		if (os.path.exists(index)):
			doc = parse( os.path.abspath(index) )
			photos = doc.documentElement.getElementsByTagName('photo')
			for each in photos:
				time = each.getAttribute('time')
				name = each.getAttribute('name')
				path = each.getAttribute('path')
				thmb = each.getAttribute('thumb')
				self.photoHash.append( ( int(time), name, path, thmb ) )
			movies = doc.documentElement.getElementsByTagName('video')
			for each in movies:
				time = each.getAttribute('time')
				name = each.getAttribute('name')
				path = each.getAttribute('path')
				thmb = each.getAttribute('thumb')
				self.movieHash.append( ( int(time), name, path, thmb ) )


	def setup( self ):
		p_mx = len(self.photoHash)
		p_mn = max(p_mx-self._thuPho.numButts, 0)
		gobject.idle_add(self.setupThumbs, self.photoHash, self._thuPho, p_mn, p_mx)
		v_mx = len(self.movieHash)
		v_mn = max(v_mx-self._thuVid.numButts, 0)
		gobject.idle_add(self.setupThumbs, self.movieHash, self._thuVid, v_mn, v_mx)


	def setupThumbs( self, hash, thumbTray, mn, mx ):
		self.UPDATING = True
		self._frame.setWaitCursor()

		if (hash == self.photoHash):
			self.thuPhoStart = mn
		elif (hash == self.movieHash):
			self.thuVidStart = mn

		thumbTray.removeButtons()

		removes = []
		for i in range (mn, mx):
			each = hash[i]
			thmbPath = os.path.join(self.journalPath, each[3])
			thmbPath_s = os.path.abspath(thmbPath)
			imgPath = os.path.join(self.journalPath, each[2])
			imgPath_s = os.path.abspath(imgPath)
			if ( (os.path.isfile(thmbPath_s)) and (os.path.isfile(imgPath_s)) ):
				pb = gtk.gdk.pixbuf_new_from_file(thmbPath_s)
				img = _camera.cairo_surface_from_gdk_pixbuf(pb)
				thumbTray.addThumb(img, imgPath_s)
			else:
				removes.append(each)

		for each in removes:
			hash.remove(each)
		if (len(removes) > 0):
			self.updatePhotoIndex()

		self._frame.setDefaultCursor()
		self.UPDATING = False


	def openShutter( self ):
		if (self.isPhotoMode()):
			self.startTakingPicture()
		elif (self.isVideoMode()):
			self.startRecordingVideo()


	def showLive( self ):
		self._img = None

		self.SHOW = self.SHOW_LIVE

		#if you were playin' anything, time to stop
		self._playvideo.playa.stop()
		self._playvideo.hide()

		self._livevideo.show()
		self._livevideo.playa.play()

		self._id.redraw()


	#todo: hide the video widget here by moving it offscreen until recording begins
	def startRecordingVideo( self ):
		self.UPDATING = True
		self._frame.setWaitCursor()
		self.SHOW = self.SHOW_RECORD
		self._img = self.modWaitImg
		self._id.redraw()
		self._livevideo.playa.startRecordingVideo()
		self._frame.setDefaultCursor()
		self.UPDATING = False


	def stopRecordingVideo( self ):
		self.UPDATING = True
		self._frame.setWaitCursor()

		self.SHOW = self.SHOW_PROCESSING
		self._livevideo.hide()
		self._id.redraw()
		self._livevideo.playa.stopRecordingVideo()


	def stoppedRecordingVideo( self ):
		self._livevideo.show()
		self._livevideo.playa.play()

		self.SHOW = self.SHOW_LIVE
		self._id.redraw()

		self._frame.setDefaultCursor()
		self.UPDATING = False


	def startTakingPicture( self ):
		self.UPDATING = True
		self._frame.setWaitCursor()
		self._livevideo.playa.takePic()


	def setPic( self, pixbuf ):
		nowtime = int(time.time())
		nowtime_s = str(nowtime)
		nowtime_fn = nowtime_s + ".jpg"
		imgpath = os.path.join(self.journalPath, nowtime_fn)
		pixbuf.save( imgpath, "jpeg" )
		thumb_fn = nowtime_s + "_thumb.jpg"
		thumbpath = os.path.join(self.journalPath, thumb_fn)

		thumbImg = self.generateThumbnail(pixbuf, self._thuPho.tscale)
		thumbImg.write_to_png(thumbpath)
		#thumb = pixbuf.scale_simple( self._thuPho.tw, self._thuPho.th, gtk.gdk.INTERP_BILINEAR )
		#thumb.save( thumbpath, "jpeg", {"quality":"85"} )

		self.photoHash.append( (nowtime, self.nickName, nowtime_fn, thumb_fn) )
		self.updatePhotoIndex()
		self.thumbAdded(self._thuPho, self.photoHash, thumbImg, imgpath)

		self._frame.setDefaultCursor()
		self.UPDATING = False

		#hey, i just took a cool picture!  let me show you!
		self.meshClient.notifyBudsOfNewPic()


	#outdated?
	def generateThumbnail( self, pixbuf, scale ):
		#need to generate thumbnail version here
		thumbImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, self._thuPho.tw, self._thuPho.th)
		tctx = cairo.Context(thumbImg)
		img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)

		tctx.scale(scale, scale)
		tctx.set_source_surface(img, 0, 0)
		tctx.paint()
		return thumbImg


	def thumbDeleted( self, path, hash, thuPanel ):
		pathName = os.path.split(path)
		deleteMe = None
		for each in hash:
			if (pathName[1] == each[2]):
				deleteMe = each
		if (deleteMe == None):
			return

		if (os.path.isfile(path)):
			os.remove(path)

		thumbPath = self.getThumbPath(hash,path)
		if (thumbPath != None):
			if (os.path.isfile(thumbPath)):
				os.remove(thumbPath)

		hash.remove(deleteMe)
		self.updatePhotoIndex()

		#start = self.thuPhoStart
		#thumbs = self._thuPho
		#if (self.MODE == self.MODE_VIDEO):
		#	start = self.vidPhoStart
		#	thumbs = self._thuVid

		mx = len(hash)
		mn = max(mx-thuPanel.numButts, 0)
		self.setupThumbs(hash, thuPanel, mn, mx)

		#todo: only show this if you've deleted the pic you're looking at!
		if (self.MODE == self.MODE_PHOTO):
			self.SHOW = self.SHOW_STILL
			self._img = self.modPhoImg
		if (self.MODE == self.MODE_VIDEO):
			self.SHOW == self.SHOW_STILL
			self._img = self.modVidImg
		self._id.redraw()


	def getThumbPath( self, hash, path ):
		pathSplit = os.path.split(path)
		for each in hash:
			if (each[2] == pathSplit[1]):
				return os.path.join(self.journalPath, each[3])


	def updatePhotoIndex( self ):
		#delete all old htmls
		files = os.listdir(self.journalPath)
		for file in files:
			if (len(file) > 5):
				if ("html" == file[len(file)-4:]):
					html = os.path.join(self.journalPath, file)
					os.remove(html)

		impl = getDOMImplementation()
		album = impl.createDocument(None, "album", None)
		root = album.documentElement
		for i in range (0, len(self.photoHash)):
			each = self.photoHash[i]

			photo = album.createElement('photo')
			root.appendChild(photo)
			photo.setAttribute("time", str(each[0]))
			photo.setAttribute("name", each[1])
			photo.setAttribute("path", each[2])
			photo.setAttribute("thumb", each[3])
			photo.setAttribute("colorStroke", str(self.colorStroke) )
			photo.setAttribute("colorFill", str(self.colorFill) )
			photo.setAttribute("hashKey", str(self.hashed_key))

			htmlDoc = impl.createDocument(None, "html", None)
			html = htmlDoc.documentElement
			head = htmlDoc.createElement('head')
			html.appendChild(head)
			title = htmlDoc.createElement('title')
			head.appendChild(title)
			titleText = htmlDoc.createTextNode( "Your Photos" )
			title.appendChild(titleText)
			body = htmlDoc.createElement('body')
			html.appendChild(body)
			center = htmlDoc.createElement('center')
			body.appendChild(center)
			ahref = htmlDoc.createElement('a')
			center.appendChild(ahref)

			if (len(self.photoHash)>0):
				nextEach = self.photoHash[0]
				if (i < len(self.photoHash)-1):
					nextEach = self.photoHash[i+1]
				nextHtml = os.path.join(self.journalPath, str(nextEach[0])+".html")
				ahref.setAttribute('href', os.path.abspath(nextHtml))

			img = htmlDoc.createElement('img')
			img.setAttribute("width", "320")
			img.setAttribute("height", "240")
			ahref.appendChild(img)
			img.setAttribute('src', each[2])
			if (i == 0):
				f = open(os.path.join(self.journalPath, "index.html"), 'w')
				htmlDoc.writexml(f)
				f.close()
			else:
				f = open(os.path.join(self.journalPath, str(each[0])+".html"), 'w')
				htmlDoc.writexml(f)
				f.close()

		for i in range (0, len(self.movieHash)):
			each = self.movieHash[i]

			video = album.createElement('video')
			root.appendChild(video)
			video.setAttribute("time", str(each[0]))
			video.setAttribute("name", each[1])
			video.setAttribute("path", each[2])
			video.setAttribute("thumb", each[3])
			video.setAttribute("colorStroke", str(self.colorStroke) )
			video.setAttribute("colorFill", str(self.colorFill) )
			video.setAttribute("hashKey", str(self.hashed_key) )

		f = open( self.journalIndex, 'w')
		album.writexml(f)
		f.close()


	def setVid( self, pixbuf, tempPath ):
		nowtime = str(int(time.time()))
		thumbFn = nowtime + "_thumbnail.png"
		movieFn = nowtime + ".ogg"
		thumbPath = os.path.join(self.journalPath, thumbFn)
		oggPath = os.path.join(self.journalPath, movieFn)

		thumbImg = self.generateThumbnail(pixbuf, float(.66875) )
		thumbImg.write_to_png(thumbPath)
		#thumb = pixbuf.scale_simple( self._thuPho.tw, self._thuPho.th, gtk.gdk.INTERP_BILINEAR )
		#thumb.save( thumbpath, "jpeg", {"quality":"85"} )
		shutil.move(tempPath, oggPath)

		self.movieHash.append( (nowtime, self.nickName, movieFn, thumbFn) )
		self.updatePhotoIndex()
		self.thumbAdded(self._thuVid, self.movieHash, thumbImg, oggPath)


	def thumbAdded( self, thuPanel, hash, thumbImg, path ):
		thuStart = 0
		if (hash == self.photoHash):
			thuStart = self.thuPhoStart
		elif (hash == self.movieHash):
			thuStart = self.thuVidStart

		#if we're somewhere at the back of the queue...
		#print( len(hash), thuPanel.numButts, thuStart )
		#if (thuStart < len(hash)):
		mx = len(hash)
		mn = max(mx-thuPanel.numButts, 0)
		self.setupThumbs(hash, thuPanel, mn, mx)
		return


	def doVideoMode( self ):
		if (self.MODE == self.MODE_VIDEO):
			return

		self._mb.redraw()
		self._thuVid.show()
		self._thuPho.hide()

		#if you've been looking at still photos, let the user know they've switched modes
		if (self.SHOW == self.SHOW_STILL):
			self._img = self.modVidImg
			self._id.redraw()

		self.MODE = self.MODE_VIDEO


	def doPhotoMode( self ):
		if (self.MODE == self.MODE_PHOTO):
			return

		if ( (self.SHOW == self.SHOW_RECORD) or (self.SHOW == self.SHOW_PROCESSING)):
			return

		self._mb.redraw()
		self._thuPho.show()
		self._thuVid.hide()

		#if you were looking at stills, switched to vid mode, and came back...
		if (self.SHOW == self.SHOW_STILL):
			self._img = self.modPhoImg
			self._id.redraw()
		#if you were looking at a playback video, then click photo mode
		if (self.SHOW == self.SHOW_PLAY):
			self.SHOW = self.SHOW_STILL
			self._img = self.modPhoImg
			self._id.redraw()
			self._playvideo.playa.stop()
			self._playvideo.hide()

		self.MODE = self.MODE_PHOTO


	def setConstants( self ):
		#pics or vids?
		self.MODE_PHOTO = 0
		self.MODE_VIDEO = 1
		self.MODE = self.MODE_PHOTO

		#are we showing or ready to record?
		self.SHOW_LIVE = 0
		self.SHOW_PLAY = 1
		self.SHOW_STILL = 2
		self.SHOW_RECORD = 3
		self.SHOW_PROCESSING = 4
		self.SHOW = self.SHOW_LIVE

		self.thuPhoStart = 0
		self.thuVidStart = 0

		self.UPDATING = True
