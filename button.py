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


	def getImg( self ):
		img = gtk.Image()
		ipb = self.recd.getThumbPixbuf()
		if (self.recd.type == self.ui.ca.m.TYPE_PHOTO):
			if (self.tc.recd.buddy):
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
			if (self.tc.recd.buddy):
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
			if (self.tc.recd.buddy):
				thumbAudioSvg = self.ui.loadSvg(self.ui.thumbAudioSvgData, self.recd.colorStroke.hex, self.recd.colorFill.hex)
				pb = thumbAudioSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 8, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )
			else:
				pb = self.ui.thumbAudioSvg.get_pixbuf()
				img.set_from_pixbuf( pb )
				img.show()
				ipb.composite(pb, 8, 22, ipb.get_width(), ipb.get_height(), 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255 )

		img.set_from_pixbuf(pb)
		return img



	def setup_rollover_options( self, info ):
		palette = Palette(info)
		self.set_palette(palette)

		menu_item = gtk.MenuItem( 'Remove' )
		menu_item.connect('activate', self._item_remove_cb)
		palette.menu.append(menu_item)
		menu_item.show()


	def _item_remove_cb(self, widget):
		self.ui.deleteThumbSelection( self.recd );