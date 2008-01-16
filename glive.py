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
		self.pipes = []

		self.playing = False

		self.AUDIO_TRANSCODE_ID = 0
		self.TRANSCODE_ID = 0
		self.VIDEO_TRANSCODE_ID = 0

		self.PIPETYPE_SUGAR_JHBUILD = 0
		self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD = 1
		self.PIPETYPE_X_VIDEO_DISPLAY = 2
		self.PIPETYPE_AUDIO_RECORD = 3
		self._PIPETYPE = self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD
		self._LAST_PIPETYPE = self._PIPETYPE
		self._NEXT_PIPETYPE = -1

		self.TRANSCODE_UPDATE_INTERVAL = 200


		self.VIDEO_WIDTH_SMALL = 160
		self.VIDEO_HEIGHT_SMALL = 120
		self.VIDEO_FRAMERATE_SMALL = 10

		self.VIDEO_WIDTH_LARGE = 200
		self.VIDEO_HEIGHT_LARGE = 150
		self.VIDEO_FRAMERATE_SMALL = 10


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
		return self.pipe().get_by_name(name)


	def thumbPipe(self):
		return self.thumbPipes[ len(self.thumbPipes)-1 ]


	def thumbEl(self, name):
		return self.thumbPipe().get_by_name(name)


	def muxPipe(self):
		return self.muxPipes[ len(self.muxPipes)-1 ]


	def muxEl(self, name):
		return self.muxPipe().get_by_name(name)


	def play(self):
		self.pipe().set_state(gst.STATE_PLAYING)
		self.playing = True


	def pause(self):
		self.pipe().set_state(gst.STATE_PAUSED)
		self.playing = False


	def stop(self):
		self.pipe().set_state(gst.STATE_NULL)
		self.playing = False

		self._LAST_PIPETYPE = self._PIPETYPE
		if (self._NEXT_PIPETYPE != -1):
			self._PIPETYPE = self._NEXT_PIPETYPE
		self._nextPipe()
		self._NEXT_PIPETYPE = -1

		#import time
		#print("stop...", int(time.time()))


	def is_playing(self):
		return self.playing


	def _nextPipe(self):
		if ( len(self.pipes) > 0 ):

			pipe = self.pipe()
			bus = pipe.get_bus()
			n = len(self.pipes)-1
			n = str(n)

			#only disconnect what was connected based on the last pipetype
			if ((self._LAST_PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD)
			or (self._LAST_PIPETYPE == self.PIPETYPE_X_VIDEO_DISPLAY)
			or (self._LAST_PIPETYPE == self.PIPETYPE_AUDIO_RECORD) ):
				bus.disconnect(self.SYNC_ID)
				bus.remove_signal_watch()
				bus.disable_sync_message_emission()
				if (self._LAST_PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD):
					pipe.get_by_name("picFakesink").disconnect(self.HANDOFF_ID)
				if (self._LAST_PIPETYPE == self.PIPETYPE_AUDIO_RECORD):
					pipe.get_by_name("picFakesink").disconnect(self.HANDOFF_ID)

		v4l2 = False
		if (self._PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD):
			pipeline = gst.parse_launch("v4l2src name=v4l2src ! tee name=videoTee ! queue name=movieQueue ! videorate name=movieVideorate ! video/x-raw-yuv,framerate="+str(self.VIDEO_FRAMERATE_SMALL)+"/1 ! videoscale name=movieVideoscale ! video/x-raw-yuv,width="+str(self.VIDEO_WIDTH_SMALL)+",height="+str(self.VIDEO_HEIGHT_SMALL)+" ! ffmpegcolorspace name=movieFfmpegcolorspace ! theoraenc quality=16 name=movieTheoraenc ! oggmux name=movieOggmux ! filesink name=movieFilesink videoTee. ! xvimagesink name=xvimagesink videoTee. ! queue name=picQueue ! ffmpegcolorspace name=picFfmpegcolorspace ! jpegenc name=picJPegenc ! fakesink name=picFakesink alsasrc name=audioAlsasrc ! audio/x-raw-int,rate=16000,channels=1,depth=16 ! tee name=audioTee ! wavenc name=audioWavenc ! filesink name=audioFilesink audioTee. ! fakesink name=audioFakesink" )
			v4l2 = True

			videoTee = pipeline.get_by_name('videoTee')

			picQueue = pipeline.get_by_name('picQueue')
			picQueue.set_property("leaky", True)
			picQueue.set_property("max-size-buffers", 1)
			picFakesink = pipeline.get_by_name("picFakesink")
			self.HANDOFF_ID = picFakesink.connect("handoff", self.copyPic)
			picFakesink.set_property("signal-handoffs", True)
			self.picExposureOpen = False

			movieQueue = pipeline.get_by_name("movieQueue")
			movieFilesink = pipeline.get_by_name("movieFilesink")
			movieFilepath = os.path.join(Instance.instancePath, "output.ogg" ) #ogv
			movieFilesink.set_property("location", movieFilepath )

			audioFilesink = pipeline.get_by_name('audioFilesink')
			audioFilepath = os.path.join(Instance.instancePath, "output.wav")
			audioFilesink.set_property("location", audioFilepath )
			audioTee = pipeline.get_by_name('audioTee')
			audioWavenc = pipeline.get_by_name('audioWavenc')

			audioTee.unlink(audioWavenc)
			videoTee.unlink(movieQueue)
			videoTee.unlink(picQueue)

		elif (self._PIPETYPE == self.PIPETYPE_X_VIDEO_DISPLAY ):
			pipeline = gst.parse_launch("v4l2src name=v4l2src ! queue name=xQueue ! videorate ! video/x-raw-yuv,framerate=2/1 ! videoscale ! video/x-raw-yuv,width="+str(ui.UI.dim_PIPW)+",height="+str(ui.UI.dim_PIPH)+" ! ffmpegcolorspace ! ximagesink name=ximagesink")
			v4l2 = True

		elif (self._PIPETYPE == self.PIPETYPE_AUDIO_RECORD):
			pipeline = gst.parse_launch("v4l2src name=v4l2src ! tee name=videoTee ! xvimagesink name=xvimagesink videoTee. ! queue name=picQueue ! ffmpegcolorspace name=picFfmpegcolorspace ! jpegenc name=picJPegenc ! fakesink name=picFakesink alsasrc name=audioAlsasrc ! audio/x-raw-int,rate=16000,channels=1,depth=16 ! queue name=audioQueue ! audioconvert name=audioAudioconvert ! wavenc name=audioWavenc ! filesink name=audioFilesink" )
			v4l2 = True

			audioQueue = pipeline.get_by_name('audioQueue')
			audioAudioconvert = pipeline.get_by_name('audioAudioconvert')
			audioQueue.unlink(audioAudioconvert)

			videoTee = pipeline.get_by_name('videoTee')
			picQueue = pipeline.get_by_name('picQueue')
			picQueue.set_property("leaky", True)
			picQueue.set_property("max-size-buffers", 1)
			picFakesink = pipeline.get_by_name('picFakesink')
			self.HANDOFF_ID = picFakesink.connect("handoff", self.copyPic)
			picFakesink.set_property("signal-handoffs", True)
			self.picExposureOpen = False
			videoTee.unlink(picQueue)

			audioFilesink = pipeline.get_by_name('audioFilesink')
			audioFilepath = os.path.join(Instance.instancePath, "output.wav")
			audioFilesink.set_property("location", audioFilepath )

		elif (self._PIPETYPE == self.PIPETYPE_SUGAR_JHBUILD):
			pipeline = gst.parse_launch("fakesrc ! queue name=xQueue ! videorate ! video/x-raw-yuv,framerate=2/1 ! videoscale ! video/x-raw-yuv,width=160,height=120 ! ffmpegcolorspace ! ximagesink name=ximagesink")

		if (v4l2):
			v4l2src = pipeline.get_by_name('v4l2src')
			try:
				v4l2src.set_property("queue-size", 2)
			except:
				pass

		if ((self._PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD)
		or (self._PIPETYPE == self.PIPETYPE_X_VIDEO_DISPLAY)
		or (self._PIPETYPE == self.PIPETYPE_AUDIO_RECORD)):
			bus = pipeline.get_bus()
			bus.enable_sync_message_emission()
			bus.add_signal_watch()
			self.SYNC_ID = bus.connect('sync-message::element', self._onSyncMessageCb)
			self.MESSAGE_ID = bus.connect('message', self._onMessageCb)

		self.pipes.append(pipeline)


	def stopRecordingAudio( self ):
		self.stop()
		gobject.idle_add( self.stoppedRecordingAudio )


	def stoppedRecordingVideo(self):
		if ( len(self.thumbPipes) > 0 ):
			thumbline = self.thumbPipes[len(self.thumbPipes)-1]
			n = str(len(self.thumbPipes)-1)
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
		gobject.idle_add( thumbline.set_state, gst.STATE_PLAYING )


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
			vorbisEnc.merge_tags(taglist, gst.TAG_REPLACE_ALL)

			audioFilesink = audioline.get_by_name('audioFilesink')
			audioOggFilepath = os.path.join(Instance.instancePath, "output.ogg")
			audioFilesink.set_property("location", audioOggFilepath )

			audioBus = audioline.get_bus()
			audioBus.add_signal_watch()
			self.AUDIO_TRANSCODE_ID = audioBus.connect('message', self._onMuxedAudioMessageCb, audioline)
			self.TRANSCODE_ID = gobject.timeout_add(self.TRANSCODE_UPDATE_INTERVAL, self._transcodeUpdateCb, audioline)
			gobject.idle_add( audioline.set_state, gst.STATE_PLAYING )
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
			self.savePhoto( pixBuf )


	def savePhoto(self, pixbuf):
		if (self._PIPETYPE == self.PIPETYPE_AUDIO_RECORD):
			self.audioPixbuf = pixbuf
		else:
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
		self.audioPixbuf = None
		self.pipe().set_state(gst.STATE_READY)

		self.takePhoto()

		self.record = True
		if (self.record):
			self.el("audioQueue").link(self.el("audioAudioconvert"))

		self.pipe().set_state(gst.STATE_PLAYING)


	def stopRecordingVideo(self):
		self.stop()
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
				vorbisEnc.merge_tags(taglist, gst.TAG_REPLACE_ALL)

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
			pipe.get_bus().disable_sync_message_emission()
			pipe.get_bus().remove_signal_watch()

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
			pipe.get_bus().disable_sync_message_emission()
			pipe.get_bus().remove_signal_watch()

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


	def isXv(self):
		return self._PIPETYPE == self.PIPETYPE_XV_VIDEO_DISPLAY_RECORD


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
