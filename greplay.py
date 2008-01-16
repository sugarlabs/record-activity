#Copyright (c) 2008, Media Modifications Ltd.

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

import gst
import gst.interfaces
import pygst
pygst.require('0.10')
import gobject
import os

import record
import utils

class Greplay(gobject.GObject):

	__gsignals__ = {
		'coverart-found':
			(gobject.SIGNAL_RUN_FIRST, None, [object])
	}


	def findAlbumArt( self, path ):
		record.Record.log.debug("getAlbumArt")
		if (path == None):
			record.Record.log.debug("getAlbumArt: path==None")
			self.emit('coverart-found', None)
			return
		if (not os.path.exists(path)):
			record.Record.log.debug("getAlbumArt: path doesn't exist")
			self.emit('coverart-found', None)
			return

		self.pp = gst.parse_launch("filesrc location="+str(path)+" ! oggdemux ! vorbisdec ! fakesink")
		self.pp.get_bus().add_signal_watch()
		self.pp.get_bus().connect("message", self._onMessageCb)
		self.pp.set_state(gst.STATE_PLAYING)


	def _onMessageCb(self, bus, message):
		t = message.type
		if t == gst.MESSAGE_EOS:
			record.Record.log.debug("Greplay:MESSAGE_EOS")
			self.emit('coverart-found', None)
			self.pp.set_state(gst.STATE_NULL)
			return False
		elif t == gst.MESSAGE_ERROR:
			record.Record.log.debug("Greplay:MESSAGE_ERROR")
			self.emit('coverart-found', None)
			self.pp.set_state(gst.STATE_NULL)
			return False
		elif t == gst.MESSAGE_TAG:
			tags = message.parse_tag()
			for tag in tags.keys():
				if (str(tag) == "extended-comment"):
					record.Record.log.debug("Found the tag!")
					#todo, check for tagname
					base64imgString = str(tags[tag])[len("coverart="):]

					pixbuf = utils.getPixbufFromString(base64imgString)
					self.pp.set_state(gst.STATE_NULL)
					self.emit('coverart-found', pixbuf)
					return False
		return True
