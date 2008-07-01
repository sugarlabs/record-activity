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

class Glive:
	def __init__(self, pca):
		self.window = None
		self.ca = pca

		self.playing = False
		self.picExposureOpen = False

		self.AUDIO_TRANSCODE_ID = 0
		self.TRANSCODE_ID = 0
		self.VIDEO_TRANSCODE_ID = 0

		self.PHOTO_MODE_PHOTO = 0
		self.PHOTO_MODE_AUDIO = 1

		self.TRANSCODE_UPDATE_INTERVAL = 200


		self.VIDEO_WIDTH_SMALL = 160
		self.VIDEO_HEIGHT_SMALL = 120
		self.VIDEO_FRAMERATE_SMALL = 10

		self.VIDEO_WIDTH_LARGE = 200
		self.VIDEO_HEIGHT_LARGE = 150
		self.VIDEO_FRAMERATE_SMALL = 10

		self.pipeline = gst.Pipeline("my-pipeline")
		self.createPhotoBin()
		self.createAudioBin()
		self.createVideoBin()
		self.createPipeline()

		self.thumbPipes = []
		self.muxPipes = []

		bus = self.pipeline.get_bus()
		bus.enable_sync_message_emission()
		bus.add_signal_watch()
		self.SYNC_ID = bus.connect('sync-message::element', self._onSyncMessageCb)
		self.MESSAGE_ID = bus.connect('message', self._onMessageCb)

	def createPhotoBin ( self ):
		queue = gst.element_factory_make("queue", "pbqueue")
		queue.set_property("leaky", True)
		queue.set_property("max-size-buffers", 1)

		colorspace = gst.element_factory_make("ffmpegcolorspace", "pbcolorspace")
		jpeg = gst.element_factory_make("jpegenc", "pbjpeg")

		sink = gst.element_factory_make("fakesink", "pbsink")
		self.HANDOFF_ID = sink.connect("handoff", self.copyPic)
		sink.set_property("signal-handoffs", True)

		self.photobin = gst.Bin("photobin")
		self.photobin.add(queue, colorspace, jpeg, sink)

		gst.element_link_many(queue, colorspace, jpeg, sink)

		pad = queue.get_static_pad("sink")
		self.photobin.add_pad(gst.GhostPad("sink", pad))

	def createAudioBin ( self ):
		src = gst.element_factory_make("alsasrc", "absrc")
		srccaps = gst.Caps("audio/x-raw-int,rate=16000,channels=1,depth=16")

		enc = gst.element_factory_make("wavenc", "abenc")

		sink = gst.element_factory_make("filesink", "absink")
		sink.set_property("location", os.path.join(Instance.instancePath, "output.wav"))

		self.audiobin = gst.Bin("audiobin")
		self.audiobin.add(src, enc, sink)

		src.link(enc, srccaps)
		enc.link(sink)

	def createVideoBin ( self ):
		queue = gst.element_factory_make("queue", "vbqueue")

		rate = gst.element_factory_make("videorate", "vbrate")
		ratecaps = gst.Caps('video/x-raw-yuv,framerate='+str(self.VIDEO_FRAMERATE_SMALL)+'/1')

		scale = gst.element_factory_make("videoscale", "vbscale")
		scalecaps = gst.Caps('video/x-raw-yuv,width='+str(self.VIDEO_WIDTH_SMALL)+',height='+str(self.VIDEO_HEIGHT_SMALL))

		colorspace = gst.element_factory_make("ffmpegcolorspace", "vbcolorspace")

		enc = gst.element_factory_make("theoraenc", "vbenc")
		enc.set_property("quality", 16)

		mux = gst.element_factory_make("oggmux", "vbmux")

		sink = gst.element_factory_make("filesink", "vbfile")
		sink.set_property("location", os.path.join(Instance.instancePath, "output.ogg"))

		self.videobin = gst.Bin("videobin")
		self.videobin.add(queue, rate, scale, colorspace, enc, mux, sink)

		queue.link(rate)
		rate.link(scale, ratecaps)
		scale.link(colorspace, scalecaps)
		gst.element_link_many(colorspace, enc, mux, sink)

		pad = queue.get_static_pad("sink")
		self.videobin.add_pad(gst.GhostPad("sink", pad))

	def createPipeline ( self ):
		src = gst.element_factory_make("v4l2src", "camsrc")
		src.set_property("queue-size", 2)
		tee = gst.element_factory_make("tee", "tee")
		queue = gst.element_factory_make("queue", "dispqueue")
		xvsink = gst.element_factory_make("xvimagesink", "xvsink")
		self.pipeline.add(src, tee, queue, xvsink)
		gst.element_link_many(src, tee, queue, xvsink)

	def thumbPipe(self):
		return self.thumbPipes[ len(self.thumbPipes)-1 ]


	def thumbEl(self, name):
		return self.thumbPipe().get_by_name(name)


	def muxPipe(self):
		return self.muxPipes[ len(self.muxPipes)-1 ]


	def muxEl(self, name):
		return self.muxPipe().get_by_name(name)


	def play(self):
		self.playing = True

	def pause(self):
		self.pipe().set_state(gst.STATE_PAUSED)
		self.playing = False


	def stop(self):
		self.pipeline.set_state(gst.STATE_NULL)
		self.playing = False

	def is_playing(self):
		return self.playing

	def idlePlayElement(self, element):
		element.set_state(gst.STATE_PLAYING)
		return False

	def stopRecordingAudio( self ):
		self.audiobin.set_state(gst.STATE_NULL)
		self.pipeline.remove(self.audiobin)
		gobject.idle_add( self.stoppedRecordingAudio )


	def stoppedRecordingVideo(self):
		if ( len(self.thumbPipes) > 0 ):
			thumbline = self.thumbPipes[len(self.thumbPipes)-1]
			thumbline.get_by_name('thumbFakesink').disconnect(self.THUMB_HANDOFF_ID)

		oggFilepath = os.path.join(Instance.instancePath, "output.ogg") #ogv
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

		line = 'filesrc location=' + str(oggFilepath) + ' name=thumbFilesrc ! oggdemux name=thumbOggdemux ! theoradec name=thumbTheoradec ! tee name=thumbTee ! queue name=thumbQueue ! ffmpegcolorspace name=thumbFfmpegcolorspace ! jpegenc name=thumbJPegenc ! fakesink name=thumbFakesink'
		thumbline = gst.parse_launch(line)
		thumbQueue = thumbline.get_by_name('thumbQueue')
		thumbQueue.set_property("leaky", True)
		thumbQueue.set_property("max-size-buffers", 1)
		thumbTee = thumbline.get_by_name('thumbTee')
		thumbFakesink = thumbline.get_by_name('thumbFakesink')
		self.THUMB_HANDOFF_ID = thumbFakesink.connect("handoff", self.copyThumbPic)
		thumbFakesink.set_property("signal-handoffs", True)
		self.thumbPipes.append(thumbline)
		self.thumbExposureOpen = True
		gobject.idle_add( self.idlePlayElement, thumbline )


	def stoppedRecordingAudio( self ):
		record.Record.log.debug("stoppedRecordingAudio")
		if (self.audioPixbuf != None):
			audioFilepath = os.path.join(Instance.instancePath, "output.wav")#self.el("audioFilesink").get_property("location")
			if (not os.path.exists(audioFilepath)):
				self.record = False
				self.audio = False
				self.ca.m.cannotSaveVideo()
				return
			wavSize = os.path.getsize(audioFilepath)
			if (wavSize <= 0):
				self.record = False
				self.ca.m.cannotSaveVideo()
				return

			self.ca.ui.setPostProcessPixBuf(self.audioPixbuf)

			line = 'filesrc location=' + str(audioFilepath) + ' name=audioFilesrc ! wavparse name=audioWavparse ! audioconvert name=audioAudioconvert ! vorbisenc name=audioVorbisenc ! oggmux name=audioOggmux ! filesink name=audioFilesink'
			audioline = gst.parse_launch(line)

			taglist = self.getTags(Constants.TYPE_AUDIO)
			base64AudioSnapshot = utils.getStringFromPixbuf(self.audioPixbuf)
			taglist[gst.TAG_EXTENDED_COMMENT] = "coverart="+str(base64AudioSnapshot)
			vorbisEnc = audioline.get_by_name('audioVorbisenc')
			vorbisEnc.merge_tags(taglist, gst.TAG_MERGE_REPLACE_ALL)

			audioFilesink = audioline.get_by_name('audioFilesink')
			audioOggFilepath = os.path.join(Instance.instancePath, "output.ogg")
			audioFilesink.set_property("location", audioOggFilepath )

			audioBus = audioline.get_bus()
			audioBus.add_signal_watch()
			self.AUDIO_TRANSCODE_ID = audioBus.connect('message', self._onMuxedAudioMessageCb, audioline)
			self.TRANSCODE_ID = gobject.timeout_add(self.TRANSCODE_UPDATE_INTERVAL, self._transcodeUpdateCb, audioline)
			gobject.idle_add( self.idlePlayElement, audioline )
		else:
			self.record = False
			self.audio = False
			self.ca.m.cannotSaveVideo()


	def getTags( self, type ):
		tl = gst.TagList()
		tl[gst.TAG_ARTIST] = str(Instance.nickName)
		tl[gst.TAG_COMMENT] = "olpc"
		#this is unfortunately, unreliable
		#record.Record.log.debug("self.ca.metadata['title']->" + str(self.ca.metadata['title']) )
		tl[gst.TAG_ALBUM] = "olpc" #self.ca.metadata['title']
		tl[gst.TAG_DATE] = utils.getDateString(int(time.time()))
		stringType = Constants.mediaTypes[type][Constants.keyIstr]
		tl[gst.TAG_TITLE] = Constants.istrBy % {"1":stringType, "2":str(Instance.nickName)}
		return tl

	def blockedCb(self, x, y, z):
		pass

	def _takePhoto(self):
		if self.picExposureOpen:
			return

		self.picExposureOpen = True
		pad = self.photobin.get_static_pad("sink")
		pad.set_blocked_async(True, self.blockedCb, None)
		self.pipeline.add(self.photobin)
		self.photobin.set_state(gst.STATE_PLAYING)
		self.pipeline.get_by_name("tee").link(self.photobin)
		pad.set_blocked_async(False, self.blockedCb, None)

	def takePhoto(self):
		self.photoMode = self.PHOTO_MODE_PHOTO
		self._takePhoto()

	def copyPic(self, fsink, buffer, pad, user_data=None):
		if not self.picExposureOpen:
			return

		pad = self.photobin.get_static_pad("sink")
		pad.set_blocked_async(True, self.blockedCb, None)
		self.pipeline.get_by_name("tee").unlink(self.photobin)
		self.pipeline.remove(self.photobin)
		pad.set_blocked_async(False, self.blockedCb, None)

		self.picExposureOpen = False
		pic = gtk.gdk.pixbuf_loader_new_with_mime_type("image/jpeg")
		pic.write( buffer )
		pic.close()
		pixBuf = pic.get_pixbuf()
		del pic

		self.savePhoto( pixBuf )


	def savePhoto(self, pixbuf):
		if self.photoMode == self.PHOTO_MODE_AUDIO:
			self.audioPixbuf = pixbuf
		else:
			self.ca.m.savePhoto(pixbuf)


	def startRecordingVideo(self):
		self.record = True
		self.audio = True

		pad = self.videobin.get_static_pad("sink")
		pad.set_blocked_async(True, self.blockedCb, None)
		self.pipeline.add(self.videobin)
		self.videobin.set_state(gst.STATE_PLAYING)
		self.pipeline.get_by_name("tee").link(self.videobin)
		pad.set_blocked_async(False, self.blockedCb, None)

		self.pipeline.add(self.audiobin)
		self.audiobin.set_state(gst.STATE_PLAYING)

	def startRecordingAudio(self):
		self.audioPixbuf = None

		self.photoMode = self.PHOTO_MODE_AUDIO
		self._takePhoto()

		self.record = True
		self.pipeline.add(self.audiobin)
		self.audiobin.set_state(gst.STATE_PLAYING)

	def stopRecordingVideo(self):
		self.audiobin.set_state(gst.STATE_NULL)
		self.videobin.set_state(gst.STATE_NULL)
		pad = self.videobin.get_static_pad("sink")
		pad.set_blocked_async(True, self.blockedCb, None)
		self.pipeline.get_by_name("tee").unlink(self.videobin)
		self.pipeline.remove(self.videobin)
		pad.set_blocked_async(False, self.blockedCb, None)
		self.pipeline.remove(self.audiobin)
		gobject.idle_add( self.stoppedRecordingVideo )


	def copyThumbPic(self, fsink, buffer, pad, user_data=None):
		if (self.thumbExposureOpen):
			self.thumbExposureOpen = False
			pic = gtk.gdk.pixbuf_loader_new_with_mime_type("image/jpeg")
			pic.write(buffer)
			pic.close()
			self.thumbBuf = pic.get_pixbuf()
			del pic
			self.thumbEl('thumbTee').unlink(self.thumbEl('thumbQueue'))

			oggFilepath = os.path.join(Instance.instancePath, "output.ogg") #ogv
			if (self.audio):
				self.ca.ui.setPostProcessPixBuf(self.thumbBuf)

				wavFilepath = os.path.join(Instance.instancePath, "output.wav")
				muxFilepath = os.path.join(Instance.instancePath, "mux.ogg") #ogv

				muxline = gst.parse_launch('filesrc location=' + str(oggFilepath) + ' name=muxVideoFilesrc ! oggdemux name=muxOggdemux ! theoradec name=muxTheoradec ! theoraenc name=muxTheoraenc ! oggmux name=muxOggmux ! filesink location=' + str(muxFilepath) + ' name=muxFilesink filesrc location=' + str(wavFilepath) + ' name=muxAudioFilesrc ! wavparse name=muxWavparse ! audioconvert name=muxAudioconvert ! vorbisenc name=muxVorbisenc ! muxOggmux.')
				taglist = self.getTags(Constants.TYPE_VIDEO)
				vorbisEnc = muxline.get_by_name('muxVorbisenc')
				vorbisEnc.merge_tags(taglist, gst.TAG_MERGE_REPLACE_ALL)

				muxBus = muxline.get_bus()
				muxBus.add_signal_watch()
				self.VIDEO_TRANSCODE_ID = muxBus.connect('message', self._onMuxedVideoMessageCb, muxline)
				self.muxPipes.append(muxline)
				#add a listener here to monitor % of transcoding...
				self.TRANSCODE_ID = gobject.timeout_add(self.TRANSCODE_UPDATE_INTERVAL, self._transcodeUpdateCb, muxline)
				muxline.set_state(gst.STATE_PLAYING)
			else:
				self.record = False
				self.audio = False
				self.ca.m.saveVideo(self.thumbBuf, str(oggFilepath), self.VIDEO_WIDTH_SMALL, self.VIDEO_HEIGHT_SMALL)
				self.ca.m.stoppedRecordingVideo()


	def _transcodeUpdateCb( self, pipe ):
		position, duration = self.queryPosition( pipe )
		if position != gst.CLOCK_TIME_NONE:
			value = position * 100.0 / duration
			value = value/100.0
			self.ca.ui.progressWindow.updateProgress(value, Constants.istrSaving)
		return True


	def queryPosition( self, pipe ):
		try:
			position, format = pipe.query_position(gst.FORMAT_TIME)
		except:
			position = gst.CLOCK_TIME_NONE

		try:
			duration, format = pipe.query_duration(gst.FORMAT_TIME)
		except:
			duration = gst.CLOCK_TIME_NONE

		return (position, duration)


	def _onMuxedVideoMessageCb(self, bus, message, pipe):
		t = message.type
		if (t == gst.MESSAGE_EOS):
			self.record = False
			self.audio = False
			gobject.source_remove(self.VIDEO_TRANSCODE_ID)
			self.VIDEO_TRANSCODE_ID = 0
			gobject.source_remove(self.TRANSCODE_ID)
			self.TRANSCODE_ID = 0
			pipe.set_state(gst.STATE_NULL)
			pipe.get_bus().remove_signal_watch()
			pipe.get_bus().disable_sync_message_emission()

			wavFilepath = os.path.join(Instance.instancePath, "output.wav")
			oggFilepath = os.path.join(Instance.instancePath, "output.ogg") #ogv
			muxFilepath = os.path.join(Instance.instancePath, "mux.ogg") #ogv
			os.remove( wavFilepath )
			os.remove( oggFilepath )
			self.ca.m.saveVideo(self.thumbBuf, str(muxFilepath), self.VIDEO_WIDTH_SMALL, self.VIDEO_HEIGHT_SMALL)
			self.ca.m.stoppedRecordingVideo()
			return False
		else:
			return True


	def _onMuxedAudioMessageCb(self, bus, message, pipe):
		t = message.type
		if (t == gst.MESSAGE_EOS):
			record.Record.log.debug("audio gst.MESSAGE_EOS")
			self.record = False
			self.audio = False
			gobject.source_remove(self.AUDIO_TRANSCODE_ID)
			self.AUDIO_TRANSCODE_ID = 0
			gobject.source_remove(self.TRANSCODE_ID)
			self.TRANSCODE_ID = 0
			pipe.set_state(gst.STATE_NULL)
			pipe.get_bus().remove_signal_watch()
			pipe.get_bus().disable_sync_message_emission()

			wavFilepath = os.path.join(Instance.instancePath, "output.wav")
			oggFilepath = os.path.join(Instance.instancePath, "output.ogg")
			os.remove( wavFilepath )
			self.ca.m.saveAudio(oggFilepath, self.audioPixbuf)
			return False
		else:
			return True


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

	def abandonMedia(self):
		self.stop()

		if (self.AUDIO_TRANSCODE_ID != 0):
			gobject.source_remove(self.AUDIO_TRANSCODE_ID)
			self.AUDIO_TRANSCODE_ID = 0
		if (self.TRANSCODE_ID != 0):
			gobject.source_remove(self.TRANSCODE_ID)
			self.TRANSCODE_ID = 0
		if (self.VIDEO_TRANSCODE_ID != 0):
			gobject.source_remove(self.VIDEO_TRANSCODE_ID)
			self.VIDEO_TRANSCODE_ID = 0

		wavFilepath = os.path.join(Instance.instancePath, "output.wav")
		if (os.path.exists(wavFilepath)):
			os.remove(wavFilepath)
		oggFilepath = os.path.join(Instance.instancePath, "output.ogg") #ogv
		if (os.path.exists(oggFilepath)):
			os.remove(oggFilepath)
		muxFilepath = os.path.join(Instance.instancePath, "mux.ogg") #ogv
		if (os.path.exists(muxFilepath)):
			os.remove(muxFilepath)


class LiveVideoWindow(gtk.Window):
	def __init__(self, bgd ):
		gtk.Window.__init__(self)

		self.imagesink = None
		self.glive = None

		self.modify_bg( gtk.STATE_NORMAL, bgd )
		self.modify_bg( gtk.STATE_INSENSITIVE, bgd )
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
