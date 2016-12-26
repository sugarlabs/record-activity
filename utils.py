#Copyright (C) 2008, Media Modifications Ltd.
#Copyright (C) 2011, One Laptop per Child (3bc80c7)

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

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
    return pixbuf.scale_simple(108, 81, gtk.gdk.INTERP_BILINEAR)

def getDateString( when ):
    return strftime( "%c", time.localtime(when) )

