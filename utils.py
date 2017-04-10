import base64
import rsvg
import re
import os
import gtk
import time
from time import strftime

import constants


def getStringEncodedFromPixbuf(pixbuf):
    data = [""]
    pixbuf.save_to_callback(_saveDataToBufferCb, "png", {}, data)
    return base64.b64encode(str(data[0]))


def getStringFromPixbuf(pixbuf):
    data = [""]
    pixbuf.save_to_callback(_saveDataToBufferCb, "png", {}, data)
    return str(data[0])


def _saveDataToBufferCb(buf, data):
    data[0] += buf
    return True


def getPixbufFromString(str):
    pbl = gtk.gdk.PixbufLoader()
    data = base64.b64decode( str )
    pbl.write(data)
    pbl.close()
    return pbl.get_pixbuf()


def load_colored_svg(filename, stroke, fill):
    path = os.path.join(constants.GFX_PATH, filename)
    data = open(path, 'r').read()

    entity = '<!ENTITY fill_color "%s">' % fill
    data = re.sub('<!ENTITY fill_color .*>', entity, data)

    entity = '<!ENTITY stroke_color "%s">' % stroke
    data = re.sub('<!ENTITY stroke_color .*>', entity, data)

    return rsvg.Handle(data=data).get_pixbuf()

def getUniqueFilepath( path, i ):
    pathOb = os.path.abspath( path )
    newPath = os.path.join( os.path.dirname(pathOb), str( str(i) + os.path.basename(pathOb) ) )
    if (os.path.exists(newPath)):
        i = i + 1
        return getUniqueFilepath( pathOb, i )
    else:
        return os.path.abspath( newPath )

def generate_thumbnail(pixbuf):
    width = 108
    height = 81

    # scale to match available height, retaining aspect ratio
    adjusted = height * pixbuf.get_width() / pixbuf.get_height()
    scaled = pixbuf.scale_simple(adjusted, height, gtk.gdk.INTERP_BILINEAR)

    # where aspect ratio is conventional, e.g. 4:3, return scaled image
    if adjusted == width:
        return scaled

    # where aspect ratio is unconventional, e.g. 16:9, trim sides
    trimmed = gtk.gdk.Pixbuf(scaled.get_colorspace(), scaled.get_has_alpha(),
                             scaled.get_bits_per_sample(), width, height)
    scaled.copy_area((adjusted - width) / 2, 0, width, height, trimmed, 0, 0)
    return trimmed

def getDateString( when ):
    return strftime( "%c", time.localtime(when) )

