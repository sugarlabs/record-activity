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

# This class is a cut-down version of glive which uses an ximagesink
# rather than an xvimagesink. This is used in video playback mode, where
# our only Xv port is used for Theora playback.
#
# I tried to modify the glive pipeline to allow swapping an xvimagesink for
# an ximagesink and vice-versa, but that didn't work out (all kinds of strange
# behaviour, perhaps a gstreamer bug). So we resort to using a separate
# pipeline - ugly, but it works...

import os
import gtk
import pygtk
pygtk.require('2.0')
import sys
import gst
import gst.interfaces
import pygst
pygst.require('0.10')
import time
import threading
import gobject
gobject.threads_init()

from instance import Instance
from constants import Constants
import record
import utils
import ui

class GliveX:
	def __init__(self, pca):
		self.window = None
		self.ca = pca

		self.playing = False

		self.pipeline = gst.Pipeline("slow-pipeline")
		self.createPipeline()

		bus = self.pipeline.get_bus()
		bus.enable_sync_message_emission()
		bus.add_signal_watch()
		self.SYNC_ID = bus.connect('sync-message::element', self._onSyncMessageCb)
		self.MESSAGE_ID = bus.connect('message', self._onMessageCb)

	def createPipeline ( self ):
		src = gst.element_factory_make("v4l2src", "camsrc")
		try:
			# old gst-plugins-good does not have this property
			src.set_property("queue-size", 2)
		except:
			pass

		queue = gst.element_factory_make("queue", "dispqueue")
		queue.set_property("leaky", True)
		queue.set_property('max-size-buffers', 1)

		scale = gst.element_factory_make("videoscale", "scale")
		scalecaps = gst.Caps('video/x-raw-yuv,width='+str(ui.UI.dim_PIPW)+',height='+str(ui.UI.dim_PIPH))
		colorspace = gst.element_factory_make("ffmpegcolorspace", "colorspace")
		xsink = gst.element_factory_make("ximagesink", "xsink")
		self.pipeline.add(src, queue, scale, colorspace, xsink)
		gst.element_link_many(src, queue, scale)
		scale.link(colorspace, scalecaps)
		colorspace.link(xsink)

	def play(self):
		self.pipeline.set_state(gst.STATE_PLAYING)
		self.playing = True

	def pause(self):
		self.pipeline.set_state(gst.STATE_PAUSED)
		self.playing = False

	def stop(self):
		self.pipeline.set_state(gst.STATE_NULL)
		self.playing = False

	def is_playing(self):
		return self.playing

	def idlePlayElement(self, element):
		element.set_state(gst.STATE_PLAYING)
		return False

	def _onSyncMessageCb(self, bus, message):
		if message.structure is None:
			return
		if message.structure.get_name() == 'prepare-xwindow-id':
			self.window.set_sink(message.src)
			message.src.set_property('force-aspect-ratio', True)

	def _onMessageCb(self, bus, message):
		t = message.type
		if t == gst.MESSAGE_EOS:
			#print("MESSAGE_EOS")
			pass
		elif t == gst.MESSAGE_ERROR:
			#todo: if we come out of suspend/resume with errors, then get us back up and running...
			#todo: handle "No space left on the resource.gstfilesink.c"
			#err, debug = message.parse_error()
			pass

class SlowLiveVideoWindow(gtk.Window):
	def __init__(self, bgd ):
		gtk.Window.__init__(self)

		self.imagesink = None
		self.glivex = None

		self.modify_bg( gtk.STATE_NORMAL, bgd )
		self.modify_bg( gtk.STATE_INSENSITIVE, bgd )
		self.unset_flags(gtk.DOUBLE_BUFFERED)
		self.set_flags(gtk.APP_PAINTABLE)

	def set_glivex(self, pglivex):
		self.glivex = pglivex
		self.glivex.window = self

	def set_sink(self, sink):
		if (self.imagesink != None):
			assert self.window.xid
			self.imagesink = None
			del self.imagesink

		self.imagesink = sink
		self.imagesink.set_xwindow_id(self.window.xid)
