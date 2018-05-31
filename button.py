# Copyright (C) 2008, Media Modifications Ltd.
# Copyright (C) 2011, One Laptop per Child (3bc80c7)

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from gi.repository import GObject, Gtk, GdkPixbuf
from gettext import gettext as _

from sugar3.graphics.palette import Palette
from sugar3.graphics.palettemenu import PaletteMenuBox
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.tray import TrayButton
import constants
import utils

class RecdButton(TrayButton):
    __gsignals__ = {
        'remove-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
        'copy-clipboard-requested': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, recd):
        TrayButton.__init__(self)
        self._recd = recd

        self.set_icon_widget(self.get_image())
        self._copy_menu_item_handler = None

        palette = Palette(recd.title)
        self.set_palette(palette)

        self._box = PaletteMenuBox()
        palette.set_content(self._box)
        self._box.show()

        self._rem_menu_item = PaletteMenuItem(_('Erase'),
                                              icon_name='edit-delete')
        self._rem_menu_item_handler = self._rem_menu_item.connect('activate', self._remove_clicked)
        self._box.append_item(self._rem_menu_item)
        self._rem_menu_item.show()

        self._add_copy_menu_item()

    def _add_copy_menu_item( self ):
        if self._recd.buddy and not self._recd.downloadedFromBuddy:
            return

        self._copy_menu_item = PaletteMenuItem(_('Copy to clipboard'),
                                               icon_name='edit-copy')
        self._copy_menu_item_handler = self._copy_menu_item.connect('activate', self._copy_clipboard_clicked)
        self._box.append_item(self._copy_menu_item)
        self._copy_menu_item.show()

    def get_recd(self):
        return self._recd

    def get_image(self):
        ipb = self._recd.getThumbPixbuf()

        if ipb:
            w = ipb.get_width()
            h = ipb.get_height()
            a = float(w) / float(h)
        else:
            a = 16./9

        if a < 1.4:
            paths = {constants.TYPE_PHOTO: 'object-photo.svg',
                     constants.TYPE_VIDEO: 'object-video.svg',
                     constants.TYPE_AUDIO: 'object-audio.svg'}
            x = 8
            y = 8
        else:
            paths = {constants.TYPE_PHOTO: 'object-photo-16to9.svg',
                     constants.TYPE_VIDEO: 'object-video-16to9.svg',
                     constants.TYPE_AUDIO: 'object-audio-16to9.svg'}
            x = 9
            y = 18

        path = paths[self._recd.type]

        pixbuf = utils.load_colored_svg(path, self._recd.colorStroke,
                                        self._recd.colorFill)
        if ipb:
            ipb.composite(pixbuf, x, y, w, h, x, y, 1, 1,
                          GdkPixbuf.InterpType.BILINEAR, 255)
        img = Gtk.Image()
        img.set_from_pixbuf(pixbuf)
        img.show()
        return img

    def cleanup(self):
        self._rem_menu_item.disconnect(self._rem_menu_item_handler)
        if self._copy_menu_item_handler != None:
            self._copy_menu_item.disconnect(self._copy_menu_item_handler)

    def _remove_clicked(self, widget):
        self.emit('remove-requested')

    def _copy_clipboard_clicked(self, widget):
        self.emit('copy-clipboard-requested')
