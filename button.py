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
		pb = self.ui.thumbVideoSvg.get_pixbuf()
		img = gtk.Image()
		img.set_from_pixbuf( pb )
		img.show()
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