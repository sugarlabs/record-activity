#!/usr/bin/env python

#todo: mode switch between photo & video
#todo: mode switch between play video & live video
#todo: mode switch between play video & record video
#todo: add the white borders around pip

import gtk
from gtk import gdk
import gobject
import cairo
import os
#parse svg
import rsvg
#parse svg xml with regex
import re
#we do some image conversion when loading gfx
import _camera
import time
from time import strftime
import math

from sugar import profile
from sugar import util
#to get the toolbox
from sugar.activity import activity
from sugar.graphics.radiotoolbutton import RadioToolButton

from color import Color
from p5 import P5
from p5_button import P5Button
from p5_button import Polygon
from p5_button import Button
from glive import LiveVideoWindow
from gplay import PlayVideoWindow

#for debug testing
from recorded import Recorded

import _camera

class UI:

	def __init__( self, pca ):
		self.ca = pca
		self.loadColors()
		self.loadGfx()

		#ui modes
		self.photoMode = True
		self.fullScreen = False
		self.liveMode = True

		#thumb dimensions:
		self.tw = 107
		self.th = 80
		self.thumbSvgW = 124
		self.thumbSvgH = 124
		#video size:
		self.vw = 640
		self.vh = 480
		#pip size:
		self.pipw = 160
		self.piph = 120
		self.pipBorderW = self.pipw + 7
		self.pipBorderH = self.piph + 7

		#maximize size:
		self.maxw = 49
		self.maxh = 49
		#number of thumbs
		self.numThumbs = 7
		#component spacing
		self.inset = 10
		#prep for when to show
		self.exposed = False
		self.mapped = False

		self.shownRecd = None

		#this includes the default sharing tab
		toolbox = activity.ActivityToolbox(self.ca)
		self.ca.set_toolbox(toolbox)
		cToolbar = ModeToolbar(self.ca)
		toolbox.add_toolbar( ('Mode'), cToolbar)
		#sToolbar = SearchToolbar(self.ca)
		#toolbox.add_toolbar( ('Search'), sToolbar)
		toolbox.show()

		self.mainBox = gtk.VBox()
		self.ca.set_canvas(self.mainBox)

		topBox = gtk.HBox()
		self.mainBox.pack_start(topBox)

		#insert entry fields on left
		infoBox = gtk.VBox(spacing=self.inset)
		infoBox.set_border_width(self.inset)
		topBox.pack_start(infoBox)

		namePanel = gtk.HBox(spacing=self.inset)
		infoBox.pack_start(namePanel, expand=False)
		nameLabel = gtk.Label("Name:")
		namePanel.pack_start( nameLabel, expand=False )
		self.nameTextfield = gtk.Label("")
		self.nameTextfield.set_alignment(0, .5)
		namePanel.pack_start(self.nameTextfield)

		photographerPanel = gtk.HBox(spacing=self.inset)
		infoBox.pack_start(photographerPanel, expand=False)
		photographerLabel = gtk.Label("Recorder:")
		photographerPanel.pack_start(photographerLabel, expand=False)
		self.photographerNameLabel = gtk.Label("")
		self.photographerNameLabel.set_alignment(0, .5)
		photographerPanel.pack_start(self.photographerNameLabel)

		datePanel = gtk.HBox(spacing=self.inset)
		infoBox.pack_start(datePanel, expand=False)
		dateLabel = gtk.Label("Date:")
		datePanel.pack_start(dateLabel, expand=False)
		self.dateDateLabel = gtk.Label("")
		self.dateDateLabel.set_alignment(0, .5)
		datePanel.pack_start(self.dateDateLabel)

		self.showLiveVideoTags()

		self.shutterButton = gtk.Button()
		self.shutterButton.set_image( self.shutterImg )
		self.shutterButton.connect("clicked", self.shutterClickCb)
		shutterBox = gtk.EventBox()
		shutterBox.add( self.shutterButton )
		shutterBox.set_border_width( 50 )
		infoBox.pack_start(shutterBox, expand=True)

		#video, scrubber etc on right
		videoBox = gtk.VBox()
		videoBox.set_size_request(self.vw, -1)
		topBox.pack_start(videoBox, expand=False)
		self.backgdCanvas = BackgroundCanvas(self)
		self.backgdCanvas.set_size_request(self.vw, self.vh)
		videoBox.pack_start(self.backgdCanvas, expand=False)
		self.videoScrubPanel = gtk.EventBox()
		videoBox.pack_end(self.videoScrubPanel, expand=True)

		thumbnailsEventBox = gtk.EventBox()
		thumbnailsEventBox.modify_bg( gtk.STATE_NORMAL, self.colorTray.gColor )
		thumbnailsEventBox.set_size_request( -1, 150 )
		thumbnailsBox = gtk.HBox( )
		thumbnailsEventBox.add( thumbnailsBox )
		self.mainBox.pack_end(thumbnailsEventBox, expand=False)

		self.leftThumbButton = gtk.Button()
		self.leftThumbButton.connect( "clicked", self._leftThumbButton )
		self.setupThumbButton( self.leftThumbButton, "left-thumb-sensitive" )
		leftThumbEventBox = gtk.EventBox()
		leftThumbEventBox.set_border_width(self.inset)
		leftThumbEventBox.modify_bg( gtk.STATE_NORMAL, self.colorTray.gColor )
		leftThumbEventBox.add( self.leftThumbButton )
		thumbnailsBox.pack_start( leftThumbEventBox, expand=False )
		self.thumbButts = []
		for i in range (0, self.numThumbs):
			thumbButt = ThumbnailCanvas(self)
			thumbnailsBox.pack_start( thumbButt, expand=True )
			self.thumbButts.append(thumbButt)
		self.rightThumbButton = gtk.Button()
		self.rightThumbButton.connect( "clicked", self._rightThumbButton )
		self.setupThumbButton( self.rightThumbButton, "right-thumb-sensitive" )
		rightThumbEventBox = gtk.EventBox()
		rightThumbEventBox.set_border_width(self.inset)
		rightThumbEventBox.modify_bg( gtk.STATE_NORMAL, self.colorTray.gColor )
		rightThumbEventBox.add( self.rightThumbButton )
		thumbnailsBox.pack_start( rightThumbEventBox, expand=False )

		#image windows
		self.livePhotoWindow = PhotoCanvasWindow(self)
		self.livePhotoCanvas = PhotoCanvas(self)
		self.livePhotoWindow.setPhotoCanvas(self.livePhotoCanvas)
		self.livePhotoWindow.set_transient_for(self.ca)
		self.livePhotoWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.livePhotoWindow.set_decorated(False)

		self.liveVideoWindow = LiveVideoWindow()
		self.liveVideoWindow.set_transient_for(self.livePhotoWindow)
		self.liveVideoWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.liveVideoWindow.set_decorated(False)
		self.liveVideoWindow.set_glive(self.ca.glive)
		self.liveVideoWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.liveVideoWindow.connect("button_release_event", self.liveButtonRelease)

		self.liveMaxWindow = MaxWindow(self, True)
		self.liveMaxWindow.set_transient_for(self.liveVideoWindow)
		self.liveMaxWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.liveMaxWindow.set_decorated(False)

		self.hideLiveWindows()

		#video playback windows
		self.playOggWindow = PlayVideoWindow()
		self.playOggWindow.set_gplay(self.ca.gplay)
		self.playOggWindow.set_transient_for(self.liveMaxWindow)
		self.playOggWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playOggWindow.set_decorated(False)

		self.playLiveWindow = LiveVideoWindow()
		self.playLiveWindow.set_transient_for(self.playOggWindow)
		self.playLiveWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playLiveWindow.set_decorated(False)
		self.playLiveWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.playLiveWindow.connect("button_release_event", self.playLiveButtonReleaseCb)

		self.playMaxWindow = MaxWindow(self, False)
		self.playMaxWindow.set_transient_for(self.playLiveWindow)
		self.playMaxWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playMaxWindow.set_decorated(False)

		self.hidePlayWindows()


		#only show the floating windows once everything is exposed and has a layout position
		self.ca.show_all()
		self.exposeId = self.ca.connect("expose-event", self.exposeEvent)
		self.livePhotoWindow.show_all()
		self.liveVideoWindow.show_all()
		self.mapId = self.liveVideoWindow.connect("map-event", self.mapEvent)
		self.liveMaxWindow.show_all()

		self.playOggWindow.show_all()
		self.playLiveWindow.show_all()
		self.playMaxWindow.show_all()

		self.enableEyeTracking( True )


	def showLiveVideoTags( self ):
		self.nameTextfield.set_label("Live Video")
		self.photographerNameLabel.set_label( str(self.ca.nickName) )
		self.dateDateLabel.set_label( "Today" )


	def updateShutterButton( self ):
		if (self.ca.m.UPDATING):
			self.shutterButton.set_sensitive( False )
			self.ca.ui.setWaitCursor()
			self.enableEyeTracking( False )
		else:
			self.shutterButton.set_sensitive( True )
			self.ca.ui.setDefaultCursor( )
			self.enableEyeTracking( True )


	def hideLiveWindows( self ):
		self.livePhotoWindow.resize(self.vw, self.vh)
		self.livePhotoWindow.move(-(self.vw+10), -(self.vh+10))
		self.liveVideoWindow.resize(self.vw, self.vh)
		self.liveVideoWindow.move(-(self.vw+10), -(self.vh+10))
		self.liveMaxWindow.resize(self.maxw, self.maxh)
		self.liveMaxWindow.move(-(self.maxw+10), -(self.maxh+10))


	def hidePlayWindows( self ):
		self.playOggWindow.resize(self.vw, self.vh)
		self.playOggWindow.move(-(self.vw+10), -(self.vh+10))
		self.playLiveWindow.resize(self.pipw, self.piph)
		self.playLiveWindow.move(-(self.pipw+10), -(self.piph+10))
		self.playMaxWindow.resize(self.maxw, self.maxh)
		self.playMaxWindow.move(-(self.maxw+10), -(self.maxh+10))


	def liveButtonRelease(self, widget, event):
		self.livePhotoCanvas.setImage(None)
		if (self.liveMode != True):
			self.liveMode = True
			self.updateVideoComponents()


	def playLiveButtonReleaseCb(self, widget, event):
		#if you are big on the screen, don't go changing anything, ok?
		if (self.liveMode):
			return

		self.ca.gplay.stop()
		self.liveMode = True
		self.startXV( self.playLiveWindow )

		#might need to hide video components here
		self.updateVideoComponents()


	def recordVideo( self ):
		#show the clock while this gets set up
		self.hideLiveWindows()
		self.hidePlayWindows()

		self.stopPlayVideoToRecord()

		#this blocks while recording gets started
		self.ca.glive.startRecordingVideo()

		#and now we show the live/recorded video at 640x480, setting liveMode on in case we were watching vhs earlier
		self.liveMode = True
		self.updateVideoComponents()


	def stopPlayVideoToRecord( self ):
		#if we're watching a movie...
		if (not self.ca.ui.liveMode):
			#stop the movie
			self.ca.gplay.stop()
			self.startXV( self.playLiveWindow )


	#this is called when a menubar button is clicked
	def updateModeChange(self):
		self.liveMode = True
		self.fullScreen = False
		self.photoMode = (self.ca.m.MODE == self.ca.m.MODE_PHOTO)

		self.hideLiveWindows()
		self.hidePlayWindows()

		#set up the x & xv x-ition (if need be)
		if (self.photoMode):
			self.ca.gplay.stop()
			self.startXV( self.liveVideoWindow )
		else:
			self.startXV( self.playLiveWindow )

		self.updateVideoComponents()


	def startXV(self, window):
		if (self.ca.glive.xv and self.ca.glive.window == window):
			return

		self.ca.glive.xv = True
		window.set_glive(self.ca.glive)
		self.ca.glive.stop()
		self.ca.glive.play()


	def doFullscreen( self ):
		self.fullScreen = not self.fullScreen
		self.updateVideoComponents()


	def setImgLocDim( self, win ):
		if (self.fullScreen):
			win.move( 0, 0 )
			win.resize( gtk.gdk.screen_width(), gtk.gdk.screen_height() )
		else:
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			win.move( vPos[0], vPos[1] )
			win.resize( self.vw, self.vh )

		win.show_all()


	def setPipLocDim( self, win ):
		win.resize( self.pipw, self.piph )

		if (self.fullScreen):
			win.move( self.inset, gtk.gdk.screen_height()-(self.inset+self.piph))
		else:
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			win.move( vPos[0]+self.inset, (vPos[1]+self.vh)-(self.piph+self.inset) )

		win.show_all()


	def setMaxLocDim( self, win ):
		if (self.fullScreen):
			win.move( gtk.gdk.screen_width()-(self.maxw+self.inset), self.inset )
		else:
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			win.move( (vPos[0]+self.vw)-(self.inset+self.maxw), vPos[1]+self.inset)

		win.show_all()


	def setupThumbButton( self, thumbButton, iconStringSensitive ):
		iconSet = gtk.IconSet()
		iconSensitive = gtk.IconSource()
		iconSensitive.set_icon_name(iconStringSensitive)
		iconSet.add_source(iconSensitive)

		iconImage = gtk.Image()
		iconImage.set_from_icon_set(iconSet, gtk.ICON_SIZE_BUTTON)
		thumbButton.set_image(iconImage)

		thumbButton.set_sensitive(False)
		thumbButton.set_relief(gtk.RELIEF_NONE)
		thumbButton.set_focus_on_click(False)
		thumbButton.set_size_request(80, -1)


	def shutterClickCb( self, arg ):
		self.ca.m.doShutter()


	def checkReadyToSetup(self):
		if (self.exposed and self.mapped):
			self.updateVideoComponents()
			self.ca.glive.play()


	#when your parent window is ready, turn on the feed of live video
	def mapEvent( self, widget, event ):
		self.liveVideoWindow.disconnect(self.mapId)
		self.mapped = True
		self.checkReadyToSetup()


	#initial setup of the panels
	def exposeEvent( self, widget, event):
		self.ca.disconnect(self.exposeId)
		self.exposed = True
		self.checkReadyToSetup( )


	def updateVideoComponents( self ):
		if (self.photoMode):
			if (self.liveMode):
				self.setImgLocDim( self.livePhotoWindow )
				self.setImgLocDim( self.liveVideoWindow )
				self.setMaxLocDim( self.liveMaxWindow )
			else:
				self.setImgLocDim( self.livePhotoWindow )
				self.setPipLocDim( self.liveVideoWindow )
				self.setMaxLocDim( self.liveMaxWindow )
		else:
			if (self.liveMode):
				self.playOggWindow.resize(self.vw, self.vh)
				self.playOggWindow.move(-(self.vw+10), -(self.vh+10))
				self.setImgLocDim( self.playLiveWindow )
				self.setMaxLocDim( self.playMaxWindow )
			else:
				self.setImgLocDim( self.playOggWindow )
				self.setMaxLocDim( self.playMaxWindow )
				self.setPipLocDim( self.playLiveWindow )


	def updateThumbs( self, addToTrayArray, left, start, right ):
		for i in range (0, len(self.thumbButts)):
			self.thumbButts[i].clear()

		for i in range (0, len(addToTrayArray)):
			self.thumbButts[i].setButton(addToTrayArray[i])

		if (left == -1):
			self.leftThumbButton.set_sensitive(False)
		else:
			self.leftThumbButton.set_sensitive(True)

		if (right == -1):
			self.rightThumbButton.set_sensitive(False)
		else:
			self.rightThumbButton.set_sensitive(True)

		self.startThumb = start
		self.leftThumbMove = left
		self.rightThumbMove = right


	def _leftThumbButton( self, args ):
		self.ca.m.setupThumbs( self.ca.m.MODE, self.leftThumbMove, self.leftThumbMove+self.numThumbs )


	def _rightThumbButton( self, args ):
		self.ca.m.setupThumbs( self.ca.m.MODE, self.rightThumbMove, self.rightThumbMove+self.numThumbs )


	#do we need to know the type, since we're showing based on the mode of the app?
	def showThumbSelection( self, recd ):
		if (recd.type == self.ca.m.TYPE_PHOTO):
			self.showPhoto( recd )
		if (recd.type == self.ca.m.TYPE_VIDEO):
			self.showVideo( recd )


	def deleteThumbSelection( self, recd ):
		#todo: test --> if this is the current selection, then clear it away here
		self.ca.m.deleteMedia( recd, self.startThumb )

		self.shownRecd = None
		self.livePhotoCanvas.setImage(None)
		self.liveMode = True
		self.updateVideoComponents()

		self.showLiveVideoTags()


	def showPhoto( self, recd ):
		self.shownRecd = recd
		imgPath = os.path.join(self.ca.journalPath, recd.mediaFilename)
		imgPath_s = os.path.abspath(imgPath)
		if ( os.path.isfile(imgPath_s) ):
			pixbuf = gtk.gdk.pixbuf_new_from_file(imgPath_s)
			img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)
			self.livePhotoCanvas.setImage(img)
			self.liveMode = False
			self.updateVideoComponents()
			self.photographerNameLabel.set_label( recd.photographer )
			self.nameTextfield.set_label( recd.name )
			self.dateDateLabel.set_label( strftime( "%a, %b %d, %I:%M:%S %p", time.localtime(recd.time) ) )


	def showVideo( self, recd ):

		if (self.ca.glive.xv):
			self.ca.glive.xv = False
			#redundant (?)
			#self.playLiveWindow.set_glive(self.ca.glive)
			self.ca.glive.stop()
			self.ca.glive.play()

		self.liveMode = False
		self.updateVideoComponents()

		videoUrl = "file://" + str(self.ca.journalPath) +"/"+ str(recd.mediaFilename)
		self.ca.gplay.setLocation(videoUrl)


	def setWaitCursor( self ):
		self.ca.window.set_cursor( gtk.gdk.Cursor(gtk.gdk.WATCH) )


	def setDefaultCursor( self ):
		self.ca.window.set_cursor( None )


	def loadGfx( self ):
		thumbPhotoSvgFile = open(os.path.join(self.ca.gfxPath, 'thumb_photo.svg'), 'r')
		self.thumbPhotoSvgData = thumbPhotoSvgFile.read()
		self.thumbPhotoSvg = self.loadSvg(self.thumbPhotoSvgData, self.colorStroke.hex, self.colorFill.hex)
		thumbPhotoSvgFile.close()

		thumbVideoSvgFile = open(os.path.join(self.ca.gfxPath, 'thumb_video.svg'), 'r')
		self.thumbVideoSvgData = thumbVideoSvgFile.read()
		self.thumbVideoSvg = self.loadSvg(self.thumbVideoSvgData, self.colorStroke.hex, self.colorFill.hex)
		thumbVideoSvgFile.close()

		closeSvgFile = open(os.path.join(self.ca.gfxPath, 'thumb_close.svg'), 'r')
		self.closeSvgData = closeSvgFile.read()
		self.closeSvg = self.loadSvg(self.closeSvgData, self.colorStroke.hex, self.colorFill.hex)
		closeSvgFile.close()

		modWaitSvgFile = open(os.path.join(self.ca.gfxPath, 'wait.svg'), 'r')
		modWaitSvgData = modWaitSvgFile.read()
		self.modWaitSvg = self.loadSvg( modWaitSvgData, None, None )
		modWaitSvgFile.close()

		eyeSvgFile = open(os.path.join(self.ca.gfxPath, 'eye.svg'), 'r')
		eyeSvgData = eyeSvgFile.read()
		self.eyeSvg = self.loadSvg(eyeSvgData, None, None )
		eyeSvgFile.close()

		maxEnlargeSvgFile = open(os.path.join(self.ca.gfxPath, 'max-enlarge.svg'), 'r')
		maxEnlargeSvgData = maxEnlargeSvgFile.read()
		self.maxEnlargeSvg = self.loadSvg(maxEnlargeSvgData, None, None )
		maxEnlargeSvgFile.close()

		#todo: this is only maxReduceSvgFile for mesh test
		self.maxReduceSvgFile = open(os.path.join(self.ca.gfxPath, 'max-reduce.svg'), 'r')
		maxReduceSvgData = self.maxReduceSvgFile.read()
		self.maxReduceSvg = self.loadSvg(maxReduceSvgData, None, None )
		self.maxReduceSvgFile.close()

		shutterImgFile = os.path.join(self.ca.gfxPath, 'shutter.png')
		shutterImgPixbuf = gtk.gdk.pixbuf_new_from_file(shutterImgFile)
		self.shutterImg = gtk.Image()
		self.shutterImg.set_from_pixbuf( shutterImgPixbuf )


	def loadColors( self ):
		profileColor = profile.get_color()
		self.colorFill = Color()
		self.colorFill.init_hex( profileColor.get_fill_color() )
		self.colorStroke = Color()
		self.colorStroke.init_hex( profileColor.get_stroke_color() )
		self.colorBlack = Color()
		self.colorBlack.init_rgba( 0, 0, 0, 255 )
		self.colorWhite = Color()
		self.colorWhite.init_rgba( 255, 255, 255, 255 )
		self.colorTray = Color()
		self.colorTray.init_rgba(  77, 77, 79, 255 )
		self.colorBg = Color()
		self.colorBg.init_rgba( 198, 199, 201, 255 )
		self.colorRed = Color()
		self.colorRed.init_rgba( 255, 0, 0, 255)


	def loadSvg( self, data, stroke, fill ):
		if ((stroke == None) or (fill == None)):
			return rsvg.Handle( data=data )

		entity = '<!ENTITY fill_color "%s">' % fill
		data = re.sub('<!ENTITY fill_color .*>', entity, data)

		entity = '<!ENTITY stroke_color "%s">' % stroke
		data = re.sub('<!ENTITY stroke_color .*>', entity, data)

		return rsvg.Handle( data=data )


class BackgroundCanvas(P5):
	def __init__(self, ui):
		P5.__init__(self)
		self.ui = ui

	def draw(self, ctx, w, h):
		self.background( ctx, self.ui.colorWhite, w, h )
		self.ui.modWaitSvg.render_cairo( ctx )


class PhotoCanvasWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.photoCanvas = None

	def setPhotoCanvas( self, photoCanvas ):
		self.photoCanvas = photoCanvas
		self.add(self.photoCanvas)


class PhotoCanvas(P5):
	def __init__(self, ui):
		P5.__init__(self)
		self.ui = ui
		self.img = None
		self.drawImg = None
		self.cacheWid = -1

	def draw(self, ctx, w, h):
		self.background( ctx, self.ui.colorBg, w, h )
		if (self.img != None):

			if (w == self.img.get_width()):
				self.cacheWid == w
				self.drawImg = self.img

			#todo: throw this into a gobject timeout
			#only scale images when you need to, otherwise you're wasting cycles, fool!
			if (self.cacheWid != w):
				self.drawImg = cairo.ImageSurface( cairo.FORMAT_ARGB32, w, h)
				dCtx = cairo.Context(self.drawImg)
				dScl = (w+0.0)/(self.ui.vw+0.0)
				dCtx.scale( dScl, dScl )
				dCtx.set_source_surface( self.img, 0, 0 )
				dCtx.paint()

			if (self.drawImg != None):
				#todo: center the image based on the image size, and w & h
				ctx.set_source_surface(self.drawImg, 0, 0)
				ctx.paint()

			self.cacheWid = w

	def setImage(self, img):
		self.cacheWid = -1
		self.img = img
		if (self.img == None):
			self.drawImg = None
		self.redraw()


class PipWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.pipButton = PipButton(self.ui)
		self.add( self.pipButton )


class MaxWindow(gtk.Window):
	def __init__(self, ui, play):
		gtk.Window.__init__(self)
		self.ui = ui
		self.maxButton = MaxButton(self.ui, play)
		self.add( self.maxButton )


#need two sizes for this guy -- max'd and min'd
class PipButton(P5Button):
	def __init__(self, ui):
		P5Button.__init__(self)
		self.ui = ui
		xs = []
		ys = []
		xs.append(0)
		ys.append(0)
		xs.append(self.ui.pipw)
		ys.append(0)
		xs.append(self.ui.pipw)
		ys.append(self.ui.piph)
		xs.append(0)
		ys.append(self.ui.piph)
		poly = Polygon( xs, ys )
		butt = Button( poly, 0, 0)
		butt.addActionListener( self )
		self.pipS = "pip"
		butt.setActionCommand( self.pipS )
		self._butts.append( butt )

	def draw(self, ctx, w, h):
		c = Color( )
		c.init_rgba( 0, 255, 0, 255 )
		self.background( ctx, c, w, h )

	def fireButton(self, actionCommand):
		if (actionCommand == self.pipS):
			print("pip!")


class MaxButton(P5Button):
	def __init__(self, ui, play):
		P5Button.__init__(self)
		self.ui = ui
		self.play = play
		xs = []
		ys = []
		xs.append(0)
		ys.append(0)
		xs.append(self.ui.maxw)
		ys.append(0)
		xs.append(self.ui.maxw)
		ys.append(self.ui.maxh)
		xs.append(0)
		ys.append(self.ui.maxh)
		poly = Polygon( xs, ys )
		butt = Button( poly, 0, 0)
		butt.addActionListener( self )
		self.maxS = "max"
		butt.setActionCommand( self.maxS )
		self._butts.append( butt )

	def draw(self, ctx, w, h):
		if (self.ui.fullScreen):
			self.ui.maxEnlargeSvg.render_cairo( ctx )
		else:
			self.ui.maxReduceSvg.render_cairo( ctx )

	def fireButton(self, actionCommand):
		if (actionCommand == self.maxS):
			self.ui.doFullscreen()


class ThumbnailCanvas(P5Button):
	def __init__(self, pui):
		P5Button.__init__(self)
		self.ui = pui

		ixs = []
		iys = []
		ixs.append(0)
		iys.append(0)
		ixs.append(self.ui.tw)
		iys.append(0)
		ixs.append(self.ui.tw)
		iys.append(self.ui.th)
		ixs.append(0)
		iys.append(self.ui.th)
		iPoly = Polygon( ixs, iys )

		self.imgButt = Button(iPoly, 0, 0)
		#imgButt.addActionListener( self )
		self.thumbS = "thumb"
		self.imgButt.setActionCommand( self.thumbS)
		self._butts.append( self.imgButt )

		self.deleteDim = 25
		dxs = []
		dys = []
		dxs.append(0)
		dys.append(0)
		dxs.append(self.deleteDim)
		dys.append(0)
		dxs.append(self.deleteDim)
		dys.append(self.deleteDim)
		dxs.append(0)
		dys.append(self.deleteDim)
		dPoly = Polygon(dxs, dys )
		self.delButt = Button(dPoly, 0, 0)
		#delButt.addActionListener( self )
		self.deleteS = "delete"
		self.delButt.setActionCommand(self.deleteS)
		self._butts.append( self.delButt )

		#init with a clear
		self.recd = None
		self.clear()
		self.cacheW = -1

	def clear(self):
		if (self.recd != None):
			self.recd.thumb = None
		self.recd = None
		self.delButt.removeActionListener(self)
		self.imgButt.removeActionListener(self)
		self.redraw()

	def setButton(self, recd):
		self.recd = recd
		self.loadThumb()
		self.delButt.addActionListener(self)
		self.imgButt.addActionListener(self)
		self.redraw()

	def loadThumb(self):
		thmbPath = os.path.join(self.ui.ca.journalPath, self.recd.thumbFilename)
		thmbPath_s = os.path.abspath(thmbPath)
		if ( os.path.isfile(thmbPath_s) ):
			pb = gtk.gdk.pixbuf_new_from_file(thmbPath_s)
			img = _camera.cairo_surface_from_gdk_pixbuf(pb)
			self.recd.thumb = img

	#todo: dImg this sucka
	#todo: make this into gtk buttons?
	def draw(self, ctx, w, h):
		self.background( ctx, self.ui.colorTray, w, h )
		if (self.recd == None):
			return

		xSvg = (w-self.ui.thumbSvgW)/2
		ySvg = (h-self.ui.thumbSvgH)/2

		if (self.recd.type == self.ui.ca.m.TYPE_PHOTO):
			ctx.translate( xSvg, ySvg )
			self.ui.thumbPhotoSvg.render_cairo(ctx)

			ctx.translate( 8, 8 )
			ctx.set_source_surface(self.recd.thumb, 0, 0)
			self.imgButt.setOffsets( ctx.user_to_device(0,0) )
			ctx.paint()

			ctx.translate( self.ui.tw-self.deleteDim, self.ui.th+4 )
			self.delButt.setOffsets( ctx.user_to_device(0,0) )
			self.ui.closeSvg.render_cairo(ctx)

		elif (self.recd.type == self.ui.ca.m.TYPE_VIDEO):
			ctx.translate( xSvg, ySvg )
			self.ui.thumbVideoSvg.render_cairo(ctx)

			ctx.translate( 8, 22 )
			ctx.set_source_surface(self.recd.thumb, 0, 0)
			self.imgButt.setOffsets( ctx.user_to_device(0,0) )
			ctx.paint()

			ctx.translate( self.ui.tw-self.deleteDim, self.ui.th+1 )
			self.delButt.setOffsets( ctx.user_to_device(0,0) )
			self.ui.closeSvg.render_cairo(ctx)

		self.cacheW = w

	def fireButton(self, actionCommand):
		if (actionCommand == self.thumbS):
			self.ui.showThumbSelection( self.recd )
		elif (actionCommand == self.deleteS):
			self.ui.deleteThumbSelection( self.recd )


class ModeToolbar(gtk.Toolbar):
	def __init__(self, pc):
		gtk.Toolbar.__init__(self)
		self.ca = pc

		picButt = RadioToolButton( "menubar_photo" )
		picButt.set_tooltip("Photo")
		picButt.props.sensitive = True
		picButt.connect('clicked', self.modePhotoCb)
		self.insert(picButt, -1)
		picButt.show()

		vidButt = RadioToolButton( "menubar_video" )
		vidButt.set_group( picButt )
		vidButt.set_tooltip("Video")
		vidButt.props.sensitive = True
		vidButt.connect('clicked', self.modeVideoCb)
		self.insert(vidButt, -1)
		vidButt.show()


	def modeVideoCb(self, button):
		self.ca.m.doVideoMode()

	def modePhotoCb(self, button):
		self.ca.m.doPhotoMode()


class SearchToolbar(gtk.Toolbar):
	def __init__(self, pc):
		gtk.Toolbar.__init__(self)
		self.ca = pc

#todo:
#multiple record