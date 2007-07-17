#!/usr/bin/env python

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
		self.pipBorder = 4
		self.pipBorderW = self.pipw + (self.pipBorder*2)
		self.pipBorderH = self.piph + (self.pipBorder*2)

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
		self.modeToolbar = ModeToolbar(self.ca)
		toolbox.add_toolbar( ('Mode'), self.modeToolbar )
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
		#todo: insensitive at launch?
		self.shutterButton.connect("clicked", self.shutterClickCb)
		shutterBox = gtk.EventBox()
		shutterBox.add( self.shutterButton )
		shutterBox.set_border_width( 50 )
		infoBox.pack_start(shutterBox, expand=True)

		#todo: dynamically query/set size
		spaceTaker = gtk.HBox()
		spaceTaker.set_size_request( -1, 25 )
		infoBox.pack_start(spaceTaker, expand=True)

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

		#pipbackground here
		self.livePipBgdWindow = PipWindow(self)
		self.livePipBgdWindow.set_transient_for(self.livePhotoWindow)
		self.livePipBgdWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.livePipBgdWindow.set_decorated(False)

		self.liveVideoWindow = LiveVideoWindow()
		self.liveVideoWindow.set_transient_for(self.livePipBgdWindow)
		self.liveVideoWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.liveVideoWindow.set_decorated(False)
		self.liveVideoWindow.set_glive(self.ca.glive)
		self.liveVideoWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.liveVideoWindow.connect("button_release_event", self.liveButtonReleaseCb)

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

		#pipbackground here
		self.playLivePipBgdWindow = PipWindow(self)
		self.playLivePipBgdWindow.modify_bg( gtk.STATE_NORMAL, self.colorWhite.gColor )
		self.playLivePipBgdWindow.set_transient_for(self.playOggWindow)
		self.playLivePipBgdWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playLivePipBgdWindow.set_decorated(False)

		self.playLiveWindow = LiveVideoWindow()
		self.playLiveWindow.set_transient_for(self.playLivePipBgdWindow)
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
		self.livePipBgdWindow.show_all()
		self.liveVideoWindow.show_all()
		self.mapId = self.liveVideoWindow.connect("map-event", self.mapEvent)
		self.liveMaxWindow.show_all()

		self.playOggWindow.show_all()
		self.playLivePipBgdWindow.show_all()
		self.playLiveWindow.show_all()
		self.playMaxWindow.show_all()


	def showLiveVideoTags( self ):
		self.nameTextfield.set_label("Live Video")
		self.photographerNameLabel.set_label( str(self.ca.nickName) )
		self.dateDateLabel.set_label( "Today" )


	def updateShutterButton( self ):
		self.shutterButton.set_sensitive( not self.ca.m.UPDATING )
		self.modeToolbar.picButt.set_sensitive( not self.ca.m.UPDATING )
		self.modeToolbar.vidButt.set_sensitive( not self.ca.m.UPDATING )

		if (self.ca.m.UPDATING):
			self.ca.ui.setWaitCursor()
		else:
			self.ca.ui.setDefaultCursor( )

		if (self.ca.m.RECORDING):
			self.shutterButton.modify_bg( gtk.STATE_NORMAL, self.colorRed.gColor )
		else:
			self.shutterButton.modify_bg( gtk.STATE_NORMAL, None )


	def hideLiveWindows( self ):
		offW = gtk.gdk.screen_width() + 100
		offH = gtk.gdk.screen_height() + 100
		print( "live", offW, offH )

		self.livePhotoWindow.move( offW, offH )
		self.livePipBgdWindow.move( offW, offH )
		self.liveVideoWindow.move( offW, offH )
		self.liveMaxWindow.move( offW, offH )


	def hidePlayWindows( self ):
		offW = gtk.gdk.screen_width() + 100
		offH = gtk.gdk.screen_height() + 100
		print( "play", offW, offH )

		self.playOggWindow.move( offW, offH )
		self.playLivePipBgdWindow.move( offW, offH )
		self.playLiveWindow.move( offW, offH )
		self.playMaxWindow.move( offW, offH )


	def liveButtonReleaseCb(self, widget, event):
		self.livePhotoCanvas.setImage(None)
		if (self.liveMode != True):
			self.liveMode = True
			self.showLiveVideoTags()
			self.updateVideoComponents()


	def playLiveButtonReleaseCb(self, widget, event):
		#if you are big on the screen, don't go changing anything, ok?
		if (self.liveMode):
			return

		self.showLiveVideoTags()

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


	def updateModeChange(self):
		#this is called when a menubar button is clicked
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
			win.move( vPos[0]+self.inset, (vPos[1]+self.vh)-(self.inset+self.piph) )

		win.show_all()


	def setPipBgdLocDim( self, win ):
		win.resize( self.pipBorderW, self.pipBorderH )
		if (self.fullScreen):
			win.move( self.inset-self.pipBorder, gtk.gdk.screen_height()-(self.inset+self.piph+self.pipBorder))
		else:
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			win.move( vPos[0]+(self.inset-self.pipBorder), (vPos[1]+self.vh)-(self.inset+self.piph+self.pipBorder) )

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


	def mapEvent( self, widget, event ):
		#when your parent window is ready, turn on the feed of live video
		self.liveVideoWindow.disconnect(self.mapId)
		self.mapped = True
		self.checkReadyToSetup()


	def exposeEvent( self, widget, event):
		#initial setup of the panels
		self.ca.disconnect(self.exposeId)
		self.exposed = True
		self.checkReadyToSetup( )


	def updateVideoComponents( self ):
		offW = gtk.gdk.screen_width() + 100
		offH = gtk.gdk.screen_height() + 100

		if (self.photoMode):
			if (self.liveMode):
				self.playLivePipBgdWindow.move( offW, offH )

				self.setImgLocDim( self.livePhotoWindow )
				self.setImgLocDim( self.liveVideoWindow )
				self.setMaxLocDim( self.liveMaxWindow )
			else:
				self.setImgLocDim( self.livePhotoWindow )
				self.setPipBgdLocDim( self.livePipBgdWindow )
				self.setPipLocDim( self.liveVideoWindow )
				self.setMaxLocDim( self.liveMaxWindow )
		else:
			if (self.liveMode):
				self.playOggWindow.move( offW, offH )
				self.playLivePipBgdWindow.move( offW, offH )

				self.setImgLocDim( self.playLiveWindow )
				self.setMaxLocDim( self.playMaxWindow )
			else:
				self.setImgLocDim( self.playOggWindow )
				self.setMaxLocDim( self.playMaxWindow )
				self.setPipBgdLocDim( self.playLivePipBgdWindow )
				self.setPipLocDim( self.playLiveWindow )


	#todo: cache buttons which we can reuse
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


	def showThumbSelection( self, recd ):
		#do we need to know the type, since we're showing based on the mode of the app?
		if (recd.type == self.ca.m.TYPE_PHOTO):
			self.showPhoto( recd )
		if (recd.type == self.ca.m.TYPE_VIDEO):
			self.showVideo( recd )


	def deleteThumbSelection( self, recd ):
		#todo: test --> if this is the current selection, then clear it away here
		#todo: for video too
		self.ca.m.deleteMedia( recd, self.startThumb )

		self.shownRecd = None
		self.livePhotoCanvas.setImage(None)
		self.liveMode = True
		self.updateVideoComponents()

		self.showLiveVideoTags()


	def showPhoto( self, recd ):
		#todo: show networked photos and request their bits
		self.shownRecd = recd

		imgPath = os.path.join(self.ca.journalPath, recd.mediaFilename)
		imgPath_s = os.path.abspath(imgPath)

		if (self.shownRecd.buddy):
			imgPath = os.path.join(self.ca.journalPath, "buddy", recd.mediaFilename)
			imgPath_s = os.path.abspath(imgPath)
			if (not os.path.isfile(imgPath_s)):
				imgPath = os.path.join(self.ca.journalPath, "buddy", recd.thumbFilename)
				#todo: make req for the real picture here
				#todo: make sure to get the correct url, pbly by asking...

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

		maxEnlargeSvgFile = open(os.path.join(self.ca.gfxPath, 'max-enlarge.svg'), 'r')
		maxEnlargeSvgData = maxEnlargeSvgFile.read()
		self.maxEnlargeSvg = self.loadSvg(maxEnlargeSvgData, None, None )
		maxEnlargeSvgFile.close()

		maxReduceSvgPath = os.path.join(self.ca.gfxPath, 'max-reduce.svg')
		maxReduceSvgFile = open(maxReduceSvgPath, 'r')
		maxReduceSvgData = maxReduceSvgFile.read()
		self.maxReduceSvg = self.loadSvg(maxReduceSvgData, None, None )
		maxReduceSvgFile.close()

		shutterImgFile = os.path.join(self.ca.gfxPath, 'shutter_button.png')
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
		self.scalingImageCb = 0
		self.cacheWid = -1

	def draw(self, ctx, w, h):
		self.background( ctx, self.ui.colorBg, w, h )
		if (self.img != None):

			if (w == self.img.get_width()):
				self.cacheWid == w
				self.drawImg = self.img

			#only scale images when you need to, otherwise you're wasting cycles, fool!
			if (self.cacheWid != w):
				if (self.scalingImageCb == 0):
					self.scalingImageCb = gobject.idle_add( self.resizeImage, w, h )

			if (self.drawImg != None):
				#center the image based on the image size, and w & h
				ctx.set_source_surface(self.drawImg, (w/2)-(self.drawImg.get_width()/2), (h/2)-(self.drawImg.get_height()/2))
				ctx.paint()

			self.cacheWid = w


	def setImage(self, img):
		self.cacheWid = -1
		self.img = img
		if (self.img == None):
			self.drawImg = None
		self.queue_draw()


	def resizeImage(self, w, h):
		#use image size in case 640 no more
		scaleImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
		sCtx = cairo.Context(scaleImg)
		#todo: test --> self.ui.vw not necc b/c of thumbs when over the network
		sScl = (w+0.0)/(self.img.get_width()+0.0)
		sCtx.scale( sScl, sScl )
		sCtx.set_source_surface( self.img, 0, 0 )
		sCtx.paint()
		self.drawImg = scaleImg
		self.cacheWid = w
		self.queue_draw()
		self.scalingImageCb = 0


class PipWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.pipCanvas = PipCanvas(self.ui)
		self.add( self.pipCanvas )


class PipCanvas(P5):
	def __init__(self, ui):
		P5.__init__(self)
		self.ui = ui

	def draw(self, ctx, w, h):
		self.background( ctx, self.ui.colorWhite, w, h )


class MaxWindow(gtk.Window):
	def __init__(self, ui, play):
		gtk.Window.__init__(self)
		self.ui = ui
		self.maxButton = MaxButton(self.ui, play)
		self.add( self.maxButton )

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
			if (not self.recd.buddy):
				self.delButt.removeActionListener(self)

		self.imgButt.removeActionListener(self)
		self.recd = None

		self.recdThumbRenderImg = None
		self.redraw()

	def setButton(self, recd):
		self.recd = recd
		self.loadThumb()
		if (not self.recd.buddy):
			self.delButt.addActionListener(self)
		self.imgButt.addActionListener(self)
		self.redraw()

	def loadThumb(self):
		thmbPath = os.path.join(self.ui.ca.journalPath, self.recd.thumbFilename)
		if (self.recd.buddy):
			thmbPath = os.path.join(self.ui.ca.journalPath, "buddies", self.recd.thumbFilename)

		thmbPath_s = os.path.abspath(thmbPath)
		if ( os.path.isfile(thmbPath_s) ):
			pb = gtk.gdk.pixbuf_new_from_file(thmbPath_s)
			img = _camera.cairo_surface_from_gdk_pixbuf(pb)
			self.recd.thumb = img


	def draw(self, ctx, w, h):
		#todo: make this into gtk buttons?  will require segmenting the thumbnail gfx or use windows & more usablity
		self.background( ctx, self.ui.colorTray, w, h )
		if (self.recd == None):
			return

		if (self.recdThumbRenderImg == None):
			self.recdThumbRenderImg = cairo.ImageSurface( cairo.FORMAT_ARGB32, w, h)
			rtCtx = cairo.Context(self.recdThumbRenderImg)
			xSvg = (w-self.ui.thumbSvgW)/2
			ySvg = (h-self.ui.thumbSvgH)/2

			if (self.recd.type == self.ui.ca.m.TYPE_PHOTO):
				rtCtx.translate( xSvg, ySvg )
				if (self.recd.buddy):
					thumbPhotoSvg = self.ui.loadSvg(self.ui.thumbPhotoSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
					thumbPhotoSvg.render_cairo(rtCtx)
				else:
					self.ui.thumbPhotoSvg.render_cairo(rtCtx)

				rtCtx.translate( 8, 8 )
				rtCtx.set_source_surface(self.recd.thumb, 0, 0)
				self.imgButt.setOffsets( rtCtx.user_to_device(0,0) )
				rtCtx.paint()

				if (not self.recd.buddy):
					rtCtx.translate( self.ui.tw-self.deleteDim, self.ui.th+4 )
					self.delButt.setOffsets( rtCtx.user_to_device(0,0) )
					self.ui.closeSvg.render_cairo(rtCtx)

			elif (self.recd.type == self.ui.ca.m.TYPE_VIDEO):
				rtCtx.translate( xSvg, ySvg )
				if (self.recd.buddy):
					thumbVideoSvg = self.ui,loadSvg(self.ui.thumbVideoSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
					thumbVideoSvg.render_cairo(rtCtx)
				else:
					self.ui.thumbVideoSvg.render_cairo(rtCtx)

				rtCtx.translate( 8, 22 )
				rtCtx.set_source_surface(self.recd.thumb, 0, 0)
				self.imgButt.setOffsets( rtCtx.user_to_device(0,0) )
				rtCtx.paint()

				if (not self.recd.buddy):
					rtCtx.translate( self.ui.tw-self.deleteDim, self.ui.th+1 )
					self.delButt.setOffsets( rtCtx.user_to_device(0,0) )
					self.ui.closeSvg.render_cairo( rtCtx )

		ctx.set_source_surface(self.recdThumbRenderImg, 0, 0)
		ctx.paint()


	def fireButton(self, actionCommand):
		if (actionCommand == self.thumbS):
			self.ui.showThumbSelection( self.recd )
		elif (actionCommand == self.deleteS):
			self.ui.deleteThumbSelection( self.recd )


class ModeToolbar(gtk.Toolbar):
	def __init__(self, pc):
		gtk.Toolbar.__init__(self)
		self.ca = pc

		self.picButt = RadioToolButton( "menubar_photo" )
		self.picButt.set_tooltip("Photo")
		self.picButt.props.sensitive = True
		self.picButt.connect('clicked', self.modePhotoCb)
		self.insert(self.picButt, -1)
		self.picButt.show()

		self.vidButt = RadioToolButton( "menubar_video" )
		self.vidButt.set_group( self.picButt )
		self.vidButt.set_tooltip("Video")
		self.vidButt.props.sensitive = True
		self.vidButt.connect('clicked', self.modeVideoCb)
		self.insert(self.vidButt, -1)
		self.vidButt.show()


	def modeVideoCb(self, button):
		self.ca.m.doVideoMode()

	def modePhotoCb(self, button):
		self.ca.m.doPhotoMode()


class SearchToolbar(gtk.Toolbar):
	def __init__(self, pc):
		gtk.Toolbar.__init__(self)
		self.ca = pc