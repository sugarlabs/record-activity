# -*- coding: UTF-8 -*-
import os
from gettext import gettext as _

from sugar.activity import activity

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

