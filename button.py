import gtk
import os
import gobject
import rsvg
import gc

from sugar.graphics.palette import Palette
from sugar.graphics.tray import TrayButton
from sugar.graphics.icon import Icon
from sugar.graphics import style
from constants import Constants
import utils

class RecdButton(TrayButton, gobject.GObject):
	def __init__(self, ui, recd):
		TrayButton.__init__(self)
		self.ui = ui
		self.recd = recd

		img = self.getImg( )
		self.set_icon_widget( img )

		self.ACTIVATE_COPY_ID = 0
		self.ACTIVATE_REMOVE_ID = 0
		self.setup_rollover_options( recd.title )


	def getImg( self ):
		img = gtk.Image()
		ipb = self.recd.getThumbPixbuf()
		xoff = 0
		yoff = 0
		pb = None
		if (self.recd.type == Constants.TYPE_PHOTO):
			xoff = 8
			yoff = 8
			if (self.recd.buddy):
				thumbPhotoSvg = utils.loadSvg(Constants.thumbPhotoSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
				pb = thumbPhotoSvg.get_pixbuf()
			else:
				pb = Constants.thumbPhotoSvg.get_pixbuf()

		elif (self.recd.type == Constants.TYPE_VIDEO):
			xoff = 8
			yoff = 22
			if (self.recd.buddy):
				thumbVideoSvg = utils.loadSvg(Constants.thumbVideoSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
				pb = thumbVideoSvg.get_pixbuf()
			else:
				pb = Constants.thumbVideoSvg.get_pixbuf()

		elif (self.recd.type == Constants.TYPE_AUDIO):
			xoff = 8
			yoff = 22
			if (self.recd.buddy):
				thumbAudioSvg = utils.loadSvg(Constants.thumbAudioSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
				pb = thumbAudioSvg.get_pixbuf()
			else:
				pb = Constants.thumbVideoSvg.get_pixbuf()

		img.set_from_pixbuf( pb )
		img.show()
		ipb.composite(pb, xoff, yoff, ipb.get_width(), ipb.get_height(), xoff, yoff, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )
		img.set_from_pixbuf(pb)

		gc.collect()

		return img


	def setButtClickedId( self, id ):
		self.BUTT_CLICKED_ID = id


	def getButtClickedId( self ):
		return self.BUTT_CLICKED_ID


	def setup_rollover_options( self, info ):
		palette = Palette(info)
		self.set_palette(palette)

		self.rem_menu_item = gtk.MenuItem( Constants.istrRemove )
		self.ACTIVATE_REMOVE_ID = self.rem_menu_item.connect('activate', self._itemRemoveCb)
		palette.menu.append(self.rem_menu_item)
		self.rem_menu_item.show()

		self.addCopyMenuItem()


	def addCopyMenuItem( self ):
		if (self.recd.buddy and not self.recd.downloadedFromBuddy):
			return
		if (self.ACTIVATE_COPY_ID != 0):
			return

		self.copy_menu_item = gtk.MenuItem( Constants.istrCopyToClipboard )
		self.ACTIVATE_COPY_ID = self.copy_menu_item.connect('activate', self._itemCopyToClipboardCb)
		self.get_palette().menu.append(self.copy_menu_item)
		self.copy_menu_item.show()


	def cleanUp( self ):
		self.rem_menu_item.disconnect( self.ACTIVATE_REMOVE_ID )
		if (self.ACTIVATE_COPY_ID != 0):
			self.copy_menu_item.disconnect( self.ACTIVATE_COPY_ID )


	def _itemRemoveCb(self, widget):
		self.ui.deleteThumbSelection( self.recd )


	def _itemCopyToClipboardCb(self, widget):
		self.ui.copyToClipboard( self.recd )