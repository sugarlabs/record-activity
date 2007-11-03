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
import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import math
import shutil
import time
import pango

from sugar.graphics.toolcombobox import ToolComboBox
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.tray import HTray
from sugar import profile
from sugar import util
from sugar.activity import activity

from instance import Instance
from constants import Constants
from color import Color
from p5 import P5
from p5_button import P5Button
from p5_button import Polygon
from p5_button import Button
from glive import LiveVideoWindow
from gplay import PlayVideoWindow
from recorded import Recorded
from button import RecdButton
import utils
import record
import _camera

class UI:

	dim_THUMB_WIDTH = 107
	dim_THUMB_HEIGHT = 78
	dim_INSET = 10
	dim_PIPW = 160
	dim_PIPH = 120 #pipBorder
	dim_PIP_BORDER = 4
	dim_PGDW = dim_PIPW + (dim_PIP_BORDER*2)
	dim_PGDH = dim_PIPH + (dim_PIP_BORDER*2)
	dim_CONTROLBAR_HT = 55

	def __init__( self, pca ):
		self.ca = pca

		self.inset = self.__class__.dim_INSET
		self.pgdh = self.__class__.dim_PGDH
		self.pgdw = self.__class__.dim_PGDW
		self.thumbTrayHt = 150 #todo: get sugar constant here
		self.thumbSvgW = 124
		self.thumbSvgH = 124
		self.maxw = 49
		self.maxh = 49
		self.controlBarHt = 55
		self.recordButtWd = 55
		self.pipw = self.__class__.dim_PIPW
		self.piph = self.__class__.dim_PIPH

		#ui modes
		self.FULLSCREEN = False
		self.LIVEMODE = True

		self.LAST_MODE = -1
		self.LAST_FULLSCREEN = False
		self.LAST_LIVE = True
		self.LAST_MESHING = False
		self.LAST_RECD_INFO = False
		self.LAST_TRANSCODING = False
		self.TRANSCODING = False
		self.MESHING = False
		self.RECD_INFO_ON = False
		self.UPDATE_DURATION_ID = 0
		self.UPDATE_TIMER_ID = 0

		#init
		self.mapped = False
		self.centered = False
		self.setup = False

		#prep for when to show
		self.shownRecd = None

		self.setUpWindows()

		#this includes the default sharing tab
		self.toolbox = activity.ActivityToolbox(self.ca)
		self.ca.set_toolbox(self.toolbox)
		self.photoToolbar = PhotoToolbar()
		self.photoToolbar.set_sensitive( False )
		self.toolbox.add_toolbar( Constants.istrPhoto, self.photoToolbar )
		self.videoToolbar = VideoToolbar()
		self.videoToolbar.set_sensitive( False )
		self.toolbox.add_toolbar( Constants.istrVideo, self.videoToolbar )
		self.audioToolbar = AudioToolbar()
		self.audioToolbar.set_sensitive( False )
		self.toolbox.add_toolbar( Constants.istrAudio, self.audioToolbar )
		self.tbars = {Constants.MODE_PHOTO:self.photoToolbar,Constants.MODE_VIDEO:self.videoToolbar,Constants.MODE_AUDIO:self.audioToolbar}
		self.toolbox.set_current_toolbar(self.ca.m.MODE+1)
		self.toolbox.connect("current-toolbar-changed", self._toolbarChangeCb)
		self.TOOLBOX_SIZE_ALLOCATE_ID = self.toolbox.connect_after("size-allocate", self._toolboxSizeAllocateCb)
		self.toolbox.show()


	def _toolboxSizeAllocateCb( self, widget, event ):
		self.toolbox.disconnect( self.TOOLBOX_SIZE_ALLOCATE_ID)

		toolboxHt = self.toolbox.size_request()[1]
		self.vh = gtk.gdk.screen_height()-(self.thumbTrayHt+toolboxHt+self.controlBarHt)
		self.vw = int(self.vh/.75)
		self.letterBoxW = (gtk.gdk.screen_width() - self.vw)/2
		self.letterBoxVW = (self.vw/2)-(self.inset*2)
		self.letterBoxVH = int(self.letterBoxVW*.75)

		#now that we know how big the toolbox is, we can layout more
		gobject.idle_add( self.layout )


	def layout( self ):
		self.mainBox = gtk.VBox()
		self.ca.set_canvas(self.mainBox)

		topBox = gtk.HBox()
		self.mainBox.pack_start(topBox, expand=True)

		leftFill = gtk.VBox()
		leftFill.set_size_request( self.letterBoxW, -1 )
		self.leftFillBox = gtk.EventBox( )
		self.leftFillBox.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		leftFill.add( self.leftFillBox )

		topBox.pack_start( leftFill, expand=True )

		centerVBox = gtk.VBox()
		centerVBox.modify_bg(gtk.STATE_NORMAL, Constants.colorBlack.gColor)
		topBox.pack_start( centerVBox, expand=True )
		self.centerBox = gtk.EventBox()
		self.centerBox.set_size_request(self.vw, -1)
		self.centerBox.modify_bg(gtk.STATE_NORMAL, Constants.colorBlack.gColor)
		centerVBox.pack_start( self.centerBox, expand=True )
		centerSizer = gtk.VBox()
		centerSizer.set_size_request(self.vw, -1)
		centerSizer.modify_bg(gtk.STATE_NORMAL, Constants.colorBlack.gColor)
		self.centerBox.add(centerSizer)

		self.bottomCenter = gtk.EventBox()
		self.bottomCenter.modify_bg(gtk.STATE_NORMAL, Constants.colorBlack.gColor)
		self.bottomCenter.set_size_request(self.vw, self.controlBarHt)
		centerVBox.pack_start( self.bottomCenter, expand=False )

		#into the center box we can put this guy...
		self.backgdCanvasBox = gtk.VBox()
		self.backgdCanvasBox.modify_bg(gtk.STATE_NORMAL, Constants.colorBlack.gColor)
		self.backgdCanvasBox.set_size_request(self.vw, -1)
		self.backgdCanvas = PhotoCanvas()
		self.backgdCanvas.set_size_request(self.vw, self.vh)
		self.backgdCanvasBox.pack_start( self.backgdCanvas, expand=False )

		#or this guy...
		self.infoBox = gtk.EventBox()
		self.infoBox.modify_bg( gtk.STATE_NORMAL, Constants.colorButton.gColor )
		iinfoBox = gtk.VBox(spacing=self.inset)
		self.infoBox.add( iinfoBox )
		iinfoBox.set_size_request(self.vw, -1)
		iinfoBox.set_border_width(self.inset)

		rightFill = gtk.VBox()
		rightFill.set_size_request( self.letterBoxW, -1 )
		rightFillBox = gtk.EventBox()
		rightFillBox.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		rightFill.add( rightFillBox )
		topBox.pack_start( rightFill, expand=True )

		#info box innards:
		self.infoBoxTop = gtk.HBox()
		iinfoBox.pack_start( self.infoBoxTop, expand=True )
		self.infoBoxTopLeft = gtk.VBox(spacing=self.inset)
		self.infoBoxTop.pack_start( self.infoBoxTopLeft )
		self.infoBoxTopRight = gtk.VBox()
		self.infoBoxTopRight.set_size_request(self.letterBoxVW, -1)
		self.infoBoxTop.pack_start( self.infoBoxTopRight )

		self.namePanel = gtk.HBox()
		leftInfBalance = gtk.VBox()
		self.nameLabel = gtk.Label("<b><span foreground='white'>"+Constants.istrTitle+"</span></b>")
		self.nameLabel.set_use_markup( True )
		self.namePanel.pack_start( self.nameLabel, expand=False, padding=self.inset )
		self.nameLabel.set_alignment(0, .5)
		self.nameTextfield = gtk.Entry(140)
		self.nameTextfield.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorBlack.gColor )
		self.nameTextfield.connect('changed', self._nameTextfieldEditedCb )
		self.nameTextfield.set_alignment(0)
		self.nameTextfield.set_size_request( -1, 39 ) #self.controlBarHt-self.inset ) #todo: dynamic
		self.namePanel.pack_start(self.nameTextfield)

		self.photographerPanel = gtk.VBox(spacing=self.inset)
		self.infoBoxTopLeft.pack_start(self.photographerPanel, expand=False)
		photographerLabel = gtk.Label("<b>" + Constants.istrRecorder + "</b>")
		photographerLabel.set_use_markup( True )
		self.photographerPanel.pack_start(photographerLabel, expand=False)
		photographerLabel.set_alignment(0, .5)
		photoNamePanel = gtk.HBox(spacing=self.inset)
		self.photographerPanel.pack_start(photoNamePanel)

		self.photoXoPanel = xoPanel()
		photoNamePanel.pack_start( self.photoXoPanel, expand=False )
		self.photoXoPanel.set_size_request( 40, 40 )

		self.photographerNameLabel = gtk.Label("")
		self.photographerNameLabel.set_alignment(0, .5)
		photoNamePanel.pack_start(self.photographerNameLabel)

		self.datePanel = gtk.HBox(spacing=self.inset)
		self.infoBoxTopLeft.pack_start(self.datePanel, expand=False)
		dateLabel = gtk.Label("<b>"+Constants.istrDate+"</b>")
		dateLabel.set_use_markup(True)
		self.datePanel.pack_start(dateLabel, expand=False)
		self.dateDateLabel = gtk.Label("")
		self.dateDateLabel.set_alignment(0, .5)
		self.datePanel.pack_start(self.dateDateLabel)

		self.tagsPanel = gtk.VBox(spacing=self.inset)
		tagsLabel = gtk.Label("<b>"+Constants.istrTags+"</b>")
		tagsLabel.set_use_markup(True)
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
		thumbnailsEventBox.set_size_request( -1, self.thumbTrayHt )
		thumbnailsBox = gtk.HBox( )
		thumbnailsEventBox.add( thumbnailsBox )

		self.thumbTray = HTray()
		self.thumbTray.set_size_request( -1, self.thumbTrayHt )
		self.mainBox.pack_end( self.thumbTray, expand=False )
		self.thumbTray.show()

		self.CENTER_SIZE_ALLOCATE_ID = self.centerBox.connect_after("size-allocate", self._centerSizeAllocateCb)
		self.ca.show_all()


	def _centerSizeAllocateCb( self, widget, event ):
		#initial setup of the panels
		self.centerBox.disconnect(self.CENTER_SIZE_ALLOCATE_ID)
		self.centerBoxPos = self.centerBox.translate_coordinates( self.ca, 0, 0 )

		centerKid = self.centerBox.get_child()
		if (centerKid != None):
			self.centerBox.remove( centerKid )

		self.centered = True
		self.setUp()


	def _mapEventCb( self, widget, event ):
		#when your parent window is ready, turn on the feed of live video
		self.liveVideoWindow.disconnect(self.MAP_EVENT_ID)
		self.mapped = True
		self.setUp()


	def setUp( self ):
		if (self.mapped and self.centered and not self.setup):
			self.setup = True

			#set correct window sizes
			self.setUpWindowsSizes()

			#listen for ctrl+c & game key buttons
			self.ca.connect('key-press-event', self._keyPressEventCb)
			#overlay widgets can go away after they've been on screen for a while
			self.HIDE_WIDGET_TIMEOUT_ID = 0
			self.hiddenWidgets = False
			self.resetWidgetFadeTimer()
			self.showLiveVideoTags()

			self.recordWindow.shutterButton.set_sensitive(True)

			self.photoToolbar.set_sensitive( True )
			self.videoToolbar.set_sensitive( True )
			self.audioToolbar.set_sensitive( True )

			#initialize the app with the default thumbs
			self.ca.m.setupMode( self.ca.m.MODE, False )

			gobject.idle_add( self.finalSetUp )


	def finalSetUp( self ):
		self.updateVideoComponents()
		self.ca.glive.play()


	def setUpWindows( self ):
		#image windows
		self.windowStack = []

		#live video windows
		self.livePhotoWindow = gtk.Window()
		self.livePhotoWindow.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.livePhotoWindow.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorBlack.gColor )
		self.addToWindowStack( self.livePhotoWindow, self.ca )
		self.livePhotoCanvas = PhotoCanvas()
		self.livePhotoWindow.add(self.livePhotoCanvas)
		self.livePhotoWindow.connect("button_release_event", self._mediaClickedForPlayback)

		#border behind
		self.pipBgdWindow = gtk.Window()
		self.pipBgdWindow.modify_bg( gtk.STATE_NORMAL, Constants.colorWhite.gColor )
		self.pipBgdWindow.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorWhite.gColor )
		self.addToWindowStack( self.pipBgdWindow, self.windowStack[len(self.windowStack)-1] )

		self.liveVideoWindow = LiveVideoWindow(Constants.colorBlack.gColor)
		self.addToWindowStack( self.liveVideoWindow, self.windowStack[len(self.windowStack)-1] )
		self.liveVideoWindow.set_glive(self.ca.glive)
		self.liveVideoWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.liveVideoWindow.connect("button_release_event", self._liveButtonReleaseCb)

		#video playback windows
		self.playOggWindow = PlayVideoWindow(Constants.colorBlack.gColor)
		self.addToWindowStack( self.playOggWindow, self.windowStack[len(self.windowStack)-1] )
		#self.playOggWindow.set_gplay(self.ca.gplay)
		self.ca.gplay.window = self.playOggWindow
		self.playOggWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.playOggWindow.connect("button_release_event", self._mediaClickedForPlayback)

		#border behind
		self.pipBgdWindow2 = gtk.Window()
		self.pipBgdWindow2.modify_bg( gtk.STATE_NORMAL, Constants.colorWhite.gColor )
		self.pipBgdWindow2.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorWhite.gColor )
		self.addToWindowStack( self.pipBgdWindow2, self.windowStack[len(self.windowStack)-1] )

		self.playLiveWindow = LiveVideoWindow(Constants.colorBlack.gColor)
		self.addToWindowStack( self.playLiveWindow, self.windowStack[len(self.windowStack)-1] )
		self.playLiveWindow.set_events(gtk.gdk.BUTTON_RELEASE_MASK)
		self.playLiveWindow.connect("button_release_event", self._playLiveButtonReleaseCb)

		self.recordWindow = RecordWindow(self)
		self.addToWindowStack( self.recordWindow, self.windowStack[len(self.windowStack)-1] )

		self.progressWindow = ProgressWindow(self)
		self.addToWindowStack( self.progressWindow, self.windowStack[len(self.windowStack)-1] )

		self.maxWindow = gtk.Window()
		maxButton = MaxButton(self)
		self.maxWindow.add( maxButton )
		self.addToWindowStack( self.maxWindow, self.windowStack[len(self.windowStack)-1] )

		self.scrubWindow = ScrubberWindow(self)
		self.addToWindowStack( self.scrubWindow, self.windowStack[len(self.windowStack)-1] )

		self.infWindow = gtk.Window()
		self.infWindow.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.infWindow.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorBlack.gColor )
		infButton= InfButton(self)
		self.infWindow.add(infButton)
		self.addToWindowStack( self.infWindow, self.windowStack[len(self.windowStack)-1] )

		self.hideAllWindows()

		self.MAP_EVENT_ID = self.liveVideoWindow.connect_after("map-event", self._mapEventCb)

		for i in range (0, len(self.windowStack)):
			self.windowStack[i].show_all()


	def setUpWindowsSizes( self ):
		pipDim = self.getPipDim(False)
		eyeDim = self.getEyeDim(False)
		imgDim = self.getImgDim( False )
		pgdDim = self.getPgdDim( False )
		maxDim = self.getMaxDim( False )
		prgDim = self.getPrgDim( False )
		infDim = self.getInfDim( False )
		self.livePhotoWindow.resize( imgDim[0], imgDim[1] )
		self.pipBgdWindow.resize( pgdDim[0], pgdDim[1] )
		self.liveVideoWindow.resize( imgDim[0], imgDim[1] )
		self.playOggWindow.resize( imgDim[0], imgDim[1] )
		self.playLiveWindow.resize( imgDim[0], imgDim[1] )
		self.pipBgdWindow2.resize( pgdDim[0], pgdDim[1] )
		self.recordWindow.resize( eyeDim[0], eyeDim[1] )
		self.maxWindow.resize( maxDim[0], maxDim[1] )
		self.progressWindow.resize( prgDim[0], prgDim[1] )
		self.infWindow.resize( infDim[0], infDim[1] )


	def _toolbarChangeCb( self, tbox, num ):
		if (num != 0) and (self.ca.m.RECORDING or self.ca.m.UPDATING):
			self.toolbox.set_current_toolbar( self.ca.m.MODE+1 )
		else:
			num = num - 1 #offset the default activity tab
			if (num == Constants.MODE_PHOTO) and (self.ca.m.MODE != Constants.MODE_PHOTO):
				self.ca.m.doPhotoMode()
			elif(num == Constants.MODE_VIDEO) and (self.ca.m.MODE != Constants.MODE_VIDEO):
				self.ca.m.doVideoMode()
			elif(num == Constants.MODE_AUDIO) and (self.ca.m.MODE != Constants.MODE_AUDIO):
				self.ca.m.doAudioMode()


	def addToWindowStack( self, win, parent ):
		self.windowStack.append( win )
		win.set_transient_for( parent )
		win.set_type_hint( gtk.gdk.WINDOW_TYPE_HINT_DIALOG )
		win.set_decorated( False )
		win.set_focus_on_map( False )
		win.set_property("accept-focus", False)


	def resetWidgetFadeTimer( self ):
		#only show the clutter when the mouse moves
		self.mx = -1
		self.my = -1
		self.hideWidgetsTimer = time.time()
		if (self.hiddenWidgets):
			self.showWidgets()
			self.hiddenWidgets = False

		#remove, then add
		self.doMouseListener( False )
		if (self.HIDE_WIDGET_TIMEOUT_ID != 0):
			gobject.source_remove( self.HIDE_WIDGET_TIMEOUT_ID)

		self.HIDE_WIDGET_TIMEOUT_ID = gobject.timeout_add( 500, self._mouseMightaMovedCb )


	def doMouseListener( self, listen ):
		if (listen):
			self.resetWidgetFadeTimer()
		else:
			if (self.HIDE_WIDGET_TIMEOUT_ID != None):
				if (self.HIDE_WIDGET_TIMEOUT_ID != 0):
					gobject.source_remove( self.HIDE_WIDGET_TIMEOUT_ID )


	def hideWidgets( self ):
		self.moveWinOffscreen( self.maxWindow )
		self.moveWinOffscreen( self.pipBgdWindow )
		self.moveWinOffscreen( self.pipBgdWindow2 )
		self.moveWinOffscreen( self.infWindow )

		if (self.FULLSCREEN):
			self.moveWinOffscreen( self.recordWindow )
			self.moveWinOffscreen( self.progressWindow )
			self.moveWinOffscreen( self.scrubWindow )

		if (self.ca.m.MODE == Constants.MODE_PHOTO):
			if (not self.LIVEMODE):
				self.moveWinOffscreen( self.liveVideoWindow )
		elif (self.ca.m.MODE == Constants.MODE_VIDEO):
			if (not self.LIVEMODE):
				self.moveWinOffscreen( self.playLiveWindow )
		elif (self.ca.m.MODE == Constants.MODE_AUDIO):
			if (not self.LIVEMODE):
				self.moveWinOffscreen( self.liveVideoWindow )
		self.LAST_MODE = -1


	def _mouseMightaMovedCb( self ):
		x, y = self.ca.get_pointer()
		passedTime = 0

		if (x != self.mx or y != self.my):
			self.hideWidgetsTimer = time.time()
			if (self.hiddenWidgets):
				self.showWidgets()
				self.hiddenWidgets = False
		else:
			passedTime = time.time() - self.hideWidgetsTimer

		if (self.ca.m.RECORDING):
			self.hideWidgetsTimer = time.time()
			passedTime = 0

		if (passedTime >= 3):
			if (not self.hiddenWidgets):
				if (self.mouseInWidget(x,y)):
					self.hideWidgetsTimer = time.time()
				elif (self.RECD_INFO_ON):
					self.hideWidgetsTimer = time.time()
				elif (self.UPDATE_TIMER_ID != 0):
					self.hideWidgetsTimer = time.time()
				else:
					self.hideWidgets()
					self.hiddenWidgets = True

		self.mx = x
		self.my = y
		return True


	def mouseInWidget( self, mx, my ):
		if (self.ca.m.MODE != Constants.MODE_AUDIO):
			if (self.inWidget( mx, my, self.getLoc("max", self.FULLSCREEN), self.getDim("max", self.FULLSCREEN))):
				return True

		if (not self.LIVEMODE):
			if (self.inWidget( mx, my, self.getLoc("pgd", self.FULLSCREEN), self.getDim("pgd", self.FULLSCREEN))):
				return True

			if (self.inWidget( mx, my, self.getLoc("inb", self.FULLSCREEN), self.getDim("inb", self.FULLSCREEN))):
				return True

			if (self.inWidget( mx, my, self.getLoc("prg", self.FULLSCREEN), self.getDim("prg", self.FULLSCREEN))):
				return True

			if (self.inWidget( mx, my, self.getLoc("inf", self.FULLSCREEN), self.getDim("inf", self.FULLSCREEN))):
				return True

		if (self.LIVEMODE):
			if (self.inWidget( mx, my, self.getLoc("eye", self.FULLSCREEN), self.getDim("eye", self.FULLSCREEN))):
				return True

		return False


	def _mediaClickedForPlayback(self, widget, event):
		if (not self.LIVEMODE):
			if (self.shownRecd != None):
				if (self.ca.m.MODE != Constants.MODE_PHOTO):
					self.showThumbSelection( self.shownRecd )


	def inWidget( self, mx, my, loc, dim ):
		if (	(mx > loc[0]) and (my > loc[1])	):
			if (	(mx < loc[0]+dim[0]) and (my < loc[1]+dim[1])	):
				return True


	def _nameTextfieldEditedCb(self, widget):
		if (self.shownRecd != None):
			if (self.nameTextfield.get_text() != self.shownRecd.title):
				self.shownRecd.setTitle( self.nameTextfield.get_text() )


	def _keyPressEventCb( self, widget, event):
		#todo: trac #4144

		self.resetWidgetFadeTimer()

		#we listen here for CTRL+C events and game keys, and pass on events to gtk.Entry fields
		keyname = gtk.gdk.keyval_name(event.keyval)
		if (keyname == 'KP_Page_Up'): #O, up
			print("GAME UP")
			if (self.LIVEMODE):
				if (self.RECD_INFO_ON):
					self.infoButtonClicked()
					return
				if (not self.ca.m.UPDATING):
					self.doShutter()
			else:
				if (self.ca.m.MODE == Constants.MODE_PHOTO):
					self.resumeLiveVideo()
				else:
					self.resumePlayLiveVideo()
		elif (keyname == 'KP_Page_Down'): #x, down
			print("GAME X")
			self.ca.m.showLastThumb()
		elif (keyname == 'KP_Home'): #square, left
			print("GAME LEFT")
			if (not self.LIVEMODE):
				self.ca.m.showPrevThumb( self.shownRecd )
		elif (keyname == 'KP_End'): #check, right
			print("GAME RIGHT")
			if (not self.LIVEMODE):
				self.ca.m.showNextThumb( self.shownRecd )
		elif (keyname == 'c' and event.state == gtk.gdk.CONTROL_MASK):
			if (self.shownRecd != None):
				self.copyToClipboard( self.shownRecd )
		elif (keyname == 'Escape'):
			if (self.FULLSCREEN):
				self.FULLSCREEN = False
				if (self.RECD_INFO_ON):
					self.infoButtonClicked()
				else:
					self.updateVideoComponents()
		elif (keyname == 'i' and event.state == gtk.gdk.CONTROL_MASK):
			if (not self.LIVEMODE):
				self.infoButtonClicked()

		return False


	def copyToClipboard( self, recd ):
		if (recd.isClipboardCopyable( )):
			tmpImgPath = self.doClipboardCopyStart( recd )
			gtk.Clipboard().set_with_data( [('text/uri-list', 0, 0)], self._clipboardGetFuncCb, self._clipboardClearFuncCb, tmpImgPath )
			return True


	def doClipboardCopyStart( self, recd ):
		imgPath_s = recd.getMediaFilepath()
		if (imgPath_s == None):
			record.Record.log.error("doClipboardCopyStart: imgPath_s==None")
			return None

		tmpImgPath = os.path.join( Instance.tmpPath, recd.mediaFilename)
		tmpImgPath = utils.getUniqueFilepath(tmpImgPath,0)
		shutil.copyfile( imgPath_s, tmpImgPath )
		return tmpImgPath


	def doClipboardCopyCopy( self, tmpImgPath, selection_data ):
		tmpImgUri = "file://" + tmpImgPath
		selection_data.set( "text/uri-list", 8, tmpImgUri )


	def doClipboardCopyFinish( self, tmpImgPath ):
		if (tmpImgPath != None):
			if (os.path.exists(tmpImgPath)):
				os.remove( tmpImgPath )
		tmpImgPath = None


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

			self.LIVEMODE = False
			self.updateVideoComponents()

			self.showRecdMeta(recd)


	def getPhotoPixbuf( self, recd ):
		pixbuf = None

		downloading = self.ca.requestMeshDownload(recd)
		self.MESHING = downloading

		if (not downloading):
			imgPath = recd.getMediaFilepath()
			if (not imgPath == None):
				if ( os.path.isfile(imgPath) ):
					pixbuf = gtk.gdk.pixbuf_new_from_file(imgPath)

		if (pixbuf == None):
			#maybe it is not downloaded from the mesh yet...
			#but we can show the low res thumb in the interim
			pixbuf = recd.getThumbPixbuf()

		return pixbuf


	def showLiveVideoTags( self ):
		self.shownRecd = None
		self.livePhotoCanvas.setImage( None )
		self.nameTextfield.set_text("")
		self.tagsBuffer.set_text("")

		self.scrubWindow.removeCallbacks()
		self.scrubWindow.reset()
		self.MESHING = False

		self.resetWidgetFadeTimer( )


	def updateButtonSensitivities( self ):
		self.recordWindow.shutterButton.set_sensitive( not self.ca.m.UPDATING )

		switchStuff = ((not self.ca.m.UPDATING) and (not self.ca.m.RECORDING))
		self.photoToolbar.set_sensitive( switchStuff )
		self.videoToolbar.set_sensitive( switchStuff )
		self.audioToolbar.set_sensitive( switchStuff )

		if (self.ca.m.UPDATING):
			self.ca.ui.setWaitCursor( self.ca.window )
			for i in range (0, len(self.windowStack)):
				self.ca.ui.setWaitCursor( self.windowStack[i].window )
		else:
			self.ca.ui.setDefaultCursor( self.ca.window )
			for i in range (0, len(self.windowStack)):
				self.ca.ui.setDefaultCursor( self.windowStack[i].window )

		if (self.ca.m.RECORDING):
			#self.recordWindow.shutterButton.modify_bg( gtk.STATE_NORMAL, Constants.colorRed.gColor )
			self.recordWindow.shutterButton.doRecordButton()
		else:
			#self.recordWindow.shutterButton.modify_bg( gtk.STATE_NORMAL, None )
			self.recordWindow.shutterButton.doNormalButton()


	def hideAllWindows( self ):
		for i in range (0, len(self.windowStack)):
			self.moveWinOffscreen( self.windowStack[i] )


	def _liveButtonReleaseCb(self, widget, event):
		self.resumeLiveVideo()


	def resumeLiveVideo( self ):
		self.livePhotoCanvas.setImage( None )

		bottomKid = self.bottomCenter.get_child()
		if (bottomKid != None):
			self.bottomCenter.remove( bottomKid )

		self.RECD_INFO_ON = False

		if (not self.LIVEMODE):
			self.ca.m.setUpdating(True)
			self.ca.gplay.stop()
			self.showLiveVideoTags()
			self.LIVEMODE = True
			self.updateVideoComponents()
			self.ca.m.setUpdating(False)


	def _playLiveButtonReleaseCb(self, widget, event):
		self.resumePlayLiveVideo()


	def resumePlayLiveVideo( self ):
		self.ca.gplay.stop()

		self.RECD_INFO_ON = False
		#if you are big on the screen, don't go changing anything, ok?
		if (self.LIVEMODE):
			return

		self.showLiveVideoTags()
		self.LIVEMODE = True
		self.startLiveVideo( self.playLiveWindow, self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, False )
		self.updateVideoComponents()


	def recordVideo( self ):
		self.ca.glive.startRecordingVideo( )
		self.beginRecordingTimer( )


	def recordAudio( self ):
		self.ca.glive.startRecordingAudio( )
		self.beginRecordingTimer( )


	def beginRecordingTimer( self ):
		self.recTime = time.time()
		self.UPDATE_DURATION_ID = gobject.timeout_add( 500, self._updateDurationCb )


	def _updateDurationCb( self ):
		passedTime = time.time() - self.recTime

		duration = 10.0
		if (self.ca.m.MODE == Constants.MODE_VIDEO):
			duration = self.videoToolbar.getDuration()+0.0
		elif (self.ca.m.MODE == Constants.MODE_AUDIO):
			duration = self.audioToolbar.getDuration()+0.0

		if (passedTime >= duration ):
			gobject.source_remove( self.UPDATE_DURATION_ID )
			self.progressWindow.updateProgress( 1, Constants.istrFinishedRecording )
			if (self.ca.m.RECORDING):
				gobject.idle_add( self.doShutter )

			return False
		else:
			secsRemaining = duration - passedTime
			self.progressWindow.updateProgress( passedTime/duration, Constants.istrDuration + " " + Constants.istrSecondsRemaining % {"1":str(int(secsRemaining))} )
			return True


	def updateModeChange(self):
		#this is called when a menubar button is clicked
		self.LIVEMODE = True
		self.FULLSCREEN = False
		self.RECD_INFO_ON = False
		self.MESHING = False

		self.progressWindow.updateProgress(0.0, "")

		#set up the x & xv x-ition (if need be)
		self.ca.gplay.stop()
		if (self.ca.m.MODE == Constants.MODE_PHOTO):
			self.startLiveVideo( self.liveVideoWindow, self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, True )
		elif (self.ca.m.MODE == Constants.MODE_VIDEO):
			self.startLiveVideo( self.playLiveWindow,  self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, True )
		elif (self.ca.m.MODE == Constants.MODE_AUDIO):
			self.startLiveVideo( self.liveVideoWindow,  self.ca.glive.PIPETYPE_AUDIO_RECORD, True )

		bottomKid = self.bottomCenter.get_child()
		if (bottomKid != None):
			self.bottomCenter.remove( bottomKid )

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
			and self.ca.props.active
			and not force):
			return

		self.ca.glive.setPipeType( pipetype )
		window.set_glive(self.ca.glive)
		self.ca.glive.stop()
		self.ca.glive.play()


	def doFullscreen( self ):
		self.FULLSCREEN = not self.FULLSCREEN
		self.updateVideoComponents()


	def moveWinOffscreen( self, win ):
		#we move offscreen to resize or else we get flashes on screen, and setting hide() doesn't allow resize & moves
		offW = (gtk.gdk.screen_width() + 100)
		offH = (gtk.gdk.screen_height() + 100)
		self.smartMove(win, offW, offH)


	def setImgLocDim( self, win ):
		imgDim = self.getImgDim( self.FULLSCREEN )
		self.smartResize( win, imgDim[0], imgDim[1] )
		imgLoc = self.getImgLoc( self.FULLSCREEN )
		self.smartMove( win, imgLoc[0], imgLoc[1] )


	def setPrgLocDim( self, win ):
		prgDim = self.getPrgDim( self.FULLSCREEN )
		self.smartResize( win, prgDim[0], prgDim[1] )
		prgLoc = self.getPrgLoc( self.FULLSCREEN )
		self.smartMove( win, prgLoc[0], prgLoc[1] )


	def setTmrLocDim( self, win ):
		tmrDim = self.getTmrDim( self.FULLSCREEN )
		self.smartResize( win, tmrDim[0], tmrDim[1] )
		tmrLoc = self.getTmrLoc( self.FULLSCREEN )
		self.smartMove( win, tmrLoc[0], tmrLoc[1] )


	def setScrLocDim( self, win ):
		scrDim = self.getScrDim( self.FULLSCREEN )
		self.smartResize( win, scrDim[0], scrDim[1] )
		scrLoc = self.getScrLoc( self.FULLSCREEN )
		self.smartMove( win, scrLoc[0], scrLoc[1] )


	def setInfLocDim( self, win ):
		infDim = self.getInfDim( self.FULLSCREEN )
		self.smartResize( win, infDim[0], infDim[1] )
		infLoc = self.getInfLoc( self.FULLSCREEN )
		self.smartMove( win, infLoc[0], infLoc[1] )


	def getScrDim( self, full ):
		if (full):
			return [gtk.gdk.screen_width()-(self.inset+self.pgdw+self.inset+self.inset), self.controlBarHt]
		else:
			return [self.vw, self.controlBarHt]


	def getScrLoc( self, full ):
		if (full):
			return [(self.inset+self.pgdw+self.inset), gtk.gdk.screen_height()-(self.inset+self.controlBarHt)]
		else:
			return [self.centerBoxPos[0], self.centerBoxPos[1]+self.vh]


	def getImgDim( self, full ):
		if (full):
			return [gtk.gdk.screen_width(), gtk.gdk.screen_height()]
		else:
			return [self.vw, self.vh]


	def getImgLoc( self, full ):
		if (full):
			return[0, 0]
		else:
			return[self.centerBoxPos[0], self.centerBoxPos[1]]


	def getTmrLoc( self, full ):
		if (not full):
			return [self.centerBoxPos[0], self.centerBoxPos[1]+self.vh]
		else:
			return [self.inset, gtk.gdk.screen_height()-(self.inset+self.controlBarHt)]


	def getTmrDim( self, full ):
		if (not full):
			return [self.vw, self.controlBarHt]
		else:
			return [gtk.gdk.screen_width()-(self.inset+self.inset), self.controlBarHt]


	def setPipLocDim( self, win ):
		self.smartResize( win, self.pipw, self.piph )

		loc = self.getPipLoc( self.FULLSCREEN )
		self.smartMove( win, loc[0], loc[1] )


	def getPipLoc( self, full ):
		if (full):
			return [self.inset+self.__class__.dim_PIP_BORDER, gtk.gdk.screen_height()-(self.inset+self.piph+self.__class__.dim_PIP_BORDER)]
		else:
			return [self.centerBoxPos[0]+self.inset+self.__class__.dim_PIP_BORDER, (self.centerBoxPos[1]+self.vh)-(self.inset+self.piph+self.__class__.dim_PIP_BORDER)]


	def setPipBgdLocDim( self, win ):
		pgdLoc = self.getPgdLoc( self.FULLSCREEN )
		self.smartMove( win, pgdLoc[0], pgdLoc[1] )


	def getPgdLoc( self, full ):
		if (full):
			return [self.inset, gtk.gdk.screen_height()-(self.inset+self.pgdh)]
		else:
			return [self.centerBoxPos[0]+self.inset, (self.centerBoxPos[1]+self.vh)-(self.inset+self.pgdh)]


	def setMaxLocDim( self, win ):
		maxLoc = self.getMaxLoc( self.FULLSCREEN )
		self.smartMove( win, maxLoc[0], maxLoc[1] )


	def getMaxLoc( self, full ):
		if (full):
			return [gtk.gdk.screen_width()-(self.maxw+self.inset), self.inset]
		else:
			return [(self.centerBoxPos[0]+self.vw)-(self.inset+self.maxw), self.centerBoxPos[1]+self.inset]


	def getInfLoc( self, full ):
		if (full):
			return [gtk.gdk.screen_width()+100,gtk.gdk.screen_height()+100 ]
		else:
			dim = self.getInfDim(self.FULLSCREEN)
			return [(self.centerBoxPos[0]+self.vw)-dim[0], (self.centerBoxPos[1]+self.vh)-dim[1]]


	def setEyeLocDim( self, win ):
		dim = self.getEyeDim( self.FULLSCREEN )
		self.smartResize( win, dim[0], dim[1] )
		loc = self.getEyeLoc( self.FULLSCREEN )
		self.smartMove( win, loc[0], loc[1] )


	def getEyeLoc( self, full ):
		if (not full):
			if (self.ca.m.MODE != Constants.MODE_PHOTO):
				return [self.centerBoxPos[0], self.centerBoxPos[1]+self.vh]
			else:
				return [(self.centerBoxPos[0]+(self.vw/2))-self.recordButtWd/2, self.centerBoxPos[1]+self.vh]
		else:
			return [self.inset, gtk.gdk.screen_height()-(self.inset+self.controlBarHt)]


	def getEyeDim( self, full ):
		if (not full):
			return [self.recordButtWd, self.controlBarHt]
		else:
			if (self.ca.m.MODE == Constants.MODE_PHOTO):
				return [gtk.gdk.screen_width()-(self.inset*2), self.controlBarHt]
			else:
				return [self.recordButtWd, self.controlBarHt]


	def getInbLoc( self, full ):
		return [(self.centerBoxPos[0]+self.vw)-(self.inset+self.letterBoxVW), self.centerBoxPos[1]+self.inset]


	def setInbLocDim( self, win ):
		dim = self.getInbDim( self.FULLSCREEN )
		self.smartResize( win, dim[0], dim[1] )
		loc = self.getInbLoc(self.FULLSCREEN)
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


	def getDim( self, pos, full ):
		if (pos == "pip"):
			return self.getPipDim( full )
		elif(pos == "pgd"):
			return self.getPgdDim( full )
		elif(pos == "max"):
			return self.getMaxDim( full )
		elif(pos == "img"):
			return self.getImgDim( full )
		elif(pos == "eye"):
			return self.getEyeDim( full )
		elif(pos == "inb"):
			return self.getInbDim( full )
		elif(pos == "prg"):
			return self.getPrgDim( full )
		elif(pos == "inf"):
			return self.getInfDim( full )


	def getMaxDim( self, full ):
		return [self.maxw, self.maxh]


	def getInfDim( self, full ):
		return [75, 75]


	def getPipDim( self, full ):
		return [self.pipw, self.piph]


	def getPgdDim( self, full ):
		return [self.pgdw, self.pgdh]


	def getInbDim( self, full ):
		return [self.letterBoxVW, self.letterBoxVH]


	def getPrgDim( self, full ):
		if (not full):
			return [self.vw-self.recordButtWd, self.controlBarHt]
		else:
			return [gtk.gdk.screen_width()-(self.inset+self.inset+self.recordButtWd), self.controlBarHt]


	def getPrgLoc( self, full ):
		if (not full):
			return [self.centerBoxPos[0]+self.recordButtWd, self.centerBoxPos[1]+self.vh]
		else:
			return [self.inset+self.recordButtWd, gtk.gdk.screen_height()-(self.inset+self.controlBarHt)]


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
		elif(pos == "inb"):
			return self.getInbLoc( full )
		elif(pos == "prg"):
			return self.getPrgLoc( full )
		elif(pos == "inf"):
			return self.getInfLoc( full )


	def _shutterClickCb( self, arg ):
		self.doShutter()


	def doShutter( self ):
		if (self.UPDATE_TIMER_ID == 0):
			if (not self.ca.m.RECORDING):
				#there is no update timer running, so we need to find out if there is a timer needed
				timerTime = 0
				if (self.ca.m.MODE == Constants.MODE_PHOTO):
					timerTime = self.photoToolbar.getTimer()
				elif (self.ca.m.MODE == Constants.MODE_VIDEO):
					timerTime = self.videoToolbar.getTimer()
				elif (self.ca.m.MODE == Constants.MODE_AUDIO):
					timerTime = self.audioToolbar.getTimer()

				if (timerTime > 0):
					self.timerStartTime = time.time()
					self.UPDATE_TIMER_ID = gobject.timeout_add( 500, self._updateTimerCb )
				else:
					self.clickShutter()
			else:
				#or, if there is no countdown, it might be because we are recording
				self.clickShutter()


		else:
			#we're timing down something, but interrupted by user click or the timer completing
			self._completeTimer()
			gobject.idle_add( self.clickShutter )


	def _completeTimer( self ):
		self.recordWindow.updateCountdown(-1)
		self.progressWindow.updateProgress( 1, "" )
		gobject.source_remove( self.UPDATE_TIMER_ID )
		self.UPDATE_TIMER_ID = 0


	def _updateTimerCb( self ):
		nowTime = time.time()
		passedTime = nowTime - self.timerStartTime

		timerTime = 0
		if (self.ca.m.MODE == Constants.MODE_PHOTO):
			timerTime = self.photoToolbar.getTimer()
		elif (self.ca.m.MODE == Constants.MODE_VIDEO):
			timerTime = self.videoToolbar.getTimer()
		elif (self.ca.m.MODE == Constants.MODE_AUDIO):
			timerTime = self.audioToolbar.getTimer()

		if (passedTime >= timerTime):
			self.doShutter()
			return False
		else:
			secsRemaining = timerTime-passedTime
			self.progressWindow.updateProgress( passedTime/timerTime, Constants.istrTimer + " " + Constants.istrSecondsRemaining % {"1":str(int(secsRemaining))} )
			self.recordWindow.updateCountdown( int(secsRemaining) )
			return True


	def clickShutter( self ):
		if (not self.ca.m.RECORDING):
			os.system( "aplay -t wav " + str(Constants.soundClick) )

		wasRec = self.ca.m.RECORDING
		self.ca.m.doShutter()
		if (wasRec):
			os.system( "aplay -t wav " + str(Constants.soundClick) )


	def updateVideoComponents( self ):
		if (	(self.LAST_MODE == self.ca.m.MODE)
				and (self.LAST_FULLSCREEN == self.FULLSCREEN)
				and (self.LAST_LIVE == self.LIVEMODE)
				and (self.LAST_RECD_INFO == self.RECD_INFO_ON)
				and (self.LAST_TRANSCODING == self.TRANSCODING)
				and (self.LAST_MESHING == self.MESHING)
			):
			return

		#something's changing so start counting anew
		self.resetWidgetFadeTimer()

		pos = []
		if (self.RECD_INFO_ON and not self.TRANSCODING):
			if (self.ca.m.MODE == Constants.MODE_PHOTO):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				pos.append({"position":"inb", "window":self.livePhotoWindow} )
				pos.append({"position":"inf", "window":self.infWindow} )
			elif (self.ca.m.MODE == Constants.MODE_VIDEO):
				pos.append({"position":"pgd", "window":self.pipBgdWindow2} )
				pos.append({"position":"pip", "window":self.playLiveWindow} )
				pos.append({"position":"inb", "window":self.playOggWindow} )
				pos.append({"position":"inf", "window":self.infWindow} )
			elif (self.ca.m.MODE == Constants.MODE_AUDIO):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				pos.append({"position":"inb", "window":self.livePhotoWindow} )
				pos.append({"position":"inf", "window":self.infWindow} )
		elif (not self.RECD_INFO_ON and not self.TRANSCODING):
			if (self.ca.m.MODE == Constants.MODE_PHOTO):
				if (self.LIVEMODE):
					pos.append({"position":"img", "window":self.liveVideoWindow} )
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"eye", "window":self.recordWindow} )
				else:
					pos.append({"position":"img", "window":self.livePhotoWindow} )
					pos.append({"position":"pgd", "window":self.pipBgdWindow} )
					pos.append({"position":"pip", "window":self.liveVideoWindow} )
					if (not self.MESHING):
						pos.append({"position":"max", "window":self.maxWindow} )
						pos.append({"position":"inf", "window":self.infWindow} )
					else:
						pos.append({"position":"tmr", "window":self.progressWindow} )
			elif (self.ca.m.MODE == Constants.MODE_VIDEO):
				if (self.LIVEMODE):
					pos.append({"position":"img", "window":self.playLiveWindow} )
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"eye", "window":self.recordWindow} )
					pos.append({"position":"prg", "window":self.progressWindow} )
				else:
					pos.append({"position":"img", "window":self.playOggWindow} )
					pos.append({"position":"pgd", "window":self.pipBgdWindow2} )
					pos.append({"position":"pip", "window":self.playLiveWindow} )
					if (not self.MESHING):
						pos.append({"position":"max", "window":self.maxWindow} )
						pos.append({"position":"scr", "window":self.scrubWindow} )
						pos.append({"position":"inf", "window":self.infWindow} )
					else:
						pos.append({"position":"tmr", "window":self.progressWindow} )
			elif (self.ca.m.MODE == Constants.MODE_AUDIO):
				if (self.LIVEMODE):
					pos.append({"position":"img", "window":self.liveVideoWindow} )
					pos.append({"position":"eye", "window":self.recordWindow} )
					pos.append({"position":"prg", "window":self.progressWindow} )
				else:
					pos.append({"position":"img", "window":self.livePhotoWindow} )
					pos.append({"position":"pgd", "window":self.pipBgdWindow} )
					pos.append({"position":"pip", "window":self.liveVideoWindow} )
					if (not self.MESHING):
						pos.append({"position":"scr", "window":self.scrubWindow} )
						pos.append({"position":"inf", "window":self.infWindow} )
					else:
						pos.append({"position":"prg", "window":self.progressWindow} )
		elif (self.TRANSCODING):
			pos.append({"position":"tmr", "window":self.progressWindow} )

		for i in range (0, len(self.windowStack)):
			self.windowStack[i].hide_all()

		self.hideAllWindows()
		self.updatePos( pos )

		for i in range (0, len(self.windowStack)):
			self.windowStack[i].show_all()

		self.LAST_MODE = self.ca.m.MODE
		self.LAST_FULLSCREEN = self.FULLSCREEN
		self.LAST_LIVE = self.LIVEMODE
		self.LAST_RECD_INFO = self.RECD_INFO_ON
		self.LAST_TRANSCODING = self.TRANSCODING
		self.LAST_MESHING = self.MESHING


	def debugWindows( self ):
		for i in range (0, len(self.windowStack)):
			print self.windowStack[i], self.windowStack[i].get_size(), self.windowStack[i].get_position()


	def showWidgets( self ):
		pos = []
		if (self.ca.m.MODE == Constants.MODE_PHOTO):
			if (not self.LIVEMODE):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				if (not self.MESHING):
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"inf", "window":self.infWindow} )
			else:
				pos.append({"position":"max", "window":self.maxWindow} )
				pos.append({"position":"eye", "window":self.recordWindow} )
		elif (self.ca.m.MODE == Constants.MODE_VIDEO):
			if (not self.LIVEMODE):
				pos.append({"position":"pgd", "window":self.pipBgdWindow2} )
				pos.append({"position":"pip", "window":self.playLiveWindow} )
				if (not self.MESHING):
					pos.append({"position":"max", "window":self.maxWindow} )
					pos.append({"position":"scr", "window":self.scrubWindow} )
					pos.append({"position":"inf", "window":self.infWindow} )
			else:
				pos.append({"position":"max", "window":self.maxWindow} )
				pos.append({"position":"eye", "window":self.recordWindow} )
				pos.append({"position":"prg", "window":self.progressWindow} )
		elif (self.ca.m.MODE == Constants.MODE_AUDIO):
			if (not self.LIVEMODE):
				pos.append({"position":"pgd", "window":self.pipBgdWindow} )
				pos.append({"position":"pip", "window":self.liveVideoWindow} )
				if (not self.MESHING):
					pos.append({"position":"scr", "window":self.scrubWindow} )
					pos.append({"position":"inf", "window":self.infWindow} )
			else:
				pos.append({"position":"eye", "window":self.recordWindow} )
				pos.append({"position":"prg", "window":self.progressWindow} )

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
					elif (pos[j]["position"] == "inb"):
						self.setInbLocDim( pos[j]["window"])
					elif (pos[j]["position"] == "prg"):
						self.setPrgLocDim( pos[j]["window"])
					elif (pos[j]["position"] == "tmr"):
						self.setTmrLocDim( pos[j]["window"])
					elif (pos[j]["position"] == "scr"):
						self.setScrLocDim( pos[j]["window"])
					elif (pos[j]["position"] == "inf"):
						self.setInfLocDim( pos[j]["window"])


	def removeThumb( self, recd ):
		kids = self.thumbTray.get_children()
		for i in range (0, len(kids)):
			if (kids[i].recd == recd):
				self.thumbTray.remove_item(kids[i])
				kids[i].cleanUp()
				kids[i].disconnect( kids[i].getButtClickedId() )


	def addThumb( self, recd ):
		butt = RecdButton( self, recd )
		BUTT_CLICKED_ID = butt.connect( "clicked", self._thumbClicked, recd )
		butt.setButtClickedId(BUTT_CLICKED_ID)
		self.thumbTray.add_item( butt, len(self.thumbTray.get_children()) )
		butt.show()


	def removeThumbs( self ):
		kids = self.thumbTray.get_children()
		for i in range (0, len(kids)):
			self.thumbTray.remove_item(kids[i])
			kids[i].cleanUp()
			kids[i].disconnect( kids[i].getButtClickedId() )


	def _thumbClicked( self, button, recd ):
		self.showThumbSelection( recd )


	def infoButtonClicked( self ):
		self.RECD_INFO_ON = not self.RECD_INFO_ON

		centerKid = self.centerBox.get_child()
		if (centerKid != None):
			self.centerBox.remove( centerKid )

		bottomKid = self.bottomCenter.get_child()
		if (bottomKid != None):
			self.bottomCenter.remove( bottomKid )

		if (not self.RECD_INFO_ON):
			if (self.ca.m.MODE == Constants.MODE_PHOTO):
				self.bottomCenter.add( self.namePanel )
				self.bottomCenter.show_all( )
		else:
			self.centerBox.add( self.infoBox )
			self.centerBox.show_all( )
			self.bottomCenter.add( self.namePanel )
			self.bottomCenter.show_all( )

		self.updateVideoComponents( )



	def showMeshRecd( self, recd ):
		record.Record.log.debug('showMeshRecd: heres the downloaded recd to display...')

		#if this thumbnail is being shown, add the option to copy it now
		kids = self.thumbTray.get_children()
		for i in range (0, len(kids)):
			if (kids[i].recd == recd):
				kids[i].addCopyMenuItem()

		if (recd == self.shownRecd):
			record.Record.log.debug('showMeshRecd: and since were still looking at same recd, here it is!')
			self.showThumbSelection( recd )


	def updateMeshProgress( self, progressMade, recd ):
		if (self.shownRecd != recd):
			return
		else:
			type = Constants.mediaTypes[recd.type][Constants.keyIstr]
			if (progressMade):
				msg = istrDownloadingFrom% {"1":type, "2":recd.meshDownloadingFromNick}
				self.progressWindow.updateProgress(recd.meshDownlodingPercent, msg)
			else:
				type = Constants.mediaTypes[recd.type][Constants.keyIstr]
				msg = Constants.istrCannotDownload % {"1":type}
				self.progressWindow.updateProgress(0.0, msg)


	def showThumbSelection( self, recd ):
		lastRecd = self.shownRecd
		self.progressWindow.updateProgress(0.0, "")

		#do we need to know the type, since we're showing based on the mode of the app?
		if (recd.type == Constants.TYPE_PHOTO):
			self.showPhoto( recd )
		elif (recd.type == Constants.TYPE_VIDEO):
			self.showVideo( recd )
		elif (recd.type == Constants.TYPE_AUDIO):
			self.showAudio( recd )

		if (self.shownRecd != lastRecd):
			self.photoXoPanel.updateXoColors(self.shownRecd.colorStroke.hex, self.shownRecd.colorFill.hex)

		bottomKid = self.bottomCenter.get_child()
		if (bottomKid != None):
			self.bottomCenter.remove( bottomKid )

		if (recd.type == Constants.TYPE_PHOTO):
			self.bottomCenter.add( self.namePanel )
		elif (recd.type == Constants.TYPE_VIDEO or recd.type == Constants.TYPE_AUDIO):
			if (self.RECD_INFO_ON):
				self.bottomCenter.add( self.namePanel )
		self.bottomCenter.show_all()

		self.resetWidgetFadeTimer()


	def showAudio( self, recd ):
		self.LIVEMODE = False

		#if (recd != self.shownRecd):
		pixbuf = recd.getAudioImagePixbuf()
		img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)
		self.livePhotoCanvas.setImage( img )
		self.shownRecd = recd
		self.showRecdMeta(recd)

		downloading = self.ca.requestMeshDownload(recd)
		self.MESHING = downloading
		record.Record.log.debug("showAudio: downloading->" + str(downloading))
		if (not downloading):
			mediaFilepath = recd.getMediaFilepath( )
			record.Record.log.debug("showAudio: mediaFilepath->" + str(mediaFilepath))
			if (mediaFilepath != None):
				videoUrl = "file://" + str( mediaFilepath )
				self.ca.gplay.setLocation(videoUrl)
				self.scrubWindow.doPlay()

		self.updateVideoComponents()


	def showVideo( self, recd ):
		if (self.LIVEMODE):
			if (self.ca.glive.isXv()):
				self.ca.glive.setPipeType( self.ca.glive.PIPETYPE_X_VIDEO_DISPLAY )
				self.ca.glive.stop()
				self.ca.glive.play()
		downloading = self.ca.requestMeshDownload(recd)
		self.MESHING = downloading
		self.LIVEMODE = False
		self.shownRecd = recd
		self.updateVideoComponents()
		gobject.idle_add( self.showVideo2, recd, downloading )


	def showVideo2( self, recd, downloading ):
		self.showRecdMeta(recd)

		ableToShowVideo = False
		if (not downloading):
			mediaFilepath = recd.getMediaFilepath()
			if (mediaFilepath != None):
				videoUrl = "file://" + str( mediaFilepath )
				self.ca.gplay.setLocation(videoUrl)
				self.scrubWindow.doPlay()
				ableToShowVideo = True

		if (not ableToShowVideo):
			thumbFilepath = recd.getThumbFilepath( )
			thumbUrl = "file://" + str( thumbFilepath )
			self.ca.gplay.setLocation(thumbUrl)


	def deleteThumbSelection( self, recd ):
		self.ca.m.deleteRecorded( recd )
		self.removeThumb( recd )
		self.removeIfSelectedRecorded( recd )


	def removeIfSelectedRecorded( self, recd ):
		if (recd == self.shownRecd):
			if (recd.type == Constants.TYPE_PHOTO):
				self.livePhotoCanvas.setImage( None )
			elif (recd.type == Constants.TYPE_VIDEO):
				self.ca.gplay.stop()
				self.startLiveVideo( self.playLiveWindow, self.ca.glive.PIPETYPE_XV_VIDEO_DISPLAY_RECORD, False )
			elif (recd.type == Constants.TYPE_AUDIO):
				self.livePhotoCanvas.setImage( None )
				self.startLiveAudio()

			self.LIVEMODE = True
			self.updateVideoComponents()

			self.showLiveVideoTags()


	def startLiveAudio( self ):
		self.ca.m.setUpdating(True)
		self.ca.gplay.stop()

		self.ca.glive.setPipeType( self.ca.glive.PIPETYPE_AUDIO_RECORD )
		self.liveVideoWindow.set_glive(self.ca.glive)

		self.showLiveVideoTags()
		self.LIVEMODE = True
		self.updateVideoComponents()
		self.ca.m.setUpdating(False)


	def showPostProcessGfx( self, show ):
		#not self.FULLSCREEN
		centerKid = self.centerBox.get_child()
		if (centerKid != None):
			self.centerBox.remove( centerKid )

		if ( show ):
			self.centerBox.add( self.backgdCanvasBox )
			self.centerBox.show_all()
		else:
			self.backgdCanvas.setImage( None )


	def setPostProcessPixBuf( self, pixbuf ):
		if (pixbuf.get_width()>160):
			pixbuf = pixbuf.scale_simple(160, 120, gtk.gdk.INTERP_NEAREST)

		pixbuf = utils.grayScalePixBuf(pixbuf, True)
		img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)
		self.backgdCanvas.setImage(img)


	def showRecdMeta( self, recd ):
		self.photographerNameLabel.set_label( recd.recorderName )
		self.nameTextfield.set_text( recd.title )
		self.nameTextfield.set_sensitive( True )
		self.dateDateLabel.set_label( utils.getDateString(recd.time) )

		self.photographerPanel.show()
		self.namePanel.show()
		self.datePanel.show()
		self.tagsPanel.show()
		self.tagsBuffer.set_text("")


	def setWaitCursor( self, win ):
		win.set_cursor( gtk.gdk.Cursor(gtk.gdk.WATCH) )


	def setDefaultCursor( self, win ):
		win.set_cursor( None )


class PhotoCanvas(P5):
	def __init__(self):
		P5.__init__(self)
		self.img = None
		self.drawImg = None
		self.SCALING_IMG_ID = 0
		self.cacheWid = -1
		self.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorBlack.gColor )


	def draw(self, ctx, w, h):
		self.background( ctx, Constants.colorBlack, w, h )

		if (self.img != None):

			if (w == self.img.get_width()):
				self.cacheWid == w
				self.drawImg = self.img

			#only scale images when you need to, otherwise you're wasting cycles, fool!
			if (self.cacheWid != w):
				if (self.SCALING_IMG_ID == 0):
					self.drawImg = None
					self.SCALING_IMG_ID = gobject.idle_add( self.resizeImage, w, h )

			if (self.drawImg != None):
				#center the image based on the image size, and w & h
				ctx.set_source_surface(self.drawImg, (w/2)-(self.drawImg.get_width()/2), (h/2)-(self.drawImg.get_height()/2))
				ctx.paint()

			self.cacheWid = w


	def setImage(self, img):
		self.cacheWid = -1
		self.img = img
		self.drawImg = None
		self.queue_draw()


	def resizeImage(self, w, h):
		self.SCALING_IMG_ID = 0
		if (self.img == None):
			return

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


class xoPanel(P5):
	def __init__(self):
		P5.__init__(self)
		self.xoGuy = None
		self.lastStroke = None
		self.lastFill = None


	def updateXoColors( self, strokeHex, fillHex ):
		if (self.lastStroke != None):
			if ((self.lastStroke == strokeHex) and (self.lastFill == fillHex)):
				return

		lastStroke = strokeHex
		lastFill = fillHex
		self.xoGuy = utils.loadSvg(Constants.xoGuySvgData, strokeHex, fillHex)
		self.queue_draw()


	def draw(self, ctx, w, h):
		#todo: 2x buffer
		self.background( ctx, Constants.colorButton, w, h )

		if (self.xoGuy != None):
			#todo: scale mr xo to fit in his box
			ctx.scale( .6, .6 )
			self.xoGuy.render_cairo( ctx )


class ScrubberWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.UPDATE_INTERVAL = 500
		self.UPDATE_SCALE_ID = 0
		self.CHANGED_ID = 0
		self.was_playing = False
		self.p_position = gst.CLOCK_TIME_NONE
		self.p_duration = gst.CLOCK_TIME_NONE

		self.hbox = gtk.HBox()
		self.hbox.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.hbox.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorBlack.gColor )
		self.add( self.hbox )

		self.button = gtk.Button()
		buttBox = gtk.EventBox()
		buttBox.add(self.button)
		buttBox.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.button.set_image( Constants.recPlayImg )
		self.button.set_property('can-default', True)
		self.button.set_relief(gtk.RELIEF_NONE)
		self.button.set_size_request( self.ui.recordButtWd, self.ui.recordButtWd )
		buttBox.set_size_request( self.ui.recordButtWd, self.ui.recordButtWd )
		#self.button.set_border_width( UI.dim_INSET/2 )
		self.button.show()

		buttBox.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.button.modify_bg( gtk.STATE_ACTIVE, Constants.colorBlack.gColor )

		self.button.connect('clicked', self._buttonClickedCb)
		self.hbox.pack_start(buttBox, expand=False)

		self.adjustment = gtk.Adjustment(0.0, 0.00, 100.0, 0.1, 1.0, 1.0)
		self.hscale = gtk.HScale(self.adjustment)
		self.hscale.set_draw_value(False)
		self.hscale.set_update_policy(gtk.UPDATE_CONTINUOUS)
		hscaleBox = gtk.EventBox()
		hscaleBox.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		hscaleBox.add( self.hscale )
		self.hscale.connect('button-press-event', self._scaleButtonPressCb)
		self.hscale.connect('button-release-event', self._scaleButtonReleaseCb)
		self.hbox.pack_start(hscaleBox, expand=True)


	def removeCallbacks( self ):
		if (self.UPDATE_SCALE_ID != 0):
			gobject.source_remove(self.UPDATE_SCALE_ID)
			self.UPDATE_SCALE_ID = 0
		if (self.CHANGED_ID != 0):
			gobject.source_remove(self.CHANGED_ID)
			self.CHANGED_ID = 0


	def reset(self):
			self.adjustment.set_value(0)


	def _buttonClickedCb(self, widget):
		self.play_toggled()


	def set_button_play(self):
		self.button.set_image(Constants.recPlayImg)


	def set_button_pause(self):
		self.button.set_image(Constants.recPauseImg)


	def play_toggled(self):
		self.p_position, self.p_duration = self.ui.ca.gplay.queryPosition()
		if (self.p_position == self.p_duration):
			self.ui.ca.gplay.seek(0)
			self.ui.ca.gplay.pause()

		if self.ui.ca.gplay.is_playing():
			self.ui.ca.gplay.pause()
			self.set_button_play()
		else:
			#if self.ui.ca.gplay.error:
			#	#todo: check if we have "error", and also to disable everything
			#	self.button.set_disabled()
			#else:
			self.doPlay()


	def doPlay(self):
		self.ui.ca.gplay.play()
		if self.UPDATE_SCALE_ID == 0:
			self.UPDATE_SCALE_ID = gobject.timeout_add(self.UPDATE_INTERVAL, self._updateScaleCb)
		self.set_button_pause()


	def _scaleButtonPressCb(self, widget, event):
		self.button.set_sensitive(False)
		self.was_playing = self.ui.ca.gplay.is_playing()
		if self.was_playing:
			self.ui.ca.gplay.pause()

		# don't timeout-update position during seek
		if self.UPDATE_SCALE_ID != 0:
			gobject.source_remove(self.UPDATE_SCALE_ID)
			self.UPDATE_SCALE_ID = 0

		# make sure we get changed notifies
		if self.CHANGED_ID == 0:
			self.CHANGED_ID = self.hscale.connect('value-changed', self._scaleValueChangedCb)


	def _scaleButtonReleaseCb(self, widget, event):
		# see seek.cstop_seek
		widget.disconnect(self.CHANGED_ID)
		self.CHANGED_ID = 0

		self.button.set_sensitive(True)
		if self.was_playing:
			self.ui.ca.gplay.play()

		if self.UPDATE_SCALE_ID != 0:
			print('Had a previous update timeout id')
		else:
			self.UPDATE_SCALE_ID = gobject.timeout_add(self.UPDATE_INTERVAL, self._updateScaleCb)


	def _scaleValueChangedCb(self, scale):
		real = long(scale.get_value() * self.p_duration / 100) # in ns
		self.ui.ca.gplay.seek(real)
		# allow for a preroll
		self.ui.ca.gplay.get_state(timeout=50*gst.MSECOND) # 50 ms


	def _updateScaleCb(self):
		self.p_position, self.p_duration = self.ui.ca.gplay.queryPosition()
		if self.p_position != gst.CLOCK_TIME_NONE:
			value = self.p_position * 100.0 / self.p_duration
			if (value > 99):
				value = 99
			elif (value < 0):
				value = 0

			self.adjustment.set_value(value)

			if self.ui.ca.gplay.is_playing() and (self.p_position == self.p_duration):
				self.ui.ca.gplay.pause()
				self.set_button_play()

		return True


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
		if (self.ui.FULLSCREEN):
			Constants.maxEnlargeSvg.render_cairo( ctx )
		else:
			Constants.maxReduceSvg.render_cairo( ctx )


	def fireButton(self, actionCommand):
		if (actionCommand == self.maxS):
			self.ui.doFullscreen()


class InfButton(P5Button):
	#todo: just a gtk.Image here, no?
	def __init__(self, ui):
		P5Button.__init__(self)
		self.ui = ui

		self.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorBlack.gColor )

		self.set_size_request( 75, 75 )

		xs = []
		ys = []
		xs.append(0)
		ys.append(0)
		xs.append(75)
		ys.append(0)
		xs.append(75)
		ys.append(75)
		xs.append(0)
		ys.append(75)
		poly = Polygon( xs, ys )
		butt = Button( poly, 0, 0)
		butt.addActionListener( self )
		self.infS = "inf"
		butt.setActionCommand( self.infS )
		self._butts.append( butt )


	def draw(self, ctx, w, h):
		self.background( ctx, Constants.colorBlack, w, h )
		Constants.infoOnSvg.render_cairo( ctx )


	def fireButton(self, actionCommand):
		if (actionCommand == self.infS):
			self.ui.infoButtonClicked()


class RecordButton(gtk.Button):
	def __init__(self):
		gtk.Button.__init__(self)
		self.sens = True
		self.img = None
		#todo: check on record state, compare button imgs


	def set_sensitive(self, sen):
		if (sen == self.sens):
			return
		self.sens = sen

		if (self.sens):
			self.set_image( Constants.recImg )
		else:
			self.set_image( Constants.recInsensitiveImg )

		super(RecordButton, self).set_sensitive(self.sens)


	def doRecordButton(self):
		if (not self.sens):
			return
		self.set_image( Constants.recRedImg )


	def doNormalButton(self):
		if (not self.sens):
			return
		self.set_image( Constants.recImg )



class RecordWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.num = -1

		self.shutterButton = RecordButton()
		self.shutterButton.set_size_request(self.ui.recordButtWd, self.ui.recordButtWd)
		self.shutterButton.set_relief(gtk.RELIEF_NONE)
		self.shutterButton.set_image( Constants.recImg )
		self.shutterButton.connect("clicked", self.ui._shutterClickCb)
		self.shutterButton.set_sensitive(False)

		shutterBox = gtk.EventBox()
		shutterBox.add( self.shutterButton )
		shutterBox.set_size_request( self.ui.controlBarHt, self.ui.controlBarHt )

		shutterBox.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.shutterButton.modify_bg( gtk.STATE_ACTIVE, Constants.colorBlack.gColor )

		hbox = gtk.HBox()
		self.add( hbox )
		leftPanel = gtk.VBox()
		leftEvent = gtk.EventBox()
		leftEvent.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		leftEvent.add( leftPanel )
		hbox.pack_start( leftEvent, expand=True )

		hbox.pack_start( shutterBox, expand=False )

		rightPanel = gtk.VBox()
		rightEvent = gtk.EventBox()
		rightEvent.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		rightEvent.add( rightPanel )
		hbox.pack_start( rightEvent, expand=True )


	def updateCountdown(self, num):
		#todo: fix
		if(num>0):
			if (num != self.num):
				ok = self.getCairoCountdown(num)
				self.shutterButton.set_image(ok)
			self.num = num
		else:
			self.num = -1
			self.updateGfx()


	def getCairoCountdown(self, num):
		return Constants.countdownImgs[int(num)]


	def updateGfx( self ):
#		if (self.ui.ca.m.MODE == Constants.MODE_AUDIO):
#			if (self.shutterButton.get_image() != Constants.micImg):
#				self.shutterButton.set_image( Constants.micImg )
#		else:
#			if (self.shutterButton.get_image() != Constants.camImg):
#				self.shutterButton.set_image( Constants.camImg )
		pass


class ProgressWindow(gtk.Window):
	def __init__(self, ui):
		gtk.Window.__init__(self)
		self.ui = ui
		self.str = None

		eb = gtk.EventBox()
		eb.modify_bg( gtk.STATE_NORMAL, Constants.colorBlack.gColor )
		self.add( eb )

		vb = gtk.VBox()
		vb.set_border_width(5) #todo: use variable
		eb.add(vb)

		self.progBar = gtk.ProgressBar()
		self.progBar.modify_bg( gtk.STATE_INSENSITIVE, Constants.colorBlack.gColor )
		vb.add( self.progBar )

		hbox = gtk.HBox()
		vb.add( hbox )
		self.infoLabel = gtk.Label()
		self.infoLabel.set_alignment( 1, .5 )
		hbox.pack_start(self.infoLabel)


	def updateProgress( self, amt, str ):
		self.progBar.set_fraction( amt )
		if (str != None and str != self.str):
			self.str = str
			self.infoLabel.set_text( "<b><span foreground='white'>"+self.str+"</span></b>")
			self.infoLabel.set_use_markup( True )
		if (amt >= 1):
			self.progBar.set_fraction( 0 )



class PhotoToolbar(gtk.Toolbar):
	def __init__(self):
		gtk.Toolbar.__init__(self)

		img = ToolButton('media-photo')
		img.connect('clicked', self._shutterClickCb)
		img.get_icon_widget().set_property( 'fill-color', Instance.colorFill.hex )
		img.get_icon_widget().set_property( 'stroke-color', Instance.colorStroke.hex )
		self.insert(img, -1)
		img.set_sensitive(False)
		img.show()

		separator = gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self.insert(separator, -1)
		separator.show()

		timerCbb = gtk.combo_box_new_text()
		self.timerCb = ToolComboBox(combo=timerCbb, label_text=Constants.istrTimer)
		for i in range (0, len(Constants.TIMERS)):
			if (i == 0):
				self.timerCb.combo.append_text( Constants.istrNow )
			else:
				self.timerCb.combo.append_text( Constants.istrSeconds % {"1":(str(Constants.TIMERS[i]))} )
		self.timerCb.combo.set_active(0)
		self.insert( self.timerCb, -1 )


	def _shutterClickCb(self, button):
		pass
		#self.ui.doShutter()


	def getTimer(self):
		return Constants.TIMERS[self.timerCb.combo.get_active()]


class VideoToolbar(gtk.Toolbar):
	def __init__(self):
		gtk.Toolbar.__init__(self)

		img = ToolButton('media-video')
		img.connect('clicked', self._shutterClickCb)
		img.get_icon_widget().set_property( 'fill-color', Instance.colorFill.hex )
		img.get_icon_widget().set_property( 'stroke-color', Instance.colorStroke.hex )
		self.insert(img, -1)
		img.set_sensitive(False)
		img.show()

		separator = gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self.insert(separator, -1)
		separator.show()

		timerCbb = gtk.combo_box_new_text()
		self.timerCb = ToolComboBox(combo=timerCbb, label_text=Constants.istrTimer)
		for i in range (0, len(Constants.TIMERS)):
			if (i == 0):
				self.timerCb.combo.append_text( Constants.istrNow )
			else:
				self.timerCb.combo.append_text( Constants.istrSeconds % {"1":(str(Constants.TIMERS[i]))} )
		self.timerCb.combo.set_active(0)
		self.insert( self.timerCb, -1 )

		separator2 = gtk.SeparatorToolItem()
		separator2.set_draw(False)
		separator2.set_expand(False)
		separator2.set_size_request(UI.dim_INSET, -1)
		self.insert( separator2, -1 )

		durCbb = gtk.combo_box_new_text()
		self.durCb = ToolComboBox(combo=durCbb, label_text=Constants.istrDuration)
		for i in range (0, len(Constants.DURATIONS)):
			self.durCb.combo.append_text( Constants.istrSeconds % {"1":(str(Constants.DURATIONS[i]))} )
		self.durCb.combo.set_active(0)
		self.insert(self.durCb, -1 )


	def _shutterClickCb(self, button):
		pass
		#self.ui.doShutter()


	def getTimer(self):
		return Constants.TIMERS[self.timerCb.combo.get_active()]


	def getDuration(self):
		return Constants.DURATIONS[self.durCb.combo.get_active()]


class AudioToolbar(gtk.Toolbar):
	def __init__(self):
		gtk.Toolbar.__init__(self)
		#self.ui = ui

		img = ToolButton('media-audio')
		img.connect('clicked', self._shutterClickCb)
		img.get_icon_widget().set_property( 'fill-color', Instance.colorFill.hex )
		img.get_icon_widget().set_property( 'stroke-color', Instance.colorStroke.hex )
		self.insert(img, -1)
		img.set_sensitive(False)
		img.show()

		separator = gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self.insert(separator, -1)
		separator.show()

		timerCbb = gtk.combo_box_new_text()
		self.timerCb = ToolComboBox(combo=timerCbb, label_text=Constants.istrTimer)
		for i in range (0, len(Constants.TIMERS)):
			if (i == 0):
				self.timerCb.combo.append_text( Constants.istrNow )
			else:
				self.timerCb.combo.append_text( Constants.istrSeconds % {"1":(str(Constants.TIMERS[i]))} )
		self.timerCb.combo.set_active(0)
		self.insert( self.timerCb, -1 )

		separator2 = gtk.SeparatorToolItem()
		separator2.set_draw(False)
		separator2.set_expand(False)
		separator2.set_size_request(UI.dim_INSET, -1)
		self.insert( separator2, -1 )

		durCbb = gtk.combo_box_new_text()
		self.durCb = ToolComboBox(combo=durCbb, label_text=Constants.istrDuration)
		for i in range (0, len(Constants.DURATIONS)):
			self.durCb.combo.append_text( Constants.istrSeconds % {"1":(str(Constants.DURATIONS[i]))} )
		self.durCb.combo.set_active(0)
		self.insert(self.durCb, -1 )


	def _shutterClickCb(self, button):
		pass
		#self.ui.doShutter()


	def getTimer(self):
		return Constants.TIMERS[self.timerCb.combo.get_active()]


	def getDuration(self):
		return Constants.DURATIONS[self.durCb.combo.get_active()]