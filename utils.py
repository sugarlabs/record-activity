import base64
import re
import os
from gi.repository import Gtk, Rsvg, GdkPixbuf
import time

import constants


def getStringEncodedFromPixbuf(pixbuf):
    result, data = pixbuf.save_to_bufferv('png', [], [])
    return base64.b64encode(data)
    #data = [""]
    #pixbuf.save_to_callbackv(_saveDataToBufferCb, data, "png", [], [])
    #return base64.b64encode(str(data[0]))


def getStringFromPixbuf(pixbuf):
    result, data = pixbuf.save_to_bufferv('png', [], [])
    return data
    #data = [""]
    #pixbuf.save_to_callbackv(_saveDataToBufferCb, data, "png", [], [])
    #return str(data[0])


#def _saveDataToBufferCb(buf, data):
#    data[0] += buf
#    return True


def getPixbufFromString(str):
    pbl = GdkPixbuf.PixbufLoader()
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

    return Rsvg.Handle.new_from_data(data).get_pixbuf()

def getUniqueFilepath( path, i ):
    pathOb = os.path.abspath( path )
    newPath = os.path.join( os.path.dirname(pathOb), str( str(i) + os.path.basename(pathOb) ) )
    if (os.path.exists(newPath)):
        i = i + 1
        return getUniqueFilepath( pathOb, i )
    else:
        return os.path.abspath( newPath )

def generate_thumbnail(pixbuf):
    return pixbuf.scale_simple(108, 81, GdkPixbuf.InterpType.BILINEAR)

def getDateString( when ):
    return time.strftime( "%c", time.localtime(when) )

