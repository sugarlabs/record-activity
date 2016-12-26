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

# -*- coding: UTF-8 -*-
import os
from gettext import gettext as _

from sugar3.activity import activity

MODE_PHOTO = 0
MODE_VIDEO = 1
MODE_AUDIO = 2
TYPE_PHOTO = MODE_PHOTO
TYPE_VIDEO = MODE_VIDEO
TYPE_AUDIO = MODE_AUDIO

STATE_INVISIBLE = 0
STATE_READY = 1
STATE_RECORDING = 2
STATE_PROCESSING = 3
STATE_DOWNLOADING = 4

MEDIA_INFO = {}
MEDIA_INFO[TYPE_PHOTO] = {
    'name' : 'photo',
    'mime' : 'image/jpeg',
    'ext' : 'jpg',
    'istr' : _('Photo')
}

MEDIA_INFO[TYPE_VIDEO] = {
    'name' : 'video',
    'mime' : 'video/ogg',
    'ext' : 'ogg',
    'istr' : _('Video')
}

MEDIA_INFO[TYPE_AUDIO] = {
    'name' : 'audio',
    'mime' :'audio/ogg',
    'ext' : 'ogg',
    'istr' : _('Audio')
}

DBUS_SERVICE = "org.laptop.Record"
DBUS_IFACE = DBUS_SERVICE
DBUS_PATH = "/org/laptop/Record"

GFX_PATH = os.path.join(activity.get_bundle_path(), "gfx")

