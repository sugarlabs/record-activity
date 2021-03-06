# Copyright (c) 2011 One Laptop per Child

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

from gi.repository import Gtk

from sugar3.graphics.combobox import ComboBox
from sugar3.graphics import style


class IconComboBox(Gtk.ToolItem):
    def __init__(self, icon_name, **kwargs):
        Gtk.ToolItem.__init__(self, **kwargs)

        self.icon_name = icon_name
        self.set_border_width(style.DEFAULT_PADDING)

        self.combo = ComboBox()
        self.combo.set_focus_on_click(False)
        self.combo.show()

        self.add(self.combo)

    def append_item(self, i, text):
        self.combo.append_item(i, text, icon_name=self.icon_name)
