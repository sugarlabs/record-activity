#Copyright (c) 2007, Media Modifications Ltd.

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


import gtk
import pygtk
import pygst
pygst.require('0.10')
import gst
import gst.interfaces

class Greplay:



	def __init__(self, pca):
		self.ca = pca


	def getAlbumArt( self, recd ):
		#todo: handle None paths here
		#todo: +n needed here?
		pp = gst.parse_launch("filesrc location="+recd.getMediaFilelocation(False)+" ! oggdemux ! vorbisdec ! fakesink")
		pp.get_bus().add_signal_watch()
		pp.get_bus().connect("message", self._onMessageCb)
		pp.set_state(gst.STATE_PLAYING)


	def _onMessageCb(self, bus, message):
		t = message.type
		if t == gst.MESSAGE_EOS:
			print("MESSAGE_EOS")
		elif t == gst.MESSAGE_ERROR:
			print("MESSAGE_ERROR")
		elif t == gst.MESSAGE_TAG:
			tags = message.parse_tag()
			for tag in tags.keys():
				if (str(tag) == "extended-comment"):
					#todo, check for tagname
					base64imgString = str(tags[tag])[len("coverart="):]
					pixbuf = utils.pixbufFromString(base64imgString)
					#todo: emit here
