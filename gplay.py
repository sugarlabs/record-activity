import gtk
import pygtk
pygtk.require('2.0')
import sys
import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import gobject
import time
gobject.threads_init()

class Gplay:

	def __init__(self, pca):
		self.ca = pca
		self.window = None
		self.players = []
		self.nextMovie()

	def nextMovie(self):
		if ( len(self.players) > 0 ):
			self.getPlayer().set_property("video-sink", None)
			self.getPlayer().get_bus().disconnect(self.SYNC_ID)
			self.getPlayer().get_bus().remove_signal_watch()
			self.getPlayer().get_bus().disable_sync_message_emission()

		player = gst.element_factory_make("playbin", "playbin")
		xis = gst.element_factory_make("xvimagesink", "xvimagesink")
		player.set_property("video-sink", xis)
		bus = player.get_bus()
		bus.enable_sync_message_emission()
		bus.add_signal_watch()
		self.SYNC_ID = bus.connect('sync-message::element', self.onSyncMessage)
		self.players.append(player)

	def getPlayer(self):
		return self.players[len(self.players)-1]

	def onSyncMessage(self, bus, message):
		if message.structure is None:
			return
		if message.structure.get_name() == 'prepare-xwindow-id':
			self.window.set_sink(message.src)
			message.src.set_property('force-aspect-ratio', True)

	def setLocation(self, location):
		if (self.getPlayer().get_property('uri') == location):
			evt = gst.event_new_seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE, gst.SEEK_TYPE_SET, gst.SECOND*0,  gst.SEEK_TYPE_NONE, 0)
			res = self.getPlayer().send_event(evt)
			if res:
				self.getPlayer().set_new_stream_time(0L)
			return

		self.getPlayer().set_state(gst.STATE_READY)
		self.getPlayer().set_property('uri', location)
		self.play()

	def pause(self):
		self.getPlayer().set_state(gst.STATE_PAUSED)

	def play(self):
		self.getPlayer().set_state(gst.STATE_PLAYING)

	def stop(self):
		self.getPlayer().set_state(gst.STATE_NULL)
		self.nextMovie()


class PlayVideoWindow(gtk.Window):
	def __init__(self):
		gtk.Window.__init__(self)

		self.imagesink = None
		self.glive = None

		self.unset_flags(gtk.DOUBLE_BUFFERED)
		self.set_flags(gtk.APP_PAINTABLE)

	def set_gplay(self, pgplay):
		self.gplay = pgplay
		self.gplay.window = self

	def set_sink(self, sink):
		if (self.imagesink != None):
			assert self.window.xid
			self.imagesink = None
			del self.imagesink

		self.imagesink = sink
		self.imagesink.set_xwindow_id(self.window.xid)