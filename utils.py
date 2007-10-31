import base64


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