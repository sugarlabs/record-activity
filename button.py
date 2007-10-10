import gtk
import os
import gobject
import rsvg

from sugar.graphics.palette import Palette
from sugar.graphics.tray import TrayButton
from sugar.graphics.icon import Icon
from sugar.graphics import style

class RecdButton(TrayButton, gobject.GObject):
	def __init__(self, ui, recd):
		TrayButton.__init__(self)
		self.ui = ui
		self.recd = recd

		img = self.getImg( )
		self.set_icon_widget( img )

		self.setup_rollover_options( recd.title )
		#todo: add drag and drop
		#todo: add copy to clipboard only when available!


	def getImg( self ):
		#todo: remove mem refs

		img = gtk.Image()
		ipb = self.recd.getThumbPixbuf()
		if (self.recd.type == self.ui.ca.m.TYPE_PHOTO):
			if (self.recd.buddy):
				thumbPhotoSvg = self.ui.loadSvg(self.ui.thumbPhotoSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
				pb = thumbPhotoSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 8, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )
			else:
				pb = self.ui.thumbPhotoSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 8, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )

		if (self.recd.type == self.ui.ca.m.TYPE_VIDEO):
			if (self.recd.buddy):
				thumbVideoSvg = self.ui.loadSvg(self.ui.thumbVideoSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
				pb = thumbVideoSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 8, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )
			else:
				pb = self.ui.thumbVideoSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 22, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )

		if (self.recd.type == self.ui.ca.m.TYPE_AUDIO):
			if (self.recd.buddy):
				thumbAudioSvg = self.ui.loadSvg(self.ui.thumbAudioSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
				pb = thumbAudioSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 8, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )
			else:
				pb = self.ui.thumbVideoSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 22, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )

		img.set_from_pixbuf(pb)
		return img


	def setup_rollover_options( self, info ):
		palette = Palette(info)
		self.set_palette(palette)

		self.rem_menu_item = gtk.MenuItem( self.ui.ca.istrRemove )
		self.ACTIVATE_REMOVE_ID = rem_menu_item.connect('activate', self._itemRemoveCb)
		palette.menu.append(rem_menu_item)
		rem_menu_item.show()

		self.copy_menu_item = gtk.MenuItem( self.ui.ca.istrCopyToClipboard )
		self.ACTIVATE_COPY_ID = copy_menu_item.connect('activate', self._itemCopyToClipboardCb)
		palette.menu.append(copy_menu_item)
		copy_menu_item.show()


	def cleanUp( self ):
		self.rem_menu_item.disconnect( self.ACTIVATE_REMOVE_ID )
		self.copy_menu_item.disconnect( self.ACTIVATE_COPY_ID )


	def _itemRemoveCb(self, widget):
		self.ui.deleteThumbSelection( self.recd )


	def _itemCopyToClipboardCb(self, widget):
		self.ui.copyToClipboard( self.recd )