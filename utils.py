import base64
import rsvg
import re
import os
import cairo
import gc
import gtk
from hashlib import md5

from sugar import util
import _camera

def getStringFromPixbuf(pixbuf):
	data = [""]
	pixbuf.save_to_callback(_saveDataToBufferCb, "png", {}, data)
	return base64.b64encode(str(data[0]))


def _saveDataToBufferCb(buf, data):
	data[0] += buf
	return True


def getPixbufFromString(str):
	pbl = gtk.gdk.PixbufLoader()
	data = base64.b64decode( str )
	pbl.write(data)
	pbl.close()
	return pbl.get_pixbuf()


def loadSvg( data, stroke, fill ):
	if ((stroke == None) or (fill == None)):
		return rsvg.Handle( data=data )

	entity = '<!ENTITY fill_color "%s">' % fill
	data = re.sub('<!ENTITY fill_color .*>', entity, data)

	entity = '<!ENTITY stroke_color "%s">' % stroke
	data = re.sub('<!ENTITY stroke_color .*>', entity, data)

	return rsvg.Handle( data=data )


def getUniqueFilepath( path, i ):
	pathOb = os.path.abspath( path )
	if (os.path.exists(pathOb)):
		i = i+1
		newPath = os.path.join( os.path.dirname(pathOb), str( str(i) + os.path.basename(pathOb) ) )
		return getUniqueFilepath( str(newPath), i )
	else:
		return os.path.abspath( path )


def md5File( filepath ):
	md = md5()
	f = file( filepath, 'rb' )
	md.update( f.read() )
	digest = md.hexdigest()
	hash = util.printable_hash(digest)
	return hash


def generateThumbnail( pixbuf, scale, thumbw, thumbh ):
	#need to generate thumbnail version here
	thumbImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, thumbw, thumbh)
	tctx = cairo.Context(thumbImg)
	img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)
	tctx.scale(scale, scale)
	tctx.set_source_surface(img, 0, 0)
	tctx.paint()
	gc.collect()
	return thumbImg


def scaleSvgToDim( handle, dim ):
	#todo...
	scale = 1.0

	svgDim = handle.get_dimension_data()
	if (svgDim[0] > dim[0]):
		pass

	return scale


def getDateString( time ):
	#todo: internationalize the date
	return strftime( "%a, %b %d, %I:%M:%S %p", time.localtime(time) )


def grayScalePixBuf( pb, copy ):
	arr = pb.get_pixels_array()
	if (copy):
		arr = arr.copy()
	for row in arr:
		for pxl in row:
			y = 0.3*pxl[0][0]+0.59*pxl[1][0]+0.11*pxl[2][0]
			pxl[0][0] = y
			pxl[1][0] = y
			pxl[2][0] = y
	return gtk.gdk.pixbuf_new_from_array(arr, pb.get_colorspace(), pb.get_bits_per_sample())