from sugar.graphics.palette import Palette
from sugar.graphics.tray import TrayButton
from sugar.grahics.icon import Icon
from sugar.graphics import style

class RecdButton(TrayButton, gobject.GObject):
	def __init__(self, stuff):
		TrayButton.__init__(self)
		