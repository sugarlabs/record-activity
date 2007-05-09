#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

from controller import Controller

import os
import gtk
import pygtk
pygtk.require('2.0')
import sys
import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import time
import threading
import gobject
gobject.threads_init()

class Glive:

	def __init__(self, pop):
		self._pop = pop
		self.pipes = []
		self.nextPipe()
		self.thumbPipes = []
		self.muxPipes = []

	def pipe(self):
		return self.pipes[ len(self.pipes)-1 ]

	def el(self, name):
		n = str(len(self.pipes)-1)
		return self.pipe().get_by_name(name+"_"+n)

	def thumbPipe(self):
		return self.thumbPipes[ len(self.thumbPipes)-1 ]

	def thumbEl(self, name):
		n = str(len(self.thumbPipes)-1)
		return self.thumbPipe().get_by_name(name+"_"+n)

	def muxPipe(self):
		return self.muxPipes[ len(self.muxPipes)-1 ]

	def play(self):
		self.pipe().set_state(gst.STATE_PLAYING)

	def stop(self):
		self.pipe().set_state(gst.STATE_NULL)
		self.nextPipe()

	def nextPipe(self):
		if ( len(self.pipes) > 0 ):
			self.pipe().get_bus().disconnect(self.SYNC_ID)
			self.pipe().get_bus().remove_signal_watch()
			self.pipe().get_bus().disable_sync_message_emission()
	
		n = str(len(self.pipes))
		pipeline = gst.parse_launch("videotestsrc name=v4l2src_"+n+" ! tee name=videoTee_"+n+" ! queue name=movieQueue_" +n+" ! videorate name=movieVideorate_"+n+" ! video/x-raw-yuv,framerate=15/1 ! videoscale name=movieVideoscale_"+n+" ! video/x-raw-yuv,width=160,height=120 ! ffmpegcolorspace name=movieFfmpegcolorspace_"+n+" ! theoraenc quality=16 name=movieTheoraenc_"+n+" ! oggmux name=movieOggmux_"+n+" ! filesink name=movieFilesink_"+n+" videoTee_"+n+". ! xvimagesink name=xvimagesink_"+n+" videoTee_"+n+". ! queue name=picQueue_"+n+" ! ffmpegcolorspace name=picFfmpegcolorspace_"+n+" ! jpegenc name=picJPegenc_"+n+" ! fakesink name=picFakesink_"+n+" alsasrc name=audioAlsasrc_"+n+" ! audio/x-raw-int,rate=8000,channels=1,depth=8 ! tee name=audioTee_"+n +" ! wavenc name=audioWavenc_"+n+" ! filesink name=audioFilesink_"+n)

		v4l2src = pipeline.get_by_name('v4l2src_'+n)
		videoTee = pipeline.get_by_name('videoTee_'+n)
		xvimagesink = pipeline.get_by_name('xvimagesink_'+n)
		xvimagesink.set_property("sync", False)

		picQueue = pipeline.get_by_name('picQueue_'+n)
		picQueue.set_property("leaky", True)
		picQueue.set_property("max-size-buffers", 1)
		picFakesink = pipeline.get_by_name("picFakesink_"+n)
		picFakesink.connect("handoff", self.copyPic)
		picFakesink.set_property("signal-handoffs", True)
		self.picExposureOpen = False

		movieQueue = pipeline.get_by_name("movieQueue_"+n)
		movieFilesink = pipeline.get_by_name("movieFilesink_"+n)
		movieFilesink.set_property("location", "/home/olpc/output_"+n+".ogg")

		audioFilesink = pipeline.get_by_name('audioFilesink_'+n)
		audioFilesink.set_property("location", "/home/olpc/output_"+n+".wav")
		audioTee = pipeline.get_by_name('audioTee_'+n)
		audioWavenc = pipeline.get_by_name('audioWavenc_'+n)

		audioTee.unlink(audioWavenc)
		videoTee.unlink(movieQueue)
		videoTee.unlink(picQueue)

		bus = pipeline.get_bus()
		bus.enable_sync_message_emission()
		bus.add_signal_watch()
		self.SYNC_ID = bus.connect('sync-message::element', self.onSyncMessage)

		self.pipes.append(pipeline)

	def takePic(self):
		if not(self.picExposureOpen):
			self.picExposureOpen = True
			self.el("videoTee").link(self.el("picQueue"))

	def copyPic(self, fsink, buffer, pad, user_data=None):
		if (self.picExposureOpen):
			self.picExposureOpen = False
			pic = gtk.gdk.pixbuf_loader_new_with_mime_type("image/jpeg")
			pic.write( buffer )
			pic.close()
			pixBuf = pic.get_pixbuf()
			del pic

			self.el("videoTee").unlink(self.el("picQueue"))

			gobject.idle_add(self.savePic, pixBuf)

	def savePic(self, pixbuf):
		self._pop._c.setPic(pixbuf)

	def startRecordingVideo(self):
		self.pipe().set_state(gst.STATE_READY)
		self.record = True
		self.audio = True
		if (self.record):
			self.el("videoTee").link(self.el("movieQueue"))
			if (self.audio):
				self.el("audioTee").link(self.el("audioWavenc"))

		self.pipe().set_state(gst.STATE_PLAYING)

	def stopRecordingVideo(self):
		self.pipe().set_state(gst.STATE_NULL)
		self.nextPipe()

		if ( len(self.thumbPipes) > 0 ):
			thumbline = self.thumbPipes[len(self.thumbPipes)-1]
			n = str(len(self.thumbPipes)-1)
			thumbline.get_by_name( "thumbFakesink_"+n ).disconnect( self.THUMB_HANDOFF )

		n = str(len(self.thumbPipes))
		thumbline = gst.parse_launch('filesrc location=/home/olpc/output_'+n+'.ogg name=thumbFilesrc_'+n+' ! oggdemux name=thumbOggdemux_'+n+' ! theoradec name=thumbTheoradec_'+n+' ! tee name=thumbTee_'+n+' ! queue name=thumbQueue_'+n+' ! ffmpegcolorspace name=thumbFfmpegcolorspace_'+n+ ' ! jpegenc name=thumbJPegenc_'+n+' ! fakesink name=thumbFakesink_'+n)
		thumbQueue = thumbline.get_by_name('thumbQueue_'+n)
		thumbQueue.set_property("leaky", True)
		thumbQueue.set_property("max-size-buffers", 1)
		thumbTee = thumbline.get_by_name('thumbTee_'+n)
		thumbFakesink = thumbline.get_by_name("thumbFakesink_"+n)
		self.THUMB_HANDOFF = thumbFakesink.connect("handoff", self.copyThumbPic)
		thumbFakesink.set_property("signal-handoffs", True)
		self.thumbPipes.append(thumbline)
		self.thumbExposureOpen = True
		thumbline.set_state(gst.STATE_PLAYING)

	def copyThumbPic(self, fsink, buffer, pad, user_data=None):
		if (self.thumbExposureOpen):
			self.thumbExposureOpen = False
			pic = gtk.gdk.pixbuf_loader_new_with_mime_type("image/jpeg")
			pic.write(buffer)
			pic.close()
			self.thumbBuf = pic.get_pixbuf()
			del pic
			self.thumbEl('thumbTee').unlink(self.thumbEl('thumbQueue'))

			if (self.audio):
				if ( len(self.muxPipes) > 0 ):
					self.muxPipe().get_bus().disable_sync_message_emission()
					self.muxPipe().get_bus().disconnect(self.MUX_MESSAGE_ID)
					self.muxPipe().get_bus().remove_signal_watch()

				n = str(len(self.muxPipes))
				muxline = gst.parse_launch('filesrc location=/home/olpc/output_'+n+'.ogg name=muxVideoFilesrc_'+n+' ! oggdemux name=muxOggdemux_'+n+' ! theoradec name=muxTheoradec_'+n+' ! theoraenc name=muxTheoraenc_'+n+' ! oggmux name=muxOggmux_'+n+' ! filesink location=/home/olpc/mux.ogg name=muxFilesink_'+n+' filesrc location=/home/olpc/output_'+n+'.wav name=muxAudioFilesrc_'+n+' ! wavparse name=muxWavparse_'+n+' ! audioconvert name=muxAudioconvert_'+n+' ! vorbisenc name=muxVorbisenc_'+n+' ! muxOggmux_'+n+'.')
				muxBus = muxline.get_bus()
				muxBus.enable_sync_message_emission()
				muxBus.add_signal_watch()
				self.MUX_MESSAGE_ID = muxBus.connect('message', self.onMuxedMessage)
				self.muxPipes.append(muxline)
				muxline.set_state(gst.STATE_PLAYING)
			else:
				self.record = False
				self.audio = False
				self._pop._c.setVid(self.thumbBuf, "/home/olpc/output_"+n+".ogg")
				self._pop._c.stoppedRecordingVideo()

	def onMuxedMessage(self, bus, message):
		t = message.type
		if (t == gst.MESSAGE_EOS):
			self.record = False
			self.audio = False
			self.muxPipe().set_state(gst.STATE_NULL)

			n = str(len(self.muxPipes)-1)
			os.remove(os.path.abspath("/home/olpc/output_"+n+".wav"))
			os.remove(os.path.abspath("/home/olpc/output_"+n+".ogg"))
			self._pop._c.setVid(self.thumbBuf, "/home/olpc/mux.ogg")
			self._pop._c.stoppedRecordingVideo()

	def onSyncMessage(self, bus, message):
		if message.structure is None:
			return
		if message.structure.get_name() == 'prepare-xwindow-id':
			self._pop.set_sink(message.src)
			message.src.set_property('force-aspect-ratio', True)

	def showLiveVideo(self):
		self.el('audioTee').unlink(self.el('audioWavenc'))
		self.el('videoTee').unlink(self.el('movieQueue'))
		self.el('videoTee').unlink(self.el('picQueue'))
		self.pipe().set_state(gst.STATE_PLAYED)

class LiveVideoSlot(gtk.EventBox):

	def __init__(self, pc):
		gtk.EventBox.__init__(self)

		self._c = pc
		self._c._livevideo = self

		self.imagesink = None
		self.unset_flags(gtk.DOUBLE_BUFFERED)
		self.playa = Glive(self)
 
	def set_sink(self, sink):
		if (self.imagesink != None):
			self.imagesink = None
			del self.imagesink

		self.imagesink = sink
		self.imagesink.set_xwindow_id(self.window.xid)
