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

import gtk
from gtk import gdk
from gtk import keysyms
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
import shutil

import pygst
pygst.require('0.10')
import gst
import gst.interfaces

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
		self.fullScreen = False
		self.liveMode = True

		self.LAST_MODE = -1
		self.LAST_FULLSCREEN = False
		self.LAST_LIVE = True
		self.LAST_RECD_INFO = False
		self.HIDE_ON_UPDATE = True
		self.RECD_INFO_ON = False

		#thumb dimensions:
		self.thumbTrayHt = 150
		self.tw = 107
		self.th = 80
		self.thumbSvgW = 124
		self.thumbSvgH = 124
		#pip size:
		self.pipw = 160
		self.piph = 120
		self.pipBorder = 4
		self.pgdw = self.pipw + (self.pipBorder*2)
		self.pgdh = self.piph + (self.pipBorder*2)
		#maximize size:
		self.maxw = 49
		self.maxh = 49
		#component spacing
		self.inset = 10
		#video size:
		#todo: dynamically set this...
		#(03:19:45 PM) eben: jedierikb: bar itself is 75px, tabs take an additional 45px (including gray spacer)
		#(03:23:16 PM) tomeu: jedierikb: you create the toolbar, you can ask him it's height after it has been allocated
		self.vh = gtk.gdk.screen_height()-(self.thumbTrayHt+75+45+5)
		self.vw = int(self.vh/.75)

		letterBoxW = (gtk.gdk.screen_width() - self.vw)/2
		self.letterBoxVW = (self.vw/2)-(self.inset*2)
		self.letterBoxVH = int(self.letterBoxVW*.75)

		#number of thumbs
		self.numThumbs = 7

		#prep for when to show
		self.allocated = False
		self.mapped = False

		self.shownRecd = None

		#this includes the default sharing tab
		toolbox = activity.ActivityToolbox(self.ca)
		self.ca.set_toolbox(toolbox)
		self.modeToolbar = ModeToolbar(self.ca)
		#todo: internationalize this
		toolbox.add_toolbar( ('Record'), self.modeToolbar )
		toolbox.show()

		self.mainBox = gtk.VBox()
		self.ca.set_canvas(self.mainBox)

		topBox = gtk.HBox()
		self.mainBox.pack_start(topBox, expand=True)

		leftFill = gtk.VBox()
		leftFill.set_size_request( letterBoxW, -1 )
		topBox.pack_start( leftFill, expand=True )

		self.centerBox = gtk.EventBox()
		topBox.pack_start( self.centerBox, expand=False )
		#filled with this guy for sizings..
		centerSizer = gtk.VBox()
		centerSizer.set_size_request(self.vw, -1)
		self.centerBox.add(centerSizer)

		#into the center box we can put this guy...
		self.backgdCanvasBox = gtk.VBox()
		self.backgdCanvasBox.set_size_request(self.vw, -1)
		self.backgdCanvas = BackgroundCanvas(self)
		self.backgdCanvas.set_size_request(self.vw, self.vh)
		self.backgdCanvasBox.pack_start( self.backgdCanvas, expand=False )

		#or this guy...
		self.infoBox = gtk.EventBox()
		self.infoBox.modify_bg( gtk.STATE_NORMAL, self.colorGreen.gColor )
		iinfoBox = gtk.VBox(spacing=self.inset)
		self.infoBox.add( iinfoBox )
		iinfoBox.set_size_request(self.vw, -1)
		iinfoBox.set_border_width(self.inset)

		rightFill = gtk.VBox()
		rightFill.set_size_request( letterBoxW, -1 )
		topBox.pack_start( rightFill, expand=True )

		rightFillTop = gtk.HBox()
		rightFill.pack_start( rightFillTop, expand=True )

		#info box innards:
		self.infoBoxTop = gtk.HBox()
		iinfoBox.pack_start( self.infoBoxTop, expand=True )
		self.infoBoxTopLeft = gtk.VBox(spacing=self.inset)
		self.infoBoxTop.pack_start( self.infoBoxTopLeft )
		self.infoBoxTopRight = gtk.VBox()
		self.infoBoxTopRight.set_size_request(self.letterBoxVW, -1)
		self.infoBoxTop.pack_start( self.infoBoxTopRight )

		self.namePanel = gtk.VBox(spacing=self.inset)
		self.infoBoxTopLeft.pack_start(self.namePanel, expand=False)
		nameLabel = gtk.Label("Title:")
		self.namePanel.pack_start( nameLabel, expand=False )
		nameLabel.set_alignment(0, .5)
		self.nameTextfield = gtk.Entry(80)
		self.nameTextfield.connect('changed', self._nameTextfieldEditedCb )
		self.nameTextfield.set_alignment(0)
		self.namePanel.pack_start(self.nameTextfield)

		self.photographerPanel = gtk.VBox(spacing=self.inset)
		self.infoBoxTopLeft.pack_start(self.photographerPanel, expand=False)
		photographerLabel = gtk.Label("Recorder:")
		self.photographerPanel.pack_start(photographerLabel, expand=False)
		photographerLabel.set_alignment(0, .5)
		photoNamePanel = gtk.HBox(spacing=self.inset)
		self.photographerPanel.pack_start(photoNamePanel)

		self.photoXoPanel = xoPanel(self)
		photoNamePanel.pack_start( self.photoXoPanel, expand=False )
		self.photoXoPanel.set_size_request( 40, 40 )

		self.photographerNameLabel = gtk.Label("")
		self.photographerNameLabel.set_alignment(0, .5)
		photoNamePanel.pack_start(self.photographerNameLabel)

		self.datePanel = gtk.HBox(spacing=self.inset)
		self.infoBoxTopLeft.pack_start(self.datePanel, expand=False)
		dateLabel = gtk.Label("Date:")
		self.datePanel.pack_start(dateLabel, expand=False)
		self.dateDateLabel = gtk.Label("")
		self.dateDateLabel.set_alignment(0, .5)
		self.datePanel.pack_start(self.dateDateLabel)

		self.tagsPanel = gtk.VBox(spacing=self.inset)
		tagsLabel = gtk.Label("Tags:")
		tagsLabel.set_alignment(0, .5)
		self.tagsPanel.pack_start(tagsLabel, expand=False)
		self.tagsBuffer = gtk.TextBuffer()
		self.tagsField = gtk.TextView( self.tagsBuffer )
		self.tagsPanel.pack_start( self.tagsField, expand=True )
		self.infoBoxTopLeft.pack_start(self.tagsPanel, expand=True)

		infoBotBox = gtk.HBox()
		infoBotBox.set_size_request( -1, self.pgdh+self.inset )
		iinfoBox.pack_start(infoBotBox, expand=False)

		thumbnailsEventBox = gtk.EventBox()
		thumbnailsEventBox.modify_bg( gtk.STATE_NORMAL, self.colorTray.gColor )
		thumbnailsEventBox.set_size_request( -1, self.thumbTrayHt )
		thumbnailsBox = gtk.HBox( )
		thumbnailsEventBox.add( thumbnailsBox )
		self.mainBox.pack_end(thumbnailsEventBox, expand=False)

		self.leftThumbButton = gtk.Button()
		self.leftThumbButton.connect( "clicked", self._leftThumbButtonCb )
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
			self.thumbButts.append( thumbButt )
		self.rightThumbButton = gtk.Button()
		self.rightThumbButton.connect( "clicked", self._rightThumbButtonCb )
		self.setupThumbButton( self.rightThumbButton, "right-thumb-sensitive" )
		rightThumbEventBox = gtk.EventBox()
		rightThumbEventBox.set_border_width(self.inset)
		rightThumbEventBox.modify_bg( gtk.STATE_NORMAL, self.colorTray.gColor )
		rightThumbEventBox.add( self.rightThumbButton )
		thumbnailsBox.pack_start( rightThumbEventBox, expand=False )

		#image windows
		self.windowStack = []

		#live video windows
		self.livePhotoWindow = PhotoCanvasWindow(self)
		self.addToWindowStack( self.livePhotoWindow, self.vw, self.vh, self.ca )
		self.livePhotoCanvas = PhotoCanvas(self)
		self.livePhotoWindow.setPhotoCanvas(self.livePhotoCanvas)
		self.livePhotoWindow.connect("button_release_event", self._mediaClickedForPlayback)

		#border behind
		self.pipBgdWindow = PipWindow(self)
		self.addToWindowStack( self.pipBgdWindow, self.pgdw, self.pgdh, self.windowStack[len(self.windowStack)-1] )

		self.liveVideoWindow = LiveVideoWindow()
		self.addToWindowStack( self.liveVideoWindow, self.vw, self.vh, self.windowStack[len(self.windowStack)-1] )
		self.liveVideoWindow.set_glive(self.ca.glive)
		self.liveVideoWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.liveVideoWindow.connect("button_release_event", self._liveButtonReleaseCb)

		#video playback windows
		self.playOggWindow = PlayVideoWindow()
		self.addToWindowStack( self.playOggWindow, self.vw, self.vh, self.windowStack[len(self.windowStack)-1] )
		self.playOggWindow.set_gplay(self.ca.gplay)
		self.playOggWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.playOggWindow.connect("button_release_event", self._mediaClickedForPlayback)

		#border behind
		self.pipBgdWindow2 = PipWindow(self)
		self.addToWindowStack( self.pipBgdWindow2, self.pgdw, self.pgdh, self.windowStack[len(self.windowStack)-1] )

		self.playLiveWindow = LiveVideoWindow()
		self.addToWindowStack( self.playLiveWindow, self.pipw, self.piph, self.windowStack[len(self.windowStack)-1] )
		self.playLiveWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.playLiveWindow.connect("button_release_event", self._playLiveButtonReleaseCb)

		self.recordWindow = RecordWindow(self)
		self.addToWindowStack( self.recordWindow, self.pgdw, self.pgdh, self.windowStack[len(self.windowStack)-1] )

		self.maxWindow = MaxWindow(self)
		self.addToWindowStack( self.maxWindow, self.maxw, self.maxh, self.windowStack[len(self.windowStack)-1] )

		self.infWindow = InfWindow(self)
		self.addToWindowStack( self.infWindow, self.maxw, self.maxh, self.windowStack[len(self.windowStack)-1] )

		self.hideLiveWindows()
		self.hidePlayWindows()
		self.hideAudioWindows()

		#only show the floating windows once everything is exposed and has a layout position
		self.SIZE_ALLOCATE_ID = self.centerBox.connect_after("size-allocate", self._sizeAllocateCb)
		self.ca.show_all()

		self.MAP_EVENT_ID = self.liveVideoWindow.connect("map-event", self._mapEventCb)
		for i in range (0, len(self.windowStack)):
			self.windowStack[i].show_all()

		#listen for ctrl+c & game key buttons
		self.ca.connect('key-press-event', self._keyPressEventCb)
		#overlay widgets can go away after they've been on screen for a while
		self.HIDE_WIDGET_TIMEOUT_ID = 0
		self.hiddenWidgets = False
		self.resetWidgetFadeTimer()

		self.showLiveVideoTags()


	def addToWindowStack( self, win, w, h, parent ):
		self.windowStack.append( win )
		win.resize( w, h )
		win.set_transient_for( parent )
		win.set_type_hint( gtk.gdk.WINDOW_TYPE_HINT_DIALOG )
		win.set_decorated( False )
		win.set_focus_on_map( False )
		win.set_property("accept-focus", False)


	def resetWidgetFadeTimer( self ):
		#only show the clutter when the mouse moves
		self.mx = -1
		self.my = -1
		self.hideWidgetsTimer = 0
		if (self.hiddenWidgets):
			self.showWidgets()
			self.hiddenWidgets = False

		#remove, then add
		self.doMouseListener( False )
		self.HIDE_WIDGET_TIMEOUT_ID = gobject.timeout_add( 500, self._mouseMightaMovedCb )


	def doMouseListener( self, listen ):
		if (listen):
			self.resetWidgetFadeTimer()
		else:
			if (self.HIDE_WIDGET_TIMEOUT_ID != None):
				if (self.HIDE_WIDGET_TIMEOUT_ID != 0):
					gobject.source_remove( self.HIDE_WIDGET_TIMEOUT_ID )


	def hideWidgets( self ):
		self.moveWinOffscreen( self.recordWindow )
		self.moveWinOffscreen( self.maxWindow )
		self.moveWinOffscreen( self.pipBgdWindow )
		self.moveWinOffscreen( self.pipBgdWindow2 )
		self.moveWinOffscreen( self.infWindow )
		if (self.ca.m.MODE == self.ca.m.MODE_PHOTO):
			if (not self.liveMode):
				self.moveWinOffscreen( self.liveVideoWindow )
		elif (self.ca.m.MODE == self.ca.m.MODE_VIDEO):
			if (not self.liveMode):
				self.moveWinOffscreen( self.playLiveWindow )
		elif (self.ca.m.MODE == self.ca.m.MODE_AUDIO):
			if (not self.liveMode):
				self.moveWinOffscreen( self.liveVideoWindow )
		self.LAST_MODE = -1


	def _mouseMightaMovedCb( self ):
		x, y = self.ca.get_pointer()
		if (x != self.mx or y != self.my):
			self.hideWidgetsTimer = 0
			if (self.hiddenWidgets):
				self.showWidgets()
				self.hiddenWidgets = False
		else:
			#todo: use time here?
			self.hideWidgetsTimer = self.hideWidgetsTimer + 500

		if (self.ca.m.RECORDING):
			self.hideWidgetsTimer = 0

		if (self.hideWidgetsTimer > 2000):
			if (not self.hiddenWidgets):
				if (self.mouseInWidget(x,y)):
					self.hideWidgetsTimer = 0
				elif (self.RECD_INFO_ON):
					self.hideWidgetsTimer = 0
				else:
					self.hideWidgets()
					self.hiddenWidgets = True

		self.mx = x
		self.my = y
		return True


	def mouseInWidget( self, mx, my ):
		#todo: audio does not have fullscreen
		if (self.inWidget( mx, my, self.getLoc("max", self.fullScreen), self.getDim("max"))):
			return True
		if (self.inWidget( mx, my, self.getLoc("pgd", self.fullScreen), self.getDim("pgd"))):
			return True
		if (self.inWidget( mx, my, self.getLoc("eye", self.fullScreen), self.getDim("eye"))):
			return True
		if (self.inWidget( mx, my, self.getLoc("inb", self.fullScreen), self.getDim("inb"))):
			return True

		return False


	def _mediaClickedForPlayback(self, widget, event):
		if (not self.liveMode):
			if (self.shownRecd != None):
				if (self.ca.m.MODE != self.ca.m.MODE_PHOTO):
					self.showThumbSelection( self.shownRecd )


	def inWidget( self, mx, my, loc, dim ):
		if (	(mx > loc[0]) and (my > loc[1])	):
			if (	(mx < loc[0]+dim[0]) and (my < loc[1]+dim[1])	):
				return True


	def _nameTextfieldEditedCb(self, widget):
		if (self.shownRecd != None):
			if (self.nameTextfield.get_text() != self.shownRecd.title):
				self.shownRecd.setTitle( self.nameTextfield.get_text() )


	def _playPauseButtonCb(self, widget):
		if (self.ca.gplay.is_playing()):
			self.ca.gplay.pause()
		else:
			self.ca.gplay.play()

		self.updatePlayPauseButton()


	def updatePlayPauseButton(self):
		if (self.ca.gplay.is_playing()):
			self.playPauseButton.set_icon_widget(self.play_image)
		else:
			self.playPauseButton.set_icon_widget(self.pause_image)


	def _scrubberPressCb(self, widget, event):
		self.toolbar.button.set_sensitive(False)
		self.was_playing = self.player.is_playing()
		if self.was_playing:
			self.player.pause()

		# don't timeout-update position during seek
		if self.update_id != -1:
			gobject.source_remove(self.update_id)
			self.update_id = -1
		# make sure we get changed notifies
			if self.changed_id == -1:
				self.changed_id = self.toolbar.hscale.connect('value-changed', self.scale_value_changed_cb)


	def _scrubberReleaseCb(self, scale):
		#todo: where are these values from?
		real = long(scale.get_value() * self.p_duration / 100) # in ns
		self.ca.gplay.seek( real )
		# allow for a preroll
		self.ca.gplay.get_state(timeout=50 * gst.MSECOND) # 50 ms


	def scale_button_release_cb(self, widget, event):
		# see seek.cstop_seek
		widget.disconnect(self.changed_id)
		self.changed_id = -1

		self.toolbar.button.set_sensitive(True)
		if self.seek_timeout_id != -1:
			gobject.source_remove(self.seek_timeout_id)
			self.seek_timeout_id = -1
		else:
			if self.was_playing:
				self.player.play()
			if self.update_id != -1:
				self.error('Had a previous update timeout id')
			else:
				self.update_id = gobject.timeout_add(self.UPDATE_INTERVAL, self.update_scale_cb)


	def _keyPressEventCb( self, widget, event):
		self.resetWidgetFadeTimer()

		#we listen here for CTRL+C events and game keys, and pass on events to gtk.Entry fields
		keyname = gtk.gdk.keyval_name(event.keyval)

		#xev...
		print( "keyname:", keyname )

		#check: KP_End
		if (keyname == 'KP_Page_Up'):
			print("gamekey O")
		elif (keyname == 'KP_Page_Down'):
			print("gamekey X")
		elif (keyname == 'KP_End'):
			print("gamekey CHECK")
		elif (keyname == 'KP_Home'):
			print("gamekey SQUARE")

		if (keyname == 'c' and event.state == gtk.gdk.CONTROL_MASK):
			if (self.shownRecd != None):
				if (self.shownRecd.isClipboardCopyable( )):
					tempImgPath = self.doClipboardCopyStart( self.shownRecd )
					gtk.Clipboard().set_with_data( [('text/uri-list', 0, 0)], self._clipboardGetFuncCb, self._clipboardClearFuncCb, tempImgPath )
					return True

		return False


	def doClipboardCopyStart( self, recd ):
		imgPath_s = recd.getMediaFilepath(False)
		if (imgPath_s == None):
			#todo: make sure this is handled correctly
			return None

		tempImgPath = os.path.join( self.ca.tempPath, recd.mediaFilename)
		tempImgPath = self.ca.m.getUniqueFilepath(tempImgPath,0)
		print( imgPath_s, " -- ", tempImgPath )
		shutil.copyfile( imgPath_s, tempImgPath )
		return tempImgPath


	def doClipboardCopyCopy( self, tempImgPath, selection_data ):
		tempImgUri = "file://" + tempImgPath
		selection_data.set( "text/uri-list", 8, tempImgUri )


	def doClipboardCopyFinish( self, tempImgPath ):
		if (tempImgPath != None):
			if (os.path.exists(tempImgPath)):
				os.remove( tempImgPath )
		tempImgPath = None


	def _clipboardGetFuncCb( self, clipboard, selection_data, info, data):
		self.doClipboardCopyCopy( data, selection_data )


	def _clipboardClearFuncCb( self, clipboard, data):
		self.doClipboardCopyFinish( data )


	def showPhoto( self, recd ):
		pixbuf = self.getPhotoPixbuf( recd )
		if (pixbuf != None):
			self.shownRecd = recd

			img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)
			self.livePhotoCanvas.setImage( img )

			self.liveMode = False
			self.updateVideoComponents()

			self.showRecdMeta(recd)


	def getPhotoPixbuf( self, recd ):
		pixbuf = None
		imgPath = recd.getMediaFilepath( True )
		print( "getting photoPixbuf: ", imgPath )
		if (not imgPath == None):
			if ( os.path.isfile(imgPath) ):
				pixbuf = gtk.gdk.pixbuf_new_from_file(imgPath)

		if (pixbuf == None):
			#maybe it is not downloaded from the mesh yet...
			print("showing thumb from pixbuf 1")
			pixbuf = recd.getThumbPixbuf()
			print("showing thumb from pixbuf 2")

		return pixbuf


	def showLiveVideoTags( self ):
		self.shownRecd = None

		#todo: if this is too long, then live video gets pushed off screen (and ends up at 0x0??!)
		#make this uneditable here
		self.nameTextfield.set_text("Live Video")
		self.nameTextfield.set_sensitive( False )
		self.photographerNameLabel.set_label( str(self.ca.nickName) )
		self.dateDateLabel.set_label("Today")

		#todo: figure this out without the ui collapsing around it
		self.namePanel.hide()
		self.photographerPanel.hide()
		self.datePanel.hide()
		self.tagsPanel.hide()
		self.tagsBuffer.set_text("")

		self.livePhotoCanvas.setImage( None )
		self.resetWidgetFadeTimer()


	def updateButtonSensitivities( self ):

		#todo: make the gtk.entry uneditable
		#todo: change this button which is now in a window
		self.recordWindow.shutterButton.set_sensitive( not self.ca.m.UPDATING )

		switchStuff = ((not self.ca.m.UPDATING) and (not self.ca.m.RECORDING))

		self.modeToolbar.picButt.set_sensitive( switchStuff )
		self.modeToolbar.vidButt.set_sensitive( switchStuff )
		self.modeToolbar.audButt.set_sensitive( switchStuff )

		for i in range (0, len(self.thumbButts)):
			self.thumbButts[i].set_sensitive( switchStuff )

		if (self.ca.m.UPDATING):
			self.ca.ui.setWaitCursor()
		else:
			self.ca.ui.setDefaultCursor( )

		if (self.ca.m.RECORDING):
			self.recordWindow.shutterButton.modify_bg( gtk.STATE_NORMAL, self.colorRed.gColor )
		else:
			self.recordWindow.shutterButton.modify_bg( gtk.STATE_NORMAL, None )


	def hideLiveWindows( self ):
		self.moveWinOffscreen( self.livePhotoWindow )
		self.moveWinOffscreen( self.pipBgdWindow )
		self.moveWinOffscreen( self.liveVideoWindow )
		self.moveWinOffscreen( self.maxWindow )
		self.moveWinOffscreen( self.recordWindow )
		self.moveWinOffscreen( self.infWindow )


	def hidePlayWindows( self ):
		self.moveWinOffscreen( self.playOggWindow )
		self.moveWinOffscreen( self.pipBgdWindow2 )
		self.moveWinOffscreen( self.playLiveWindow )
		self.moveWinOffscreen( self.maxWindow )
		self.moveWinOffscreen( self.recordWindow )
		self.moveWinOffscreen( self.infWindow )

	def hideAudioWindows( self ):
		self.moveWinOffscreen( self.livePhotoWindow )
		self.moveWinOffscreen( self.liveVideoWindow )
		self.moveWinOffscreen( self.recordWindow )
		self.moveWinOffscreen( self.pipBgdWindow )
		self.moveWinOffscreen( self.infWindow )

	def _liveButtonReleaseCb(self, widget, event):
		self.livePhotoCanvas.setImage( None )

		self.RECD_INFO_ON = False

		if (self.liveMode != True):
			#todo: updating here?
			self.ca.gplay.stop()
			self.showLiveVideoTags()
			self.liveMode = True
			self.updateVideoComponents()


	def _playLiveButtonReleaseCb(self, widget, event):
		self.ca.gplay.stop()

		self.RECD_INFO_ON = False
		#if you are big on the screen, don't go changing anything, ok?
		if (self.liveMode):
			return

		self.showLiveVideoTags()
		self.liveMode = True
		self.startLiveVideo( self.playLiveWindow, self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, False )
		self.updateVideoComponents()


	def recordVideo( self ):
		self.ca.glive.startRecordingVideo( )


	def recordAudio( self ):
		self.ca.glive.startRecordingAudio( )


	def updateModeChange(self):
		#this is called when a menubar button is clicked
		self.liveMode = True
		self.fullScreen = False
		self.RECD_INFO_ON = False

		#set up the x & xv x-ition (if need be)
		self.ca.gplay.stop()
		if (self.ca.m.MODE == self.ca.m.MODE_PHOTO):
			self.startLiveVideo( self.liveVideoWindow, self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, True )
		elif (self.ca.m.MODE == self.ca.m.MODE_VIDEO):
			self.startLiveVideo( self.playLiveWindow,  self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, True )
		elif (self.ca.m.MODE == self.ca.m.MODE_AUDIO):
			self.startLiveVideo( self.liveVideoWindow,  self.ca.glive.PIPETYPE_AUDIO_RECORD, True )

		self.doMouseListener( True )
		self.showLiveVideoTags()
		self.LAST_MODE = -1 #force an update
		self.recordWindow.updateGfx()
		self.updateVideoComponents()
		self.resetWidgetFadeTimer()


	def startLiveVideo(self, window, pipetype, force):
		#We need to know which window and which pipe here

		#if returning from another activity, active won't be false and needs to be to get started
		if (self.ca.glive.getPipeType() == pipetype
			and self.ca.glive.window == window
			and self.ca.ACTIVE
			and not force):
			return

		self.ca.glive.setPipeType( pipetype )
		window.set_glive(self.ca.glive)
		self.ca.glive.stop()
		self.ca.glive.play()
		print("force reset video")


	def doFullscreen( self ):
		self.fullScreen = not self.fullScreen
		self.updateVideoComponents()


	def moveWinOffscreen( self, win ):
		#we move offscreen to resize or else we get flashes on screen, and setting hide() doesn't allow resize & moves
		offW = (gtk.gdk.screen_width() + 100)
		offH = (gtk.gdk.screen_height() + 100)
		self.smartMove(win, offW, offH)


	def setImgLocDim( self, win ):
		imgDim = self.getImgDim( self.fullScreen )
		r = self.smartResize( win, imgDim[0], imgDim[1] )

		if (self.fullScreen):
			self.smartMove( win, 0, 0 )
		else:
			m = self.smartMove( win, self.centerBoxPos[0], self.centerBoxPos[1] )


	def getImgDim( self, full ):
		if (full):
			return [gtk.gdk.screen_width(), gtk.gdk.screen_height()]
		else:
			return [self.vw, self.vh]


	def setPipLocDim( self, win ):
		self.smartResize( win, self.pipw, self.piph )

		loc = self.getPipLoc( self.fullScreen )
		self.smartMove( win, loc[0], loc[1] )


	def getPipLoc( self, full ):
		if (full):
			return [self.inset+self.pipBorder, gtk.gdk.screen_height()-(self.inset+self.piph+self.pipBorder)]
		else:
			return [self.centerBoxPos[0]+self.inset+self.pipBorder, (self.centerBoxPos[1]+self.vh)-(self.inset+self.piph+self.pipBorder)]


	def setPipBgdLocDim( self, win ):
		pgdLoc = self.getPgdLoc( self.fullScreen )
		self.smartMove( win, pgdLoc[0], pgdLoc[1] )


	def getPgdLoc( self, full ):
		if (full):
			return [self.inset, gtk.gdk.screen_height()-(self.inset+self.pgdh)]
		else:
			return [self.centerBoxPos[0]+self.inset, (self.centerBoxPos[1]+self.vh)-(self.inset+self.pgdh)]


	def setMaxLocDim( self, win ):
		maxLoc = self.getMaxLoc( self.fullScreen )
		self.smartMove( win, maxLoc[0], maxLoc[1] )


	def getMaxLoc( self, full ):
		if (full):
			return [gtk.gdk.screen_width()-(self.maxw+self.inset), self.inset]
		else:
			return [(self.centerBoxPos[0]+self.vw)-(self.inset+self.maxw), self.centerBoxPos[1]+self.inset]


	def setEyeLocDim( self, win ):
		eyeLoc = self.getEyeLoc( self.fullScreen )
		self.smartMove( win, eyeLoc[0], eyeLoc[1] )


	def getEyeLoc( self, full ):
		x = (gtk.gdk.screen_width()/2) - (self.pipw/2)
		if (full):
			return [x, gtk.gdk.screen_height()-(self.inset+self.pgdh)]
		else:
			return [x, (self.centerBoxPos[1]+self.vh)-(self.inset+self.pgdh)]


	def getInfLoc( self ):
		return [(self.centerBoxPos[0]+self.vw)-(self.inset+self.letterBoxVW), self.centerBoxPos[1]+self.inset]


	def setInfLocDim( self, win ):
		self.smartResize( win, self.letterBoxVW, self.letterBoxVH )
		loc = self.getInfLoc()
		self.smartMove( win, loc[0], loc[1] )


	def getInbLoc( self, full ):
		if (full):
			return [(gtk.gdk.screen_width() + 100), (gtk.gdk.screen_height() + 100)]
		else:
			return [(self.centerBoxPos[0]+self.vw)-(self.inset+self.maxw), (self.centerBoxPos[1]+self.vh)-(self.maxh+self.inset)]


	def setInbLocDim( self, win ):
		loc = self.getInbLoc(self.fullScreen)
		self.smartMove( win, loc[0], loc[1] )


	def smartResize( self, win, w, h ):
		winSize = win.get_size()
		if ( (winSize[0] != w) or (winSize[1] != h) ):
			win.resize( w, h )
			return True
		else:
			return False


	def smartMove( self, win, x, y ):
		winLoc = win.get_position()
		if ( (winLoc[0] != x) or (winLoc[1] != y) ):
			win.move( x, y )
			return True
		else:
			return False


	def getDim( self, pos ):
		if (pos == "pip"):
			return [self.pipw, self.piph]
		elif(pos == "pgd"):
			return [self.pgdw, self.pgdh]
		elif(pos == "max"):
			return [self.maxw, self.maxh]
		elif(pos == "img"):
			return self.getImgDim( full )
		elif(pos == "eye"):
			return [self.pgdw, self.pgdh]
		elif(pos == "inf"):
			return [self.letterBoxVW, self.letterBoxVH]
		elif(pos == "inb"):
			return [self.maxw, self.maxh]


	def getLoc( self, pos, full ):
		if (pos == "pip"):
			return self.getPipLoc( full )
		elif(pos == "pgd"):
			return self.getPgdLoc( full )
		elif(pos == "max"):
			return self.getMaxLoc( full )
		elif(pos == "img"):
			return self.getImgLoc( full )
		elif(pos == "eye"):
			return self.getEyeLoc( full )
		elif(pos == "inf"):
			return self.getInfLoc( full )
		elif(pos == "inb"):
			return self.getInbLoc( full )


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
		if (self.allocated and self.mapped):
			self.recordWindow.shutterButton.set_sensitive(True)
			self.updateVideoComponents()
			self.ca.glive.play()


	def _mapEventCb( self, widget, event ):
		#when your parent window is ready, turn on the feed of live video
		self.liveVideoWindow.disconnect(self.MAP_EVENT_ID)
		self.mapped = True
		self.checkReadyToSetup()


	def _sizeAllocateCb( self, widget, event ):
		#initial setup of the panels
		self.centerBox.disconnect(self.SIZE_ALLOCATE_ID)
		self.centerBoxPos = self.centerBox.translate_coordinates( self.ca, 0, 0 )

		centerKid = self.centerBox.get_child()
		if (centerKid != None):
			self.centerBox.remove( centerKid )

		self.allocated = True
		self.checkReadyToSetup( )


	def updateVideoComponents( self ):
		if (	(self.LAST_MODE == self.ca.m.MODE)
				and (self.LAST_FULLSCREEN == self.fullScreen)
				and (self.LAST_LIVE == self.liveMode)
				and (self.LAST_RECD_INFO == self.RECD_INFO_ON)):
			print("same, same")
			return

		#something's changing so start counting anew
		self.resetWidgetFadeTimer()

		pos = []
		if (self.RECD_INFO_ON):
			if (self.ca.m.MODE == self.ca.m.MODE_PHOTO):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				pos.append({"position":"inf", "window":self.livePhotoWindow} )
				pos.append({"position":"inb", "window":self.infWindow} )
			elif (self.ca.m.MODE == self.ca.m.MODE_VIDEO):
				pos.append({"position":"pgd", "window":self.pipBgdWindow2} )
				pos.append({"position":"pip", "window":self.playLiveWindow} )
				pos.append({"position":"inf", "window":self.playOggWindow} )
				pos.append({"position":"inb", "window":self.infWindow} )
			elif (self.ca.m.MODE == self.ca.m.MODE_AUDIO):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				pos.append({"position":"inf", "window":self.livePhotoWindow} )
				pos.append({"position":"inb", "window":self.infWindow} )
		else:
			if (self.ca.m.MODE == self.ca.m.MODE_PHOTO):
				if (self.liveMode):
					pos.append({"position":"img", "window":self.liveVideoWindow})
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"eye", "window":self.recordWindow} )
				else:
					pos.append({"position":"img", "window":self.livePhotoWindow} )
					pos.append({"position":"pgd", "window":self.pipBgdWindow} )
					pos.append({"position":"pip", "window":self.liveVideoWindow} )
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"inb", "window":self.infWindow} )
			elif (self.ca.m.MODE == self.ca.m.MODE_VIDEO):
				if (self.liveMode):
					pos.append({"position":"img", "window":self.playLiveWindow} )
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"eye", "window":self.recordWindow} )
				else:
					pos.append({"position":"img", "window":self.playOggWindow} )
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"pgd", "window":self.pipBgdWindow2} )
					pos.append({"position":"pip", "window":self.playLiveWindow} )
					pos.append({"position":"inb", "window":self.infWindow} )
			elif (self.ca.m.MODE == self.ca.m.MODE_AUDIO):
				if (self.liveMode):
					pos.append({"position":"img", "window":self.liveVideoWindow} )
					pos.append({"position":"eye", "window":self.recordWindow} )
				else:
					pos.append({"position":"img", "window":self.livePhotoWindow} )
					pos.append({"position":"pgd", "window":self.pipBgdWindow} )
					pos.append({"position":"pip", "window":self.liveVideoWindow} )
					pos.append({"position":"inb", "window":self.infWindow} )

		if (self.HIDE_ON_UPDATE):
			#hide everything
			for i in range (0, len(self.windowStack)):
				self.windowStack[i].hide_all()

		#todo: only move away the windows *not* moved in the call below:
		self.hideLiveWindows()
		self.hidePlayWindows()
		self.hideAudioWindows()

		self.updatePos( pos )

		#show everything
		if (self.HIDE_ON_UPDATE):
			for i in range (0, len(self.windowStack)):
				self.windowStack[i].show_all()

		print("all reset!")
		self.LAST_MODE = self.ca.m.MODE
		self.LAST_FULLSCREEN = self.fullScreen
		self.LAST_LIVE = self.liveMode
		self.LAST_RECD_INFO = self.RECD_INFO_ON
		self.HIDE_ON_UPDATE = True


	def showWidgets( self ):
		pos = []
		if (self.ca.m.MODE == self.ca.m.MODE_PHOTO):
			if (not self.liveMode):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				pos.append({"position":"max", "window":self.maxWindow} )
				pos.append({"position":"inb", "window":self.infWindow} )
			else:
				pos.append({"position":"max", "window":self.maxWindow} )
				pos.append({"position":"eye", "window":self.recordWindow} )
		elif (self.ca.m.MODE == self.ca.m.MODE_VIDEO):
			if (not self.liveMode):
				pos.append({"position":"max", "window":self.maxWindow} )
				pos.append({"position":"pgd", "window":self.pipBgdWindow2} )
				pos.append({"position":"pip", "window":self.playLiveWindow} )
				pos.append({"position":"inb", "window":self.infWindow} )
			else:
				pos.append({"position":"max", "window":self.maxWindow} )
				pos.append({"position":"eye", "window":self.recordWindow} )
		elif (self.ca.m.MODE == self.ca.m.MODE_AUDIO):
			if (not self.liveMode):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				pos.append({"position":"inb", "window":self.infWindow} )
			else:
				pos.append({"position":"eye", "window":self.recordWindow} )

		self.updatePos( pos )


	def updatePos( self, pos ):
		#now move those pieces where they need to be...
		for i in range (0, len(self.windowStack)):
			for j in range (0, len(pos)):
				if (self.windowStack[i] == pos[j]["window"]):
					if (pos[j]["position"] == "img"):
						self.setImgLocDim( pos[j]["window"] )
					elif (pos[j]["position"] == "max"):
						self.setMaxLocDim( pos[j]["window"] )
					elif (pos[j]["position"] == "pip"):
						self.setPipLocDim( pos[j]["window"] )
					elif (pos[j]["position"] == "pgd"):
						self.setPipBgdLocDim( pos[j]["window"] )
					elif (pos[j]["position"] == "eye"):
						self.setEyeLocDim( pos[j]["window"] )
					elif (pos[j]["position"] == "inf"):
						self.setInfLocDim( pos[j]["window"] )
					elif (pos[j]["position"] == "inb"):
						self.setInbLocDim( pos[j]["window"])

	def updateThumbs( self, addToTrayArray, left, start, right ):
		#todo: cache buttons which we can reuse
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


	def _leftThumbButtonCb( self, args ):
		self.ca.m.setupThumbs( self.ca.m.MODE, self.leftThumbMove, self.leftThumbMove+self.numThumbs )


	def _rightThumbButtonCb( self, args ):
		self.ca.m.setupThumbs( self.ca.m.MODE, self.rightThumbMove, self.rightThumbMove+self.numThumbs )


	def infoButtonClicked( self ):
		self.RECD_INFO_ON = not self.RECD_INFO_ON

		centerKid = self.centerBox.get_child()
		if (centerKid != None):
			self.centerBox.remove( centerKid )

		if (not self.RECD_INFO_ON):
			self.centerBox.hide_all()
			#self.centerBox.add( self.backgdCanvasBox )
		else:
			self.centerBox.add( self.infoBox )
			self.centerBox.show_all()

		self.updateVideoComponents()


	def showPostProcessGfx( self, show ):
		centerKid = self.centerBox.get_child()
		if (centerKid != None):
			self.centerBox.remove( centerKid )

		if (show):
			self.centerBox.add( self.backgdCanvasBox )
			self.centerBox.show_all()
		else:
			self.centerBox.hide_all()


	def showThumbSelection( self, recd ):
		#do we need to know the type, since we're showing based on the mode of the app?
		if (recd.type == self.ca.m.TYPE_PHOTO):
			self.showPhoto( recd )
		elif (recd.type == self.ca.m.TYPE_VIDEO):
			self.showVideo( recd )
		elif (recd.type == self.ca.m.TYPE_AUDIO):
			self.showAudio( recd )

		self.photoXoPanel.updateXoColors()
		self.resetWidgetFadeTimer()


	def showAudio( self, recd ):
		print("showing Audio 1")

		self.liveMode = False

		#returns the small file to start with, and gets updated when the fullscreen arrives on the mesh
		#todo: gracefully replace the picture without restarting the audio
		pixbuf = recd.getAudioImagePixbuf()
		img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)
		self.livePhotoCanvas.setImage( img )
		self.shownRecd = recd

		self.updateVideoComponents()

		mediaFilepath = recd.getMediaFilepath( True )
		if (mediaFilepath != None):
			videoUrl = "file://" + str( mediaFilepath )
			self.ca.gplay.setLocation(videoUrl)
			self.showRecdMeta(recd)
			print("showing Audio 2")


	def deleteThumbSelection( self, recd ):
		self.ca.m.deleteRecorded( recd, self.startThumb )
		self.removeIfSelectedRecorded( recd )


	def removeIfSelectedRecorded( self, recd ):
		#todo: blank the livePhotoCanvas whenever it is removed
		if (recd == self.shownRecd):

			#todo: should be using modes here to check which mode to switch to
			if (recd.type == self.ca.m.TYPE_PHOTO):
				self.livePhotoCanvas.setImage( None )
			elif (recd.type == self.ca.m.TYPE_VIDEO):
				self.ca.gplay.stop()
				self.startLiveVideo( self.playLiveWindow, self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, False )
			elif (recd.type == self.ca.m.TYPE_AUDIO):
				self.livePhotoCanvas.setImage( None )
				self.startLiveAudio()

			self.liveMode = True
			self.updateVideoComponents()

			self.showLiveVideoTags()


	def startLiveAudio( self ):
		#todo: finesse the stopping of the play pipes
		self.ca.gplay.stop()

		#todo: updating
		self.ca.glive.setPipeType( self.ca.glive.PIPETYPE_AUDIO_RECORD )
		self.liveVideoWindow.set_glive(self.ca.glive)

		#self.ca.glive.stop()
		#self.ca.glive.play()

		self.showLiveVideoTags()
		self.liveMode = True
		self.updateVideoComponents()


	def updateShownMedia( self, recd ):
		print("updateShownMedia 1")
		if (self.shownRecd == recd):
			print("updateShownMedia 2")
			#todo: better method name
			self.showThumbSelection( recd )


	def showVideo( self, recd ):
		#todo: this can be cleaned up for when playing subsequent videos
		if (self.ca.glive.isXv()):
			self.ca.glive.setPipeType( self.ca.glive.PIPETYPE_X_VIDEO_DISPLAY )
			self.ca.glive.stop()
			self.ca.glive.play()

		self.liveMode = False
		self.updateVideoComponents()

		#todo: yank from the datastore here, yo
		#todo: use os.path calls here, see jukebox
		#~~> urllib.quote(os.path.abspath(file_path))

		mediaFilepath = recd.getMediaFilepath( True )
		if (mediaFilepath == None):
			mediaFilepath = recd.getThumbFilepath( True )

		#todo: might need to pause the player...
		videoUrl = "file://" + str( mediaFilepath )
		print( "videoUrl: ", videoUrl )
		self.ca.gplay.setLocation(videoUrl)

		self.shownRecd = recd
		self.showRecdMeta(recd)


	def showRecdMeta( self, recd ):
		self.photographerNameLabel.set_label( recd.photographer )
		self.nameTextfield.set_text( recd.title )
		self.nameTextfield.set_sensitive( True )
		self.dateDateLabel.set_label( strftime( "%a, %b %d, %I:%M:%S %p", time.localtime(recd.time) ) )

		self.photographerPanel.show()
		self.namePanel.show()
		self.datePanel.show()
		self.tagsPanel.show()
		self.tagsBuffer.set_text("")


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
		closeSvgData = closeSvgFile.read()
		self.closeSvg = self.loadSvg(closeSvgData, self.colorStroke.hex, self.colorFill.hex)
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

		shutterCamImgFile = os.path.join(self.ca.gfxPath, 'device-cam.png')
		shutterCamImgPixbuf = gtk.gdk.pixbuf_new_from_file(shutterCamImgFile)
		self.shutterCamImg = gtk.Image()
		self.shutterCamImg.set_from_pixbuf( shutterCamImgPixbuf )

		shutterMicImgFile = os.path.join(self.ca.gfxPath, 'device-mic.png')
		shutterMicImgPixbuf = gtk.gdk.pixbuf_new_from_file(shutterMicImgFile)
		self.shutterMicImg = gtk.Image()
		self.shutterMicImg.set_from_pixbuf( shutterMicImgPixbuf )

		infoOnSvgFile = open(os.path.join(self.ca.gfxPath, 'info-on.svg'), 'r')
		infoOnSvgData = infoOnSvgFile.read()
		self.infoOnSvg = self.loadSvg(infoOnSvgData, None, None )
		infoOnSvgFile.close()

		infoOffSvgFile = open(os.path.join(self.ca.gfxPath, 'info-off.svg'), 'r')
		infoOffSvgData = infoOffSvgFile.read()
		self.infoOffSvg = self.loadSvg(infoOffSvgData, None, None )
		infoOffSvgFile.close()

		xoGuySvgFile = open(os.path.join(self.ca.gfxPath, 'xo-guy.svg'), 'r')
		self.xoGuySvgData = xoGuySvgFile.read()
		infoOffSvgFile.close()


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
		#todo: get this from the os
		self.colorBg.init_rgba( 226, 226, 226, 255 )
		self.colorRed = Color()
		self.colorRed.init_rgba( 255, 0, 0, 255)
		self.colorGreen = Color()
		self.colorGreen.init_rgba( 0, 255, 0, 255)
		self.colorBlue = Color()
		self.colorBlue.init_rgba( 0, 0, 255, 255)


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
		#todo: set to default bg color
		#self.background( ctx, self.ui.colorRed, w, h )
		ctx.translate( (w/2)-(h/2), 0 )
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
					self.drawImg = None
					self.scalingImageCb = gobject.idle_add( self.resizeImage, w, h )

			if (self.drawImg != None):
				#center the image based on the image size, and w & h
				ctx.set_source_surface(self.drawImg, (w/2)-(self.drawImg.get_width()/2), (h/2)-(self.drawImg.get_height()/2))
				ctx.paint()

			self.cacheWid = w


	def setImage(self, img):
		self.cacheWid = -1
		self.img = img

#		if (self.img == None):
#			self.drawImg = None
		self.drawImg = None

		self.queue_draw()


	def resizeImage(self, w, h):
		#use image size in case 640 no more
		scaleImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
		sCtx = cairo.Context(scaleImg)
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


class xoPanel(P5):
	def __init__(self, ui):
		P5.__init__(self)
		self.ui = ui

		self.xoGuy = None
		self.lastStroke = None
		self.lastFill = None


	def updateXoColors( self ):
		if ((self.lastStroke == self.ui.shownRecd.colorStroke.hex) and (self.lastFill == self.ui.shownRecd.colorFill.hex)):
			return

		lastStroke = self.ui.shownRecd.colorStroke.hex
		lastFill = self.ui.shownRecd.colorFill.hex

		if (self.ui.shownRecd != None):
			self.xoGuy = self.ui.loadSvg(self.ui.xoGuySvgData, self.ui.shownRecd.colorStroke.hex, self.ui.shownRecd.colorFill.hex)
		else:
			self.xoGuy = None

		self.queue_draw()


	def draw(self, ctx, w, h):
		#todo: 2x buffer

		#todo: bgd for the info panel..
		self.background( ctx, self.ui.colorWhite, w, h )

		if (self.xoGuy != None):
			#todo: scale mr xo
			ctx.scale( .5, .5 )
			self.xoGuy.render_cairo( ctx )
			print("see me?")


class MaxWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.maxButton = MaxButton(self.ui)
		self.add( self.maxButton )


class MaxButton(P5Button):
	def __init__(self, ui):
		P5Button.__init__(self)
		self.ui = ui
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


class InfWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.infButton = InfButton(self.ui)
		self.add( self.infButton )


class InfButton(P5Button):
	def __init__(self, ui):
		P5Button.__init__(self)
		self.ui = ui
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
		self.infS = "inf"
		butt.setActionCommand( self.infS )
		self._butts.append( butt )

	def draw(self, ctx, w, h):
		if (not self.ui.RECD_INFO_ON):
			self.ui.infoOnSvg.render_cairo( ctx )
		else:
			self.ui.infoOffSvg.render_cairo( ctx )

	def fireButton(self, actionCommand):
		if (actionCommand == self.infS):
			self.ui.infoButtonClicked()


#todo: rename, and handle clear events to clear away and remove all listeners
class ThumbnailCanvas(gtk.VBox):
	def __init__(self, pui):
		gtk.VBox.__init__(self)
		self.ui = pui

		self.recd = None
		self.butt = None
		self.delButt = None
		self.thumbPixbuf = None
		self.thumbCanvas = None

		self.butt = ThumbnailButton(self, self.ui)
		self.pack_start(self.butt, expand=True)

		self.delButt = ThumbnailDeleteButton(self, self.ui)
		self.delButt.set_size_request( -1, 20 )
		#self.pack_start(self.delButt, expand=False)

		self.show_all()


	def set_sensitive(self, sen):
		#todo: change colors here to gray'd out, and don't change if already in that mode
		self.butt.set_sensitive( sen )
		self.delButt.set_sensitive( sen )


	def clear(self):
		self.recd = None
		self.thumbPixbuf = None
		self.thumbCanvas = None
		self.butt.clear()
		self.butt.queue_draw()
		self.delButt.clear()
		self.delButt.queue_draw()


	def setButton(self, recd):
		self.recd = recd
		if (self.recd == None):
			return

		self.loadThumb()
		self.butt.setDraggable()
		self.butt.queue_draw()
		self.delButt.queue_draw()


	def loadThumb(self):
		#todo: either thumbs are going into the main datastore object or they are dynamic.  ask dcbw for advice.
		if (self.recd == None):
			#todo: alert error here?
			return

		self.thumbPixbuf = self.recd.getThumbPixbuf( )
		#todo: handle None
		self.thumbCanvas = _camera.cairo_surface_from_gdk_pixbuf( self.thumbPixbuf )


class ThumbnailDeleteButton(gtk.Button):
	def __init__(self, ptc, ui):
		gtk.Button.__init__(self)
		self.tc = ptc
		self.ui = ui
		self.recd = None
		self.recdThumbRenderImg = None
		self.recdThumbInsensitiveImg = None

		self.exposeConnection = self.connect("expose_event", self.expose)
		self.clickConnection = self.connect("clicked", self.buttonClickCb)

	def clear( self ):
		self.recdThumbRenderImg == None
		self.recdThumbInsensitiveImg = None

	def buttonClickCb(self, args ):
		if (self.tc.recd == None):
			return
		if (not self.props.sensitive):
			return

		self.ui.deleteThumbSelection( self.tc.recd )

	def expose(self, widget, event):
		ctx = widget.window.cairo_create()
		self.draw( ctx, self.allocation.width, self.allocation.height )
		return True

	def draw(self, ctx, w, h):
		ctx.translate( self.allocation.x, self.allocation.y )
		self.background( ctx, self.ui.colorTray, w, h )
		if (self.tc.recd == None):
			return

		if (self.recdThumbRenderImg == None):
			self.recdThumbRenderImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
			rtCtx = cairo.Context(self.recdThumbRenderImg)
			self.background(rtCtx, self.ui.colorTray, w, h)

			#todo: dynamic query of the delete button size
			rtCtx.translate( w/2-25/2, 0 )
			self.ui.closeSvg.render_cairo(rtCtx)


		ctx.set_source_surface(self.recdThumbRenderImg, 0, 0)
		ctx.paint()

	def background(self, ctx, col, w, h):
		self.setColor( ctx, col )

		ctx.line_to(0, 0)
		ctx.line_to(w, 0)
		ctx.line_to(w, h)
		ctx.line_to(0, h)
		ctx.close_path()

		ctx.fill()

	def setColor( self, ctx, col ):
		if (not col._opaque):
			ctx.set_source_rgba( col._r, col._g, col._b, col._a )
		else:
			ctx.set_source_rgb( col._r, col._g, col._b )


class ThumbnailButton(gtk.Button):
	def __init__(self, ptc, ui):
		gtk.Button.__init__(self)
		self.tc = ptc
		self.ui = ui
		self.recd = None
		self.recdThumbRenderImg = None
		self.recdThumbInsensitiveImg = None

		self.exposeConnection = self.connect("expose_event", self._exposeEventCb)
		self.clickConnection = self.connect("clicked", self._buttonClickCb)
		self.dragBeginConnection = None
		self.dragDataGetConnection = None
		self.dragEndConnection = None


	def setDraggable( self ):
		#todo: update when the media has been downloaded

		if ( self.tc.recd.isClipboardCopyable() ):
			targets =[]
			#todo: make an array for all the mimes we support for these calls
			if ( self.tc.recd.type == self.ui.ca.m.TYPE_PHOTO ):
				targets = [('image/jpeg', 0, 0)]
			elif ( self.tc.recd.type == self.ui.ca.m.TYPE_VIDEO ):
				targets = [('video/ogg', 0, 0)]
			elif ( self.tc.recd.type == self.ui.ca.m.TYPE_AUDIO ):
				targets = [('audio/wav', 0, 0)]

			if ( len(targets) > 0 ):
				self.drag_source_set( gtk.gdk.BUTTON1_MASK, targets, gtk.gdk.ACTION_COPY)
				self.dragBeginConnection = self.connect("drag_begin", self._dragBeginCb)
				self.dragDataGetConnection = self.connect("drag_data_get", self._dragDataGetCb)
				self.dragEndConnection = self.connect("drag_end", self._dragEndCb)


	def clear( self ):
		#todo: no dragging if insensitive either, why not?
		self.drag_source_unset()
		self.recdThumbRenderImg = None
		self.recdThumbInsensitiveImg = None

		#todo: remove the tempImagePath file..
		self.tempImgPath = None

		#disconnect the dragConnections
		if (self.dragBeginConnection != None):
			if (self.dragBeginConnection != 0):
				self.disconnect(self.dragBeginConnection)
				self.disconnect(self.dragDataGetConnection)
				self.disconnect(self.dragEndConnection)
				self.dragBeginConnection = None
				self.dragDataGetConnection = None
				self.dragEndConnection = None


	def _buttonClickCb(self, args ):
		if (self.tc.recd == None):
			return
		if (not self.props.sensitive):
			return
		self.ui.showThumbSelection( self.tc.recd )


	def _exposeEventCb(self, widget, event):
		ctx = widget.window.cairo_create()
		self.draw( ctx, self.allocation.width, self.allocation.height )
		return True


	def _dragEndCb(self, widget, dragCtxt):
		self.ui.doClipboardCopyFinish( self.tempImgPath )


	def _dragBeginCb(self, widget, dragCtxt ):
		self.drag_source_set_icon_pixbuf( self.tc.thumbPixbuf )


	def _dragDataGetCb(self, widget, drag_context, selection_data, info, timestamp):
		if (	(selection_data.target == 'image/jpeg') or
				(selection_data.target == 'video/ogg' ) or
				(selection_data.target == 'audio/wav')	):
			self.tempImgPath = self.ui.doClipboardCopyStart( self.tc.recd )
			self.ui.doClipboardCopyCopy( self.tempImgPath, selection_data )


	def draw(self, ctx, w, h):
		ctx.translate( self.allocation.x, self.allocation.y )
		self.background( ctx, self.ui.colorTray, w, h )

		if (self.tc.recd == None):
			return
		if (self.tc.thumbCanvas == None):
			return

		if (self.recdThumbRenderImg == None):
			self.recdThumbRenderImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
			rtCtx = cairo.Context(self.recdThumbRenderImg)
			self.background(rtCtx, self.ui.colorTray, w, h)

			xSvg = (w-self.ui.thumbSvgW)/2
			ySvg = (h-self.ui.thumbSvgH)/2
			rtCtx.translate( xSvg, ySvg )

			if (self.tc.recd.type == self.ui.ca.m.TYPE_PHOTO):
				if (self.tc.recd.buddy):
					thumbPhotoSvg = self.ui.loadSvg(self.ui.thumbPhotoSvgData, self.tc.recd.colorStroke.hex, self.tc.recd.colorFill.hex)
					thumbPhotoSvg.render_cairo(rtCtx)
				else:
					self.ui.thumbPhotoSvg.render_cairo(rtCtx)

				rtCtx.translate( 8, 8 )
				rtCtx.set_source_surface(self.tc.thumbCanvas, 0, 0)
				rtCtx.paint()

			elif (self.tc.recd.type == self.ui.ca.m.TYPE_VIDEO):
				if (self.tc.recd.buddy):
					thumbVideoSvg = self.ui.loadSvg(self.ui.thumbVideoSvgData, self.tc.recd.colorStroke.hex, self.tc.recd.colorFill.hex)
					thumbVideoSvg.render_cairo(rtCtx)
				else:
					self.ui.thumbVideoSvg.render_cairo(rtCtx)

				rtCtx.translate( 8, 22 )
				rtCtx.set_source_surface(self.tc.thumbCanvas, 0, 0)
				rtCtx.paint()


			elif (self.tc.recd.type == self.ui.ca.m.TYPE_AUDIO):
				if (self.tc.recd.buddy):
					thumbVideoSvg = self.ui.loadSvg(self.ui.thumbVideoSvgData, self.tc.recd.colorStroke.hex, self.tc.recd.colorFill.hex)
					thumbVideoSvg.render_cairo(rtCtx)
				else:
					self.ui.thumbVideoSvg.render_cairo(rtCtx)

				rtCtx.translate( 8, 22 )
				rtCtx.set_source_surface(self.tc.thumbCanvas, 0, 0)
				rtCtx.paint()

		ctx.set_source_surface(self.recdThumbRenderImg, 0, 0)
		ctx.paint()

	def background(self, ctx, col, w, h):
		self.setColor( ctx, col )

		ctx.line_to(0, 0)
		ctx.line_to(w, 0)
		ctx.line_to(w, h)
		ctx.line_to(0, h)
		ctx.close_path()

		ctx.fill()

	def setColor( self, ctx, col ):
		if (not col._opaque):
			ctx.set_source_rgba( col._r, col._g, col._b, col._a )
		else:
			ctx.set_source_rgb( col._r, col._g, col._b )



class RecordWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui

		self.shutterButton = gtk.Button()
		self.shutterButton.set_image( self.ui.shutterCamImg )
		self.shutterButton.connect("clicked", self.ui.shutterClickCb)
		#todo: this is insensitive until we're all set up
		#self.shutterButton.set_sensitive(False)
		shutterBox = gtk.EventBox()
		shutterBox.modify_bg( gtk.STATE_NORMAL, self.ui.colorWhite.gColor )
		self.shutterButton.set_border_width( self.ui.pipBorder )

		shutterBox.add( self.shutterButton )
		self.add( shutterBox )

	def updateGfx( self ):
		if (self.ui.ca.m.MODE == self.ui.ca.m.MODE_AUDIO):
			if (self.shutterButton.get_image() != self.ui.shutterMicImg):
				self.shutterButton.set_image( self.ui.shutterMicImg )
		else:
			if (self.shutterButton.get_image() != self.ui.shutterCamImg):
				self.shutterButton.set_image( self.ui.shutterCamImg )


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

		self.audButt = RadioToolButton( "menubar_video" )
		self.audButt.set_group( self.picButt )
		self.audButt.set_tooltip("Audio")
		self.audButt.props.sensitive = True
		self.audButt.connect('clicked', self.modeAudioCb)
		self.insert(self.audButt, -1)
		self.audButt.show()


	def modeVideoCb(self, button):
		self.ca.m.doVideoMode()

	def modePhotoCb(self, button):
		self.ca.m.doPhotoMode()

	def modeAudioCb(self, button):
		self.ca.m.doAudioMode()


class SearchToolbar(gtk.Toolbar):
	def __init__(self, pc):
		gtk.Toolbar.__init__(self)
		self.ca = pc