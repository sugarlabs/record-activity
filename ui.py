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
		self.photoMode = True
		self.fullScreen = False
		self.liveMode = True

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
		self.pipBorderW = self.pipw + (self.pipBorder*2)
		self.pipBorderH = self.piph + (self.pipBorder*2)
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

		#number of thumbs
		self.numThumbs = 7

		#prep for when to show
		self.exposed = False
		self.mapped = False

		self.shownRecd = None

		#this includes the default sharing tab
		toolbox = activity.ActivityToolbox(self.ca)
		self.ca.set_toolbox(toolbox)
		self.modeToolbar = ModeToolbar(self.ca)
		#todo: internationalize this
		toolbox.add_toolbar( ('Record'), self.modeToolbar )
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

		self.namePanel = gtk.VBox(spacing=self.inset)
		infoBox.pack_start(self.namePanel, expand=False)
		#todo: internationalize this...
		nameLabel = gtk.Label("Title:")
		self.namePanel.pack_start( nameLabel, expand=False )
		nameLabel.set_alignment(0, .5)
		#todo: listen for changes here
		self.nameTextfield = gtk.Entry(80)
		self.nameTextfield.connect('changed', self._nameTextfieldEditedCb )
		self.nameTextfield.set_alignment(0)
		self.namePanel.pack_start(self.nameTextfield)

		self.photographerPanel = gtk.VBox(spacing=self.inset)
		infoBox.pack_start(self.photographerPanel, expand=False)
		photographerLabel = gtk.Label("Recorder:")
		self.photographerPanel.pack_start(photographerLabel, expand=False)
		photographerLabel.set_alignment(0, .5)
		self.photographerNameLabel = gtk.Label("")
		self.photographerNameLabel.set_alignment(0, .5)
		self.photographerPanel.pack_start(self.photographerNameLabel)

		self.datePanel = gtk.HBox(spacing=self.inset)
		infoBox.pack_start(self.datePanel, expand=False)
		dateLabel = gtk.Label("Date:")
		self.datePanel.pack_start(dateLabel, expand=False)
		self.dateDateLabel = gtk.Label("")
		self.dateDateLabel.set_alignment(0, .5)
		self.datePanel.pack_start(self.dateDateLabel)

		#todo: move this into its own window
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


		##
		##
		#the video scrubber
		self.videoScrubBox = gtk.HBox()
		self.videoScrubPanel.add( self.videoScrubBox )

		self.pause_image = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE, gtk.ICON_SIZE_BUTTON)
		self.pause_image.show()
		self.play_image = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_BUTTON)
		self.play_image.show()

		self.playPauseButton = gtk.ToolButton()
		self.playPauseButton.set_icon_widget(self.play_image)
		self.playPauseButton.set_property('can-default', True)
		self.playPauseButton.show()
		self.playPauseButton.connect('clicked', self._playPauseButtonCb)

		self.videoScrubBox.pack_start(self.playPauseButton, expand=False)

		self.adjustment = gtk.Adjustment(0.0, 0.00, 100.0, 0.1, 1.0, 1.0)
		self.hscale = gtk.HScale(self.adjustment)
		self.hscale.set_draw_value(False)
		self.hscale.set_update_policy(gtk.UPDATE_CONTINUOUS)
		self.hscale.connect('button-press-event', self._scrubberPressCb)
		self.hscale.connect('button-release-event', self._scrubberReleaseCb)

		self.scale_item = gtk.ToolItem()
		self.scale_item.set_expand(True)
		self.scale_item.add(self.hscale)
		self.videoScrubBox.pack_start(self.scale_item, expand=True)
		##
		##


		thumbnailsEventBox = gtk.EventBox()
		thumbnailsEventBox.modify_bg( gtk.STATE_NORMAL, self.colorTray.gColor )
		thumbnailsEventBox.set_size_request( -1, self.thumbTrayHt )
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
			self.thumbButts.append( thumbButt )
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
		self.livePhotoWindow.resize( self.vw, self.vh )
		self.livePhotoCanvas = PhotoCanvas(self)
		self.livePhotoWindow.setPhotoCanvas(self.livePhotoCanvas)
		self.livePhotoWindow.set_transient_for(self.ca)
		self.livePhotoWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.livePhotoWindow.set_decorated(False)
		self.livePhotoWindow.set_focus_on_map(False)
		self.livePhotoWindow.set_property("accept-focus", False)

		#pipbackground here
		self.livePipBgdWindow = PipWindow(self)
		self.livePipBgdWindow.resize( self.pipBorderW, self.pipBorderH )
		self.livePipBgdWindow.set_transient_for(self.livePhotoWindow)
		self.livePipBgdWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.livePipBgdWindow.set_decorated(False)
		self.livePipBgdWindow.set_focus_on_map(False)
		self.livePipBgdWindow.set_property("accept-focus", False)

		self.liveVideoWindow = LiveVideoWindow()
		self.liveVideoWindow.resize( self.vw, self.vh )
		self.liveVideoWindow.set_transient_for(self.livePipBgdWindow)
		self.liveVideoWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.liveVideoWindow.set_decorated(False)
		self.liveVideoWindow.set_glive(self.ca.glive)
		self.liveVideoWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.liveVideoWindow.connect("button_release_event", self.liveButtonReleaseCb)
		self.liveVideoWindow.set_focus_on_map(False)
		self.liveVideoWindow.set_property("accept-focus", False)

		self.liveMaxWindow = MaxWindow(self, True)
		self.liveMaxWindow.resize( self.maxw, self.maxh )
		self.liveMaxWindow.set_transient_for(self.liveVideoWindow)
		self.liveMaxWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.liveMaxWindow.set_decorated(False)
		self.liveMaxWindow.set_focus_on_map(False)
		self.liveMaxWindow.set_property("accept-focus", False)

		self.hideLiveWindows()

		#video playback windows
		#todo: make into an array, replete with constructors, etc.
		self.playOggWindow = PlayVideoWindow()
		self.playOggWindow.resize(self.vw, self.vh)
		self.playOggWindow.set_gplay(self.ca.gplay)
		self.playOggWindow.set_transient_for(self.liveMaxWindow)
		self.playOggWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playOggWindow.set_decorated(False)
		self.playOggWindow.set_focus_on_map(False)
		self.playOggWindow.set_property("accept-focus", False) 

		#pipbackground here
		self.playLivePipBgdWindow = PipWindow(self)
		self.playLivePipBgdWindow.resize( self.pipBorderW, self.pipBorderH )
		self.playLivePipBgdWindow.set_transient_for(self.playOggWindow)
		self.playLivePipBgdWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playLivePipBgdWindow.set_decorated(False)
		self.playLivePipBgdWindow.set_focus_on_map(False)
		self.playLivePipBgdWindow.set_property("accept-focus", False)

		self.playLiveWindow = LiveVideoWindow()
		self.playLiveWindow.resize( self.pipw, self.piph )
		self.playLiveWindow.set_transient_for(self.playLivePipBgdWindow)
		self.playLiveWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playLiveWindow.set_decorated(False)
		self.playLiveWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.playLiveWindow.connect("button_release_event", self.playLiveButtonReleaseCb)
		self.playLiveWindow.set_focus_on_map(False)
		self.playLiveWindow.set_property("accept-focus", False)

		self.playMaxWindow = MaxWindow(self, False)
		self.playMaxWindow.resize( self.maxw, self.maxh )
		self.playMaxWindow.set_transient_for(self.playLiveWindow)
		self.playMaxWindow.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.playMaxWindow.set_decorated(False)
		self.playMaxWindow.set_focus_on_map(False)
		self.playMaxWindow.set_property("accept-focus", False)

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

		#actually, we're not showing you just yet
		self.videoScrubPanel.hide_all()
		self.showLiveVideoTags()

		#listen for ctrl+c
		self.ca.connect('key-press-event', self._keyPressEventCb)

		#overlay widgets can go away after they've been on screen for a while
		self.hiddenWidgets = False
		self.resetWidgetFadeTimer()


	def resetWidgetFadeTimer( self ):
		#only show the clutter when the mouse moves
		self.mx = -1
		self.my = -1
		self.hideWidgetsTimer = 0
		if (self.hiddenWidgets):
			print("reshow widgets")
		#todo: how do you stop a gobject.timeout_add?
		#answer: gobject.source_remove(source_id)
		self.hideWidgetTimeout = gobject.timeout_add( 500, self._mouseMightaMovedCb )


	def _mouseMightaMovedCb( self ):

		x, y = self.ca.get_pointer()
		if (x != self.mx or y != self.my):
			self.hideWidgetsTimer = 0
			#todo: be sure to show the widgets here iff hidden
			if (self.hiddenWidgets):
				self.hiddenWidgets = False
				print("reshow widgets")
		else:
			#todo: use time here?
			self.hideWidgetsTimer = self.hideWidgetsTimer + 500

		if (self.hideWidgetsTimer > 7500):
			if (not self.hiddenWidgets):
				print("hide widgets")
			self.hiddenWidgets = True



		self.mx = x
		self.my = y
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
		#we listen here for CTRL+C events
		keyname = gtk.gdk.keyval_name(event.keyval)
		print( "keyname:", keyname )
		if (keyname == 'c' and event.state == gtk.gdk.CONTROL_MASK):
			if (not self.shownRecd == None):
				if (self.shownRecd.type == self.ca.m.TYPE_PHOTO):
					tempImgPath = self.doClipboardCopyStart( self.shownRecd )
					gtk.Clipboard().set_with_data( [('text/uri-list', 0, 0)], self._clipboardGetFuncCb, self._clipboardClearFuncCb, tempImgPath )
					return True

		return False

	def doClipboardCopyStart( self, recd ):
		#todo: gracefully make sure you are yanking from the datastore here
		imgPath_s = os.path.join(self.ca.journalPath, recd.mediaFilename)
		imgPath_s = os.path.abspath(imgPath_s)
		#todo: get alternate path for buddies pics...

		#todo: truly unique filenames for temp... #and check they're not taken..
		tempImgPath = os.path.join("tmp", recd.mediaFilename)
		tempImgPath = os.path.abspath(tempImgPath)
		shutil.copyfile(imgPath_s, tempImgPath)
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
			self.livePhotoCanvas.setImage(img)

			self.liveMode = False
			self.updateVideoComponents()

			self.showRecdMeta(recd)


	def getPhotoPixbuf( self, recd ):
		pixbuf = None
		imgPath = recd.getMediaFilepath( )
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
		self.dateDateLabel.set_label( "Today" )

		#todo: figure this out without the ui collapsing around it
		self.namePanel.hide()
		self.photographerPanel.hide()
		self.datePanel.hide()

		#self.videoScrubPanel.hide_all()


	def updateButtonSensitivities( self ):
		#todo: make the gtk.entry uneditable
		self.shutterButton.set_sensitive( not self.ca.m.UPDATING )

		switchStuff = ((not self.ca.m.UPDATING) and (not self.ca.m.RECORDING))

		self.modeToolbar.picButt.set_sensitive( switchStuff )
		self.modeToolbar.vidButt.set_sensitive( switchStuff )

		for i in range (0, len(self.thumbButts)):
			self.thumbButts[i].set_sensitive( switchStuff )

		if (self.ca.m.UPDATING):
			self.ca.ui.setWaitCursor()
		else:
			self.ca.ui.setDefaultCursor( )

		if (self.ca.m.RECORDING):
			self.shutterButton.modify_bg( gtk.STATE_NORMAL, self.colorRed.gColor )
		else:
			self.shutterButton.modify_bg( gtk.STATE_NORMAL, None )


	def hideLiveWindows( self ):
		self.moveWinOffscreen( self.livePhotoWindow )
		self.moveWinOffscreen( self.livePipBgdWindow )
		self.moveWinOffscreen( self.liveVideoWindow )
		self.moveWinOffscreen( self.liveMaxWindow )


	def hidePlayWindows( self ):
		self.moveWinOffscreen( self.playOggWindow )
		self.moveWinOffscreen( self.playLivePipBgdWindow )
		self.moveWinOffscreen( self.playLiveWindow )
		self.moveWinOffscreen( self.playMaxWindow )


	def liveButtonReleaseCb(self, widget, event):
		self.livePhotoCanvas.setImage(None)
		if (self.liveMode != True):
			#todo: updating here?
			self.showLiveVideoTags()
			self.liveMode = True
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
		#todo: move the video offscreen when switching modes until the video comes on and is playng

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

		self.showLiveVideoTags()
		self.updateVideoComponents()


	def startXV(self, window):
		#if returning from another activity, active won't be false and needs to be to get started
		if (self.ca.glive.xv and self.ca.glive.window == window and self.ca.ACTIVE):
			return

		self.ca.glive.xv = True
		window.set_glive(self.ca.glive)
		self.ca.glive.stop()
		self.ca.glive.play()


	def doFullscreen( self ):
		self.fullScreen = not self.fullScreen
		self.updateVideoComponents()

	def moveWinOffscreen( self, win ):
		#we move offscreen to resize or else we get flashes on screen, and setting hide() doesn't allow resize & moves
		offW = (gtk.gdk.screen_width() + 100)
		offH = (gtk.gdk.screen_height() + 100)
		win.move(offW, offH)

	def setImgLocDim( self, win ):
		#this is *very* annoying... this call makes the video not show up at launch
		#win.hide_all()

		#win.hide()

		self.moveWinOffscreen( win )

		if (self.fullScreen):
			win.resize( gtk.gdk.screen_width(), gtk.gdk.screen_height() )
			win.move( 0, 0 )
		else:
			win.resize( self.vw, self.vh )
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			print( vPos[0], vPos[1] )
			win.move( vPos[0], vPos[1] )

		#win.show_all()


	def setPipLocDim( self, win ):
		#this order of operations prevents video flicker
		#win.hide()

		self.moveWinOffscreen( win )

		win.resize( self.pipw, self.piph )

		if (self.fullScreen):
			win.move( self.inset, gtk.gdk.screen_height()-(self.inset+self.piph))
		else:
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			win.move( vPos[0]+self.inset, (vPos[1]+self.vh)-(self.inset+self.piph) )

		#win.show_all()


	def setPipBgdLocDim( self, win ):
		#win.hide()

		if (self.fullScreen):
			win.move( self.inset-self.pipBorder, gtk.gdk.screen_height()-(self.inset+self.piph+self.pipBorder))
		else:
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			win.move( vPos[0]+(self.inset-self.pipBorder), (vPos[1]+self.vh)-(self.inset+self.piph+self.pipBorder) )

		#win.show_all()


	def setMaxLocDim( self, win ):
		#win.hide()

		if (self.fullScreen):
			win.move( gtk.gdk.screen_width()-(self.maxw+self.inset), self.inset )
		else:
			vPos = self.backgdCanvas.translate_coordinates( self.ca, 0, 0 )
			win.move( (vPos[0]+self.vw)-(self.inset+self.maxw), vPos[1]+self.inset)

		#win.show_all()


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

#		self.livePhotoWindow.hide()
#		self.livePipBgdWindow.hide()
#		self.liveVideoWindow.hide()
#		self.liveMaxWindow.hide()
#		self.playOggWindow.hide()
#		self.playLivePipBgdWindow.hide()
#		self.playLiveWindow.hide()
#		self.playMaxWindow.hide()

		if (self.photoMode):
			if (self.liveMode):
				self.moveWinOffscreen( self.livePipBgdWindow )

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
				self.moveWinOffscreen( self.playOggWindow )
				self.moveWinOffscreen( self.playLivePipBgdWindow )

				self.setImgLocDim( self.playLiveWindow )
				self.setMaxLocDim( self.playMaxWindow )
			else:
				self.setImgLocDim( self.playOggWindow )
				self.setMaxLocDim( self.playMaxWindow )
				self.setPipBgdLocDim( self.playLivePipBgdWindow )
				self.setPipLocDim( self.playLiveWindow )


#		self.livePhotoWindow.realize()
#		self.livePhotoWindow.set_transient_for(self.ca)
#		self.livePhotoWindow.window.raise_()
#		self.livePhotoWindow.show_all()

#		self.livePipBgdWindow.realize()
#		self.livePipBgdWindow.set_transient_for(self.livePhotoWindow)
#		self.livePipBgdWindow.window.raise_()
#		self.livePipBgdWindow.show_all()

#		self.liveVideoWindow.realize()
#		self.liveVideoWindow.set_transient_for(self.livePipBgdWindow)
#		self.liveVideoWindow.window.raise_()
#		self.liveVideoWindow.show_all()

#		self.liveMaxWindow.realize()
#		self.liveMaxWindow.set_transient_for(self.liveVideoWindow)
#		self.liveMaxWindow.window.raise_()
#		self.liveMaxWindow.show_all()

#		self.playOggWindow.realize()
#		self.playOggWindow.set_transient_for(self.liveMaxWindow)
#		self.playOggWindow.window.raise_()
#		self.playOggWindow.show_all()

#		self.playLivePipBgdWindow.realize()
#		self.playLivePipBgdWindow.set_transient_for(self.playOggWindow)
#		self.playLivePipBgdWindow.window.raise_()
#		self.playLivePipBgdWindow.show_all()

#		self.playLiveWindow.realize()
#		self.playLiveWindow.set_transient_for(self.playLivePipBgdWindow)
#		self.playLiveWindow.window.raise_()
#		self.playLiveWindow.show_all()

#		self.playMaxWindow.realize()
#		self.playMaxWindow.set_transient_for(self.playLiveWindow)
#		self.playMaxWindow.window.raise_()
#		self.playMaxWindow.show_all()

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
		print("deleteThumbSelection 1")
		self.ca.m.deleteRecorded( recd, self.startThumb )
		print("deleteThumbSelection 2")
		self.removeIfSelectedRecorded( recd )
		print("deleteThumbSelection 3")

	#todo: blank the livePhotoCanvas whenever it is removed
	def removeIfSelectedRecorded( self, recd ):
		if (recd == self.shownRecd):

			if (recd.type == self.ca.m.TYPE_PHOTO):
				self.livePhotoCanvas.setImage(None)
			elif (recd.type == self.ca.m.TYPE_VIDEO):
				self.ca.gplay.stop()
				self.startXV( self.playLiveWindow )

			self.liveMode = True
			self.updateVideoComponents()

			self.showLiveVideoTags()


	def updateShownPhoto( self, recd ):
		if (self.shownRecd == recd):
			self.showPhoto( recd )


	def showVideo( self, recd ):
		if (self.ca.glive.xv):
			self.ca.glive.xv = False
			#redundant (?)
			#self.playLiveWindow.set_glive(self.ca.glive)
			self.ca.glive.stop()
			self.ca.glive.play()

		self.liveMode = False
		self.updateVideoComponents()

		#todo: yank from the datastore here, yo
		#todo: use os.path calls here, see jukebox
		#~~> urllib.quote(os.path.abspath(file_path))
		mediaFilepath = recd.getMediaFilepath( )
		videoUrl = "file://" + str( mediaFilepath )
		print( "videoUrl: ", videoUrl )
		#+ str(self.ca.journalPath) +"/"+ str(recd.mediaFilename)
		self.ca.gplay.setLocation(videoUrl)

		#self.videoScrubPanel.show_all()

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
		self.pack_start(self.delButt, expand=False)

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

		print("buttonClickCb 1")
		self.ui.deleteThumbSelection( self.tc.recd )
		print("buttonClickCb 2")

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
		#todo: let you drag your buddy's photos around if they're downloaded...
		if ( (not self.tc.recd.buddy) and (self.tc.recd.type == self.ui.ca.m.TYPE_PHOTO) ):
			targets = [('image/jpeg', 0, 0)]
			self.drag_source_set( gtk.gdk.BUTTON1_MASK, targets, gtk.gdk.ACTION_COPY)
			self.dragBeginConnection = self.connect("drag_begin", self._dragBeginCb)
			self.dragDataGetConnection = self.connect("drag_data_get", self._dragDataGetCb)
			self.dragEndConnection = self.connect("drag_end", self._dragEndCb)


#	def set_sensitive( self, sen ):
#		gtk.Button.se

	def clear( self ):
		#todo: no dragging if insensitive either, why not?
		self.drag_source_unset()
		self.recdThumbRenderImg = None
		self.recdThumbInsensitiveImg = None

		#todo: remove the tempImagePath file..
		self.tempImgPath = None

		#todo: disconnect the dragConnections
		#print( "self.dragBeginConnection: ", self.dragBeginConnection )
		if (self.dragBeginConnection != None):
			#todo: check what a connect signal becomes after it is disconnected
			if (self.dragBeginConnection != -1):
				self.disconnect(self.dragBeginConnection)
				self.disconnect(self.dragDataGetConnection)
				self.disconnect(self.dragEndConnection)
				#print( "2 self.dragBeginConnection: ", self.dragBeginConnection )
				self.dragBeginConnection = None
				self.dragDataGetConnection = None
				self.dragEndConnection = None


	def _buttonClickCb(self, args ):
		print("buttonClickCb 1")
		if (self.tc.recd == None):
			print("buttonClickCb 2")
			return
		if (not self.props.sensitive):
			print("buttonClickCb 3")
			return
		print("buttonClickCb 4")
		self.ui.showThumbSelection( self.tc.recd )
		print("buttonClickCb 5")


	def _exposeEventCb(self, widget, event):
		ctx = widget.window.cairo_create()
		self.draw( ctx, self.allocation.width, self.allocation.height )
		return True


	def _dragEndCb(self, widget, dragCtxt):
		self.ui.doClipboardCopyFinish( self.tempImgPath )


	def _dragBeginCb(self, widget, dragCtxt ):
		self.drag_source_set_icon_pixbuf( self.tc.thumbPixbuf )


	def _dragDataGetCb(self, widget, drag_context, selection_data, info, timestamp):
		#todo: is this the proper way to handle returning None if file deleted from another xo..?
		if (selection_data.target == 'image/jpeg'):
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

			elif (self.tc.recd.type == self.ui.ca.m.TYPE_VIDEO):
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
		self.audButt.set_tooltip("Video")
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