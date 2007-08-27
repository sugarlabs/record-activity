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
	def __init__(self, pca):
		self.window = None
		self.ca = pca
		self.pipes = []

		self.PIPETYPE_SUGAR_JHBUILD = 0
		self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD = 1
		self.PIPETYPE_X_VIDEO_DISPLAY = 2
		self.PIPETYPE_AUDIO_RECORD = 3
		self._PIPETYPE = self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD
		self._LAST_PIPETYPE = self._PIPETYPE
		self._NEXT_PIPETYPE = -1
		#todo: create a dictionary here of what pipetypes have, e.g., "v4l2", "video", etc.

		self.thumbPipes = []
		self.muxPipes = []
		self._nextPipe()

	def setPipeType( self, type ):
		self._NEXT_PIPETYPE = type

	def getPipeType( self ):
		return self._PIPETYPE

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

	def pause(self):
		self.pipe().set_state(gst.STATE_PAUSED)

	def stop(self):
		self.pipe().set_state(gst.STATE_NULL)
		self._LAST_PIPETYPE = self._PIPETYPE
		if (self._NEXT_PIPETYPE != -1):
			self._PIPETYPE = self._NEXT_PIPETYPE
		self._nextPipe()
		self._NEXT_PIPETYPE = -1

	def _nextPipe(self):
		if ( len(self.pipes) > 0 ):
			#todo: only disconnect what was connected based on the last pipetype
			pipe = self.pipe()
			bus = pipe.get_bus()
			n = len(self.pipes)-1
			n = str(n)

			if ((self._LAST_PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD) or (self._LAST_PIPETYPE == self.PIPETYPE_X_VIDEO_DISPLAY)):
				bus.disconnect(self.SYNC_ID)
				bus.remove_signal_watch()
				bus.disable_sync_message_emission()
				if (self._LAST_PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD):
					pipe.get_by_name("picFakesink_"+n).disconnect(self.HANDOFF_ID)
			elif (self._LAST_PIPETYPE == self.PIPETYPE_AUDIO_RECORD):
				pipe.get_by_name("audioFakesink_"+n).disconnect(self.AUDIOBUFFER_ID)

		n = str(len(self.pipes))
		v4l2 = False
		if (self._PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD):
			pipeline = gst.parse_launch("v4l2src name=v4l2src_"+n+" ! tee name=videoTee_"+n+" ! queue name=movieQueue_" +n+" ! videorate name=movieVideorate_"+n+" ! video/x-raw-yuv,framerate=15/1 ! videoscale name=movieVideoscale_"+n+" ! video/x-raw-yuv,width=160,height=120 ! ffmpegcolorspace name=movieFfmpegcolorspace_"+n+" ! theoraenc quality=16 name=movieTheoraenc_"+n+" ! oggmux name=movieOggmux_"+n+" ! filesink name=movieFilesink_"+n+" videoTee_"+n+". ! xvimagesink name=xvimagesink_"+n+" videoTee_"+n+". ! queue name=picQueue_"+n+" ! ffmpegcolorspace name=picFfmpegcolorspace_"+n+" ! jpegenc name=picJPegenc_"+n+" ! fakesink name=picFakesink_"+n+" alsasrc name=audioAlsasrc_"+n+" ! audio/x-raw-int,rate=16000,channels=1,depth=16 ! tee name=audioTee_"+n +" ! wavenc name=audioWavenc_"+n+" ! filesink name=audioFilesink_"+n )
			v4l2 = True

			videoTee = pipeline.get_by_name('videoTee_'+n)

			picQueue = pipeline.get_by_name('picQueue_'+n)
			picQueue.set_property("leaky", True)
			picQueue.set_property("max-size-buffers", 1)
			picFakesink = pipeline.get_by_name("picFakesink_"+n)
			self.HANDOFF_ID = picFakesink.connect("handoff", self.copyPic)
			picFakesink.set_property("signal-handoffs", True)
			self.picExposureOpen = False

			movieQueue = pipeline.get_by_name("movieQueue_"+n)
			movieFilesink = pipeline.get_by_name("movieFilesink_"+n)
			movieFilepath = os.path.join(self.ca.tempPath, "output_"+n+".ogv" )
			movieFilesink.set_property("location", movieFilepath )

			audioFilesink = pipeline.get_by_name('audioFilesink_'+n)
			audioFilepath = os.path.join(self.ca.tempPath, "output_"+n+".wav")
			audioFilesink.set_property("location", audioFilepath )
			audioTee = pipeline.get_by_name('audioTee_'+n)
			audioWavenc = pipeline.get_by_name('audioWavenc_'+n)

			audioTee.unlink(audioWavenc)
			videoTee.unlink(movieQueue)
			videoTee.unlink(picQueue)

		elif (self._PIPETYPE == self.PIPETYPE_X_VIDEO_DISPLAY ):
			pipeline = gst.parse_launch("v4l2src name=v4l2src_"+n+" ! queue name=xQueue_"+n+" ! videorate ! video/x-raw-yuv,framerate=2/1 ! videoscale ! video/x-raw-yuv,width=160,height=120 ! ffmpegcolorspace ! ximagesink name=ximagesink_"+n)
			v4l2 = True

		elif (self._PIPETYPE == self.PIPETYPE_AUDIO_RECORD):
			pipeline = gst.parse_launch("alsasrc name=audioAlsasrc_"+n+" ! audio/x-raw-int,rate=48000,channels=1,depth=16 ! tee name=audioTee_"+n +" ! audioconvert name=audioAudioconvert_"+n +" ! vorbisenc name=audioVorbisenc_"+n+" ! oggmux name=audioOggmux_"+n+" ! filesink name=audioFilesink_"+n + " audioTee_"+n+". ! fakesink name=audioFakesink_"+n )
			audioFakesink = pipeline.get_by_name("audioFakesink_"+n)
			self.AUDIOBUFFER_ID = audioFakesink.connect( "handoff", self._audioBufferCb)
			audioFakesink.set_property("signal-handoffs", True)

			audioFilesink = pipeline.get_by_name('audioFilesink_'+n)
			audioFilepath = os.path.join(self.ca.tempPath, "output_"+n+".wav")
			audioFilesink.set_property("location", audioFilepath )

			audioTee = pipeline.get_by_name('audioTee_'+n)
			audioAudioconvert = pipeline.get_by_name('audioAudioconvert_'+n)
			audioTee.unlink(audioAudioconvert)

		elif (self._PIPETYPE == self.PIPETYPE_SUGAR_JHBUILD):
			pipeline = gst.parse_launch("fakesrc ! queue name=xQueue_"+n+" ! videorate ! video/x-raw-yuv,framerate=2/1 ! videoscale ! video/x-raw-yuv,width=160,height=120 ! ffmpegcolorspace ! ximagesink name=ximagesink_"+n)

		if (pipeline == None):
			#todo: handle this?
			print("no pipeline error!")

		if (v4l2):
			v4l2src = pipeline.get_by_name('v4l2src_'+n)
			try:
				v4l2src.set_property("queue-size", 2)
			except:
				pass

		#todo: this should be checked with an attribute library
		if ((self._PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD) or (self._PIPETYPE == self.PIPETYPE_X_VIDEO_DISPLAY)):
			bus = pipeline.get_bus()
			bus.enable_sync_message_emission()
			bus.add_signal_watch()
			self.SYNC_ID = bus.connect('sync-message::element', self.onSyncMessage)

		self.pipes.append(pipeline)


	def _audioBufferCb(self, element, buffer, pad):
		gobject.timeout_add( 30, self._audioBufferNew, str(buffer) )
		return True


	def _audioBufferNew( self, bufferString ):
		#self.emit("new-buffer", bufferString, self.draw_graph_status )
		self.ca.ui.audioCanvas.queueDisplayOfNewAudioBuffer( bufferString )
		return False



	def stopRecordingAudio( self ):
		audioFile = self.el("audioFilesink").get_property("location")
		self.stop()
		print("audioFile:", audioFile )
		self.record = False
		self.audio = False
		self.ca.m.saveAudio( audioFile)


	def takePhoto(self):
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
			gobject.idle_add(self.savePhoto, pixBuf)


	def savePhoto(self, pixbuf):
		self.ca.m.savePhoto(pixbuf)


	def startRecordingVideo(self):
		self.pipe().set_state(gst.STATE_READY)
		self.record = True
		self.audio = True
		if (self.record):
			self.el("videoTee").link(self.el("movieQueue"))
			if (self.audio):
				self.el("audioTee").link(self.el("audioWavenc"))

		self.pipe().set_state(gst.STATE_PLAYING)


	def startRecordingAudio(self):
		self.pipe().set_state(gst.STATE_READY)
		self.record = True
		#todo: not really needed, is it :-)
		self.audio = True
		if (self.record):
			self.el("audioTee").link(self.el("audioAudioconvert"))

		self.pipe().set_state(gst.STATE_PLAYING)


	def stopAudioHandoffs( self ):
		#todo: do this when switching pipelines too!
		if self._PIPETYPE == self.PIPETYPE_AUDIO_RECORD:
			thumbFakesink = self.el( "audioFakesink" )
			thumbFakesink.set_property( "signal-handoffs", False )


	def stopRecordingVideo(self):
		#sometimes we hang here because we're trying to open an empty file or nonexistant file
		self.stop()

		if ( len(self.thumbPipes) > 0 ):
			thumbline = self.thumbPipes[len(self.thumbPipes)-1]
			n = str(len(self.thumbPipes)-1)
			thumbline.get_by_name( "thumbFakesink_"+n ).disconnect( self.THUMB_HANDOFF )

		n = str(len(self.thumbPipes))
		f = str(len(self.pipes)-2)
		oggFilepath = os.path.join(self.ca.tempPath, "output_"+f+".ogv" )

		#todo: test ~~> need to check *exists* and the filesize here to prevent stalling... & maybe earlier?
		if (not os.path.exists(oggFilepath)):
			self.record = False
			self.ca.m.cannotSaveVideo()
			self.ca.m.stoppedRecordingVideo()
			return

		oggSize = os.path.getsize(oggFilepath)
		if (oggSize <= 0):
			self.record = False
			self.ca.m.cannotSaveVideo()
			self.ca.m.stoppedRecordingVideo()
			return

		line = 'filesrc location=' + str(oggFilepath) + ' name=thumbFilesrc_'+n+' ! oggdemux name=thumbOggdemux_'+n+' ! theoradec name=thumbTheoradec_'+n+' ! tee name=thumbTee_'+n+' ! queue name=thumbQueue_'+n+' ! ffmpegcolorspace name=thumbFfmpegcolorspace_'+n+ ' ! jpegenc name=thumbJPegenc_'+n+' ! fakesink name=thumbFakesink_'+n
		thumbline = gst.parse_launch(line)
		thumbQueue = thumbline.get_by_name('thumbQueue_'+n)
		thumbQueue.set_property("leaky", True)
		thumbQueue.set_property("max-size-buffers", 1)
		thumbTee = thumbline.get_by_name('thumbTee_'+n)
		thumbFakesink = thumbline.get_by_name("thumbFakesink_"+n)
		self.THUMB_HANDOFF = thumbFakesink.connect("handoff", self.copyThumbPic)
		thumbFakesink.set_property("signal-handoffs", True)
		self.thumbPipes.append(thumbline)
		self.thumbExposureOpen = True
		gobject.idle_add( thumbline.set_state, gst.STATE_PLAYING )


	def copyThumbPic(self, fsink, buffer, pad, user_data=None):
		if (self.thumbExposureOpen):
			self.thumbExposureOpen = False
			pic = gtk.gdk.pixbuf_loader_new_with_mime_type("image/jpeg")
			pic.write(buffer)
			pic.close()
			self.thumbBuf = pic.get_pixbuf()
			del pic
			self.thumbEl('thumbTee').unlink(self.thumbEl('thumbQueue'))

			n = str(len(self.muxPipes))
			f = str(len(self.pipes)-2)
			oggFilepath = os.path.join(self.ca.tempPath, "output_"+f+".ogv")
			print( n, f, oggFilepath )
			if (self.audio):
				if ( len(self.muxPipes) > 0 ):
					self.muxPipe().get_bus().disable_sync_message_emission()
					self.muxPipe().get_bus().disconnect(self.MUX_MESSAGE_ID)
					self.muxPipe().get_bus().remove_signal_watch()

				wavFilepath = os.path.join(self.ca.tempPath, "output_"+f+".wav")
				muxFilepath = os.path.join(self.ca.tempPath, "mux.ogv")
				muxline = gst.parse_launch('filesrc location=' + str(oggFilepath) + ' name=muxVideoFilesrc_'+n+' ! oggdemux name=muxOggdemux_'+n+' ! theoradec name=muxTheoradec_'+n+' ! theoraenc name=muxTheoraenc_'+n+' ! oggmux name=muxOggmux_'+n+' ! filesink location=' + str(muxFilepath) + ' name=muxFilesink_'+n+' filesrc location=' + str(wavFilepath) + ' name=muxAudioFilesrc_'+n+' ! wavparse name=muxWavparse_'+n+' ! audioconvert name=muxAudioconvert_'+n+' ! vorbisenc name=muxVorbisenc_'+n+' ! muxOggmux_'+n+'.')
				muxBus = muxline.get_bus()
				muxBus.enable_sync_message_emission()
				muxBus.add_signal_watch()
				self.MUX_MESSAGE_ID = muxBus.connect('message', self.onMuxedMessage)
				self.muxPipes.append(muxline)
				muxline.set_state(gst.STATE_PLAYING)
			else:
				self.record = False
				self.audio = False
				self.ca.m.saveVideo(self.thumbBuf, str(oggFilepath))
				self.ca.m.stoppedRecordingVideo()


	def onMuxedMessage(self, bus, message):
		t = message.type
		if (t == gst.MESSAGE_EOS):
			self.record = False
			self.audio = False
			self.muxPipe().set_state(gst.STATE_NULL)

			n = str(len(self.muxPipes)-1)
			f = str(len(self.pipes)-2)

			wavFilepath = os.path.join(self.ca.tempPath, "output_"+f+".wav")
			oggFilepath = os.path.join(self.ca.tempPath, "output_"+f+".ogv")
			muxFilepath = os.path.join(self.ca.tempPath, "mux.ogv")
			os.remove( wavFilepath )
			os.remove( oggFilepath )
			self.ca.m.saveVideo(self.thumbBuf, str(muxFilepath))
			self.ca.m.stoppedRecordingVideo()


	def onSyncMessage(self, bus, message):
		if message.structure is None:
			return
		if message.structure.get_name() == 'prepare-xwindow-id':
			self.window.set_sink(message.src)
			message.src.set_property('force-aspect-ratio', True)


	def showLiveVideo(self):
		self.el('audioTee').unlink(self.el('audioWavenc'))
		self.el('videoTee').unlink(self.el('movieQueue'))
		self.el('videoTee').unlink(self.el('picQueue'))
		self.pipe().set_state(gst.STATE_PLAYED)


	def isXv(self):
		return self._PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD


class LiveVideoWindow(gtk.Window):
	def __init__(self):
		gtk.Window.__init__(self)

		self.imagesink = None
		self.glive = None

		self.unset_flags(gtk.DOUBLE_BUFFERED)
		self.set_flags(gtk.APP_PAINTABLE)

	def set_glive(self, pglive):
		self.glive = pglive
		self.glive.window = self

	def set_sink(self, sink):
		if (self.imagesink != None):
			assert self.window.xid
			self.imagesink = None
			del self.imagesink

		self.imagesink = sink
		self.imagesink.set_xwindow_id(self.window.xid)
