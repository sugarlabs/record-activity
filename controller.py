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
import _sugar
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

from color import Color
from polygon import Polygon

class Controller:

	def __init__( self ):
		#our dirs
		self._basepath = activity.get_bundle_path()
		self.journalPath = os.path.join(os.path.expanduser("~"), "Journal", "camera")
		if (not os.path.exists(self.journalPath)):
			os.makedirs(self.journalPath)

		self.photoHash = []
		self.movieHash = []
		self.journalIndex = os.path.join(self.journalPath, 'camera_index.xml')

		if (os.path.exists(self.journalIndex)):
			doc = parse( os.path.abspath(self.journalIndex) )
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

		#the current image
		self._img = None

		#container
		self._frame = None
		#menubar
		self._mb = None
		#img display
		self._id = None
		#video slot for live video
		self._livevideo = None
		#video slot for playback of video
		self._playvideo = None
		#thumbs
		self._thuPho = None
		self._thuVid = None

		self._w = gtk.gdk.screen_width( )
		self._h = gtk.gdk.screen_height( )
		self.loadColors()
		self.loadGfx()
		self.setConstants()

	def setup( self ):
		p_mx = len(self.photoHash)
		p_mn = max(p_mx-self._thuPho.numButts, 0)
		gobject.idle_add(self.setupThumbs, self.photoHash, self._thuPho, p_mn, p_mx)
		v_mx = len(self.movieHash)
		v_mn = max(v_mx-self._thuVid.numButts, 0)
		gobject.idle_add(self.setupThumbs, self.movieHash, self._thuVid, v_mn, v_mx)

	def inFocus( self, widget, event ):
		if (self.SHOW == self.SHOW_LIVE):
			self._livevideo.playa.play()
		if (self.SHOW == self.SHOW_PLAY):
			self._playvideo.playa.play()

	def outFocus( self, widget, event ):
		if (self.SHOW == self.SHOW_LIVE):
			self._livevideo.playa.stop()
		if (self.SHOW == self.SHOW_PLAY):
			self._playvideo.playa.stop()

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
				img = _sugar.cairo_surface_from_gdk_pixbuf(pb)
				thumbTray.addThumb(img, imgPath_s)
			else:
				removes.append(each)

		for each in removes:
			hash.remove(each)
		if (len(removes) > 0):
			self.updatePhotoIndex()

		self._frame.setDefaultCursor()
		self.UPDATING = False

	def getJournalPath( self ):
		return self.journalPath

	def openShutter( self ):
		if (self.isPhotoMode()):
			self.startTakingPicture()
		elif (self.isVideoMode()):
			self.startRecordingVideo()

	def showLive( self ):
		self._img = None
		if (self.DONE):
			self._img = self.modDoneImg

		self.SHOW = self.SHOW_LIVE

		#if you were playin' anything, time to stop
		self._playvideo.playa.stop()
		self._playvideo.hide()

		if not (self.DONE):
			self._livevideo.show()
			self._livevideo.playa.play()
			pass

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
		self.DONE = True

		if (self.DONE):
			self._img = self.modDoneImg
		else:
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
		thumb_fn = nowtime_s + "_thumb.png"
		thumbpath = os.path.join(self.journalPath, thumb_fn)

		thumbImg = self.generateThumbnail(pixbuf, self._thuPho.tscale)
		thumbImg.write_to_png(thumbpath)

		self.photoHash.append( (nowtime, self.nickName, nowtime_fn, thumb_fn) )
		self.updatePhotoIndex()
		self.thumbAdded(self._thuPho, self.photoHash, thumbImg, imgpath)

		self._frame.setDefaultCursor()
		self.UPDATING = False

	def generateThumbnail( self, pixbuf, scale ):
		#need to generate thumbnail version here
		thumbImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, self._thuPho.tw, self._thuPho.th)
		tctx = cairo.Context(thumbImg)
		img = _sugar.cairo_surface_from_gdk_pixbuf(pixbuf)

		tctx.scale(scale, scale)
		tctx.set_source_surface(img, 0, 0)
		tctx.paint()
		return thumbImg

	def deleteThumb( self, path, hash ):
		pathName = os.path.split(path)
		deleteMe = None
		for each in hash:
			if (pathName[1] == each[2]):
				deleteMe = each
		if (deleteMe == None):
			return

		if (os.path.isfile(path)):
			os.remove(path)
		thumbPath = getThumbPath(hash,path)
		if (thumbPath != None):
			if (os.path.isfile(thumbPath)):
				os.remove(thumbPath)

		hash.remove(deleteMe)
		self.updatePhotoIndex()

		start = self.thuPhoStart
		thumbs = self._thuPho
		if (self.MODE == self.MODE_VIDEO):
			start = self.vidPhoStart
			thumbs = self._thuVid

		#if not at the end..., then slide down
		if ( (start+thumbs) < len(hash) ):
			each = hash[start+thumbs.numButts]
			imgPath = os.path.join(self.journalPath, each[2])
			imgPath_s = os.path.abspath(imgPath)
			if (os.path.isfile(imgPath_s)):
				pb = gtk.gdk.pixbuf_new_from_file(imgPath_s)
				img = _sugar.cairo_surface_from_gdk_pixbuf(pb)
				self._thuPho.addThumb(img, imgPath_s)

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
		#pixbuf.save(imgpath, "jpeg")

		shutil.move(tempPath, oggPath)

		self.movieHash.append( (nowtime, self.nickName, movieFn, thumbFn) )
		self.updatePhotoIndex()
		self.thumbAdded(self._thuVid, self.movieHash, thumbImg, oggPath)

	#if we're not at the end, move to the end...
	#otherwise, just append to the end
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

		#if we're far along in picture taking just push along
		#if (thuStart > thuPanel.numButts):
		#	if (hash == self.photoHash):
		#		self.thuPhoStart = self.thuPhoStart + 1
		#	elif (hash == self.movieHash):
		#		self.thuVidStart = self.thuVidStart + 1

		#thuPanel.addThumb(thumbImg, path)

	def showImg( self, imgPath ):
		self.SHOW = self.SHOW_STILL

		if (self._img == None):
			self._livevideo.hide()
			self._playvideo.hide()

		pixbuf = gtk.gdk.pixbuf_new_from_file(imgPath)
		self._img = _sugar.cairo_surface_from_gdk_pixbuf(pixbuf)
		self._id.redraw()

	def showVid( self, vidPath = None ):
		if (vidPath != None):
			self.DONE = True
			self.UPDATING = True
			self._frame.setWaitCursor()

			self._img = self.modWaitImg
			self.SHOW = self.SHOW_PLAY
			self._id.redraw()

			self._livevideo.hide()
			self._livevideo.playa.stop()
			self._playvideo.show()
			vp = "file://" + vidPath
			self._playvideo.playa.setLocation(vp)
			self._frame.setDefaultCursor()
			self.UPDATING = False

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

	def isVideoMode( self ):
		return self.MODE == self.MODE_VIDEO

	def isPhotoMode( self ):
		return self.MODE == self.MODE_PHOTO

	def loadGfx( self ):
		#load svgs
		polSvg_f = open(os.path.join(self._basepath, 'polaroid.svg'), 'r')
		polSvg_d = polSvg_f.read()
		polSvg_f.close()
		self.polSvg = self.loadSvg( polSvg_d, None, None )

		camSvg_f = open(os.path.join(self._basepath, 'shutter_button.svg'), 'r')
		camSvg_d = camSvg_f.read()
		camSvg_f.close()
		self.camSvg = self.loadSvg( camSvg_d, None, None )
		
		camInvSvg_f = open( os.path.join(self._basepath, 'shutter_button_invert.svg'), 'r')
		camInvSvg_d = camInvSvg_f.read()
		camInvSvg_f.close()
		self.camInvSvg = self.loadSvg(camInvSvg_d, None, None)

		camRecSvg_f = open(os.path.join(self._basepath, 'shutter_button_record.svg'), 'r')
		camRecSvg_d = camRecSvg_f.read()
		camRecSvg_f.close()
		self.camRecSvg = self.loadSvg( camRecSvg_d, None, None)

		self.nickName = profile.get_nick_name()

		#sugar colors, replaced with b&w b/c of xv issues
		color = profile.get_color()
		fill = color.get_fill_color()
		stroke = color.get_stroke_color()
		self.colorFill = self._colWhite._hex
		self.colorStroke = self._colBlack._hex

		butPhoSvg_f = open(os.path.join(self._basepath, 'thumb_photo.svg'), 'r')
		butPhoSvg_d = butPhoSvg_f.read()
		self.thumbPhotoSvg = self.loadSvg(butPhoSvg_d, self.colorStroke, self.colorFill)
		butPhoSvg_f.close()

		butVidSvg_f = open(os.path.join(self._basepath, 'thumb_video.svg'), 'r')
		butVidSvg_d = butVidSvg_f.read()
		self.thumbVideoSvg = self.loadSvg(butVidSvg_d, self.colorStroke, self.colorFill)
		butVidSvg_f.close()

		closeSvg_f = open(os.path.join(self._basepath, 'thumb_close.svg'), 'r')
		closeSvg_d = closeSvg_f.read()
		self.closeSvg = self.loadSvg(closeSvg_d, self.colorStroke, self.colorFill)
		closeSvg_f.close()

		menubarPhoto_f = open( os.path.join(self._basepath, 'menubar_photo.svg'), 'r' )
		menubarPhoto_d = menubarPhoto_f.read()
		self.menubarPhoto = self.loadSvg( menubarPhoto_d, self._colWhite._hex, self._colMenuBar._hex )
		menubarPhoto_f.close()

		menubarVideo_f = open( os.path.join(self._basepath, 'menubar_video.svg'), 'r' )
		menubarVideo_d = menubarVideo_f.read()
		self.menubarVideo = self.loadSvg( menubarVideo_d, self._colWhite._hex, self._colMenuBar._hex)
		menubarVideo_f.close()

		modVidF = os.path.join(self._basepath, 'mode_video.png')
		modVidPB = gtk.gdk.pixbuf_new_from_file(modVidF)
		self.modVidImg = _sugar.cairo_surface_from_gdk_pixbuf(modVidPB)

		modPhoF = os.path.join(self._basepath, 'mode_photo.png')
		modPhoPB = gtk.gdk.pixbuf_new_from_file(modPhoF)
		self.modPhoImg = _sugar.cairo_surface_from_gdk_pixbuf(modPhoPB)

		modWaitF = os.path.join(self._basepath, 'mode_wait.png')
		modWaitPB = gtk.gdk.pixbuf_new_from_file(modWaitF)
		self.modWaitImg = _sugar.cairo_surface_from_gdk_pixbuf(modWaitPB)

		modDoneF = os.path.join(self._basepath, 'mode_restart.png')
		modDonePB = gtk.gdk.pixbuf_new_from_file(modDoneF)
		self.modDoneImg = _sugar.cairo_surface_from_gdk_pixbuf(modDonePB)

		#reset there here for uploading to server
		self.fill = color.get_fill_color()
		self.stroke = color.get_stroke_color()
		key = profile.get_pubkey()
		key_hash = util._sha_data(key)
		self.hashed_key = util.printable_hash(key_hash)

	def loadColors( self ):
		self._colBlack = Color( 0, 0, 0, 255 )
		self._colWhite = Color( 255, 255, 255, 255 )
		self._colRed = Color( 255, 0, 0, 255 )
		self._colThumbTray = Color( 255, 255, 255, 255 )
		#Color( 224, 224, 224, 255 )
		self._colMenuBar = Color( 0, 0, 0, 255 )
		#Color( 65, 65, 65, 255 )

	def loadSvg( self, data, stroke, fill ):
		if ((stroke == None) or (fill == None)):
			return rsvg.Handle( data=data )

		entity = '<!ENTITY fill_color "%s">' % fill
		data = re.sub('<!ENTITY fill_color .*>', entity, data)

		entity = '<!ENTITY stroke_color "%s">' % stroke
		data = re.sub('<!ENTITY stroke_color .*>', entity, data)

		return rsvg.Handle( data=data )

	def setConstants( self ):
		#THUMB TRAY TYPES
		self.THUMB_PHOTO = 0
		self.THUMB_VIDEO = 1

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

		self.DONE = False
