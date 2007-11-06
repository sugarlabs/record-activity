import os
import gtk
from gettext import gettext as _

import sugar.graphics.style
from sugar.activity import activity

from instance import Instance
from sugar import profile
from color import Color
import utils
import _camera
import cairo
import pango
import pangocairo

class Constants:

	VERSION = 39

	SERVICE = "org.laptop.Record"
	IFACE = SERVICE
	PATH = "/org/laptop/Record"
	activityId = None

	recdTitle = "title"
	recdTime = "time"
	recdRecorderName = "photographer"
	recdRecorderHash = "recorderHash"
	recdColorStroke = "colorStroke"
	recdColorFill = "colorFill"
	recdHashKey = "hashKey"
	recdBuddy = "buddy"
	recdMediaMd5 = "mediaMd5"
	recdThumbMd5 = "thumbMd5"
	recdMediaBytes = "mediaBytes"
	recdThumbBytes = "thumbBytes"
	recdBuddyThumb = "buddyThumb"
	recdDatastoreId = "datastoreId"
	recdAudioImage = "audioImage"
	recdAlbum = "album"
	recdType = "type"
	recdRecd = "recd"
	recdRecordVersion = "version"

	keyName = "name"
	keyMime = "mime"
	keyExt = "ext"
	keyIstr = "istr"

	MODE_PHOTO = 0
	MODE_VIDEO = 1
	MODE_AUDIO = 2
	TYPE_PHOTO = MODE_PHOTO
	TYPE_VIDEO = MODE_VIDEO
	TYPE_AUDIO = MODE_AUDIO

	TIMER_0 = 0
	TIMER_5 = 5
	TIMER_10 = 10
	TIMERS = []
	TIMERS.append(TIMER_0)
	TIMERS.append(TIMER_5)
	TIMERS.append(TIMER_10)

	DURATION_15 = 15
	DURATION_30 = 30
	DURATION_45 = 45
	DURATIONS = []
	DURATIONS.append(DURATION_15)
	DURATIONS.append(DURATION_30)
	DURATIONS.append(DURATION_45)

	colorBlack = Color()
	colorBlack.init_rgba( 0, 0, 0, 255 )
	colorWhite = Color()
	colorWhite.init_rgba( 255, 255, 255, 255 )
	colorRed = Color()
	colorRed.init_rgba( 255, 0, 0, 255)
	colorGreen = Color()
	colorGreen.init_rgba( 0, 255, 0, 255)
	colorBlue = Color()
	colorBlue.init_rgba( 0, 0, 255, 255)
	colorButton = Color()
	colorButton.init_gdk( sugar.graphics.style.COLOR_BUTTON_GREY )

	gfxPath = os.path.join(activity.get_bundle_path(), "gfx")
	soundClick = os.path.join(gfxPath, 'photoShutter.wav')

	istrActivityName = _('Record')
	istrPhoto = _('Photo')
	istrVideo = _('Video')
	istrAudio = _('Audio')
	istrTimelapse = _('Time Lapse')
	istrAnimation = _('Animation')
	istrPanorama = _('Panorama')
	#TRANS: photo by photographer, e.g., "Photo by Mary"
	istrBy = _("%(1)s by %(2)s")
	istrTitle = _('Title:')
	istrRecorder = _('Recorder:')
	istrDate = _('Date:')
	istrTags = _('Tags:')
	istrSaving = _('Saving')
	istrFinishedRecording = _("Finished recording")
	istrMinutesSecondsRemaining = _("%(1)s minutes, %(1)s seconds remaining")
	istrSecondsRemaining = _("%(1)s seconds remaining")
	istrRemove = _("Remove")
	istrStoppedRecording = _("Stopped recording")
	istrCopyToClipboard = _("Copy to clipboard")
	istrTimer = _("Timer:")
	istrDuration = _("Duration:")
	istrNow = _("Immediate")
	istrSeconds = _("%(1)s seconds")
	istrMinutes = _("%(1)s minutes")
	istrPlay = _("Play")
	istrPause = _("Pause")
	istrAddFrame = _("Add frame")
	istrRemoveFrame = _("Remove frame")
	istrFramesPerSecond = _("%(1)s frames per second")
	istrQuality = _("Quality:")
	istrBestQuality = _("Best quality")
	istrHighQuality = _("High quality")
	istrLowQuality = _("Low quality")
	istrLargeFile = _("Large file")
	istrSmallFile = _("Small file")
	istrSilent = _("Silent")
	istrRotate = _("Rotate")
	istrClickToTakePicture = _("Click to take picture")
	istrClickToAddPicture = _("Click to add picture")
	#TRANS: Downloading Photo from Mary
	istrDownloadingFrom = _("Downloading %(1)s from %(2)s")
	#TRANS: Cannot download this Photo
	istrCannotDownload = _("Cannot download this %(1)s")

	mediaTypes = {}
	mediaTypes[TYPE_PHOTO] = {keyName:"photo", keyMime:"image/jpeg", keyExt:"jpg", keyIstr:istrPhoto}
	mediaTypes[TYPE_VIDEO] = {keyName:"video", keyMime:"video/ogg", keyExt:"ogg", keyIstr:istrVideo}
	mediaTypes[TYPE_AUDIO] = {keyName:"audio", keyMime:"audio/ogg", keyExt:"ogg", keyIstr:istrAudio}

	thumbPhotoSvgData = None
	thumbPhotoSvg = None
	thumbVideoSvg = None
	maxEnlargeSvg = None
	maxReduceSvg = None
	infoOnSvg = None
	xoGuySvgData = None

	recImg = None
	recRedImg = None
	recCircleCairo = None
	recInsensitiveImg = None
	recPlayImg = None
	recPauseImg = None
	countdownImgs = {}

	dim_CONTROLBAR_HT = 55

	def __init__( self, ca ):
		self.__class__.activityId = ca._activity_id

		thumbPhotoSvgPath = os.path.join(self.__class__.gfxPath, 'object-photo.svg')
		thumbPhotoSvgFile = open(thumbPhotoSvgPath, 'r')
		self.__class__.thumbPhotoSvgData = thumbPhotoSvgFile.read()
		self.__class__.thumbPhotoSvg = utils.loadSvg(self.__class__.thumbPhotoSvgData, Instance.colorStroke.hex, Instance.colorFill.hex)
		thumbPhotoSvgFile.close()

		thumbVideoSvgPath = os.path.join(self.__class__.gfxPath, 'object-video.svg')
		thumbVideoSvgFile = open(thumbVideoSvgPath, 'r')
		self.__class__.thumbVideoSvgData = thumbVideoSvgFile.read()
		self.__class__.thumbVideoSvg = utils.loadSvg(self.__class__.thumbVideoSvgData, Instance.colorStroke.hex, Instance.colorFill.hex)
		thumbVideoSvgFile.close()

		thumbAudioSvgPath = os.path.join(self.__class__.gfxPath, 'object-audio.svg')
		thumbAudioSvgFile = open(thumbAudioSvgPath, 'r')
		self.__class__.thumbAudioSvgData = thumbAudioSvgFile.read()
		self.__class__.thumbAudioSvg = utils.loadSvg(self.__class__.thumbAudioSvgData, Instance.colorStroke.hex, Instance.colorFill.hex)
		thumbAudioSvgFile.close()

		maxEnlargeSvgPath = os.path.join(self.__class__.gfxPath, 'max-enlarge.svg')
		maxEnlargeSvgFile = open(maxEnlargeSvgPath, 'r')
		maxEnlargeSvgData = maxEnlargeSvgFile.read()
		self.__class__.maxEnlargeSvg = utils.loadSvg(maxEnlargeSvgData, None, None )
		maxEnlargeSvgFile.close()

		maxReduceSvgPath = os.path.join(self.__class__.gfxPath, 'max-reduce.svg')
		maxReduceSvgFile = open(maxReduceSvgPath, 'r')
		maxReduceSvgData = maxReduceSvgFile.read()
		self.__class__.maxReduceSvg = utils.loadSvg(maxReduceSvgData, None, None )
		maxReduceSvgFile.close()

		infoOnSvgPath = os.path.join(self.__class__.gfxPath, 'corner-info.svg')
		infoOnSvgFile = open(infoOnSvgPath, 'r')
		infoOnSvgData = infoOnSvgFile.read()
		self.__class__.infoOnSvg = utils.loadSvg(infoOnSvgData, None, None )
		infoOnSvgFile.close()

		xoGuySvgPath = os.path.join(self.__class__.gfxPath, 'xo-guy.svg')
		xoGuySvgFile = open(xoGuySvgPath, 'r')
		self.__class__.xoGuySvgData = xoGuySvgFile.read()
		xoGuySvgFile.close()

		recFile = os.path.join(self.__class__.gfxPath, 'media-record.png')
		recPixbuf = gtk.gdk.pixbuf_new_from_file(recFile)
		self.__class__.recImg = gtk.Image()
		self.__class__.recImg.set_from_pixbuf( recPixbuf )

		recRedFile = os.path.join(self.__class__.gfxPath, 'media-record-red.png')
		recRedPixbuf = gtk.gdk.pixbuf_new_from_file(recRedFile)
		self.__class__.recRedImg = gtk.Image()
		self.__class__.recRedImg.set_from_pixbuf( recRedPixbuf )

		recCircleFile = os.path.join(self.__class__.gfxPath, 'media-circle.png')
		recCirclePixbuf = gtk.gdk.pixbuf_new_from_file(recCircleFile)
		self.__class__.recCircleCairo = _camera.cairo_surface_from_gdk_pixbuf(recCirclePixbuf)

		recInsFile = os.path.join(self.__class__.gfxPath, 'media-insensitive.png')
		recInsPixbuf = gtk.gdk.pixbuf_new_from_file(recInsFile)
		self.__class__.recInsensitiveImg = gtk.Image()
		self.__class__.recInsensitiveImg.set_from_pixbuf( recInsPixbuf )

		recPlayFile = os.path.join(self.__class__.gfxPath, 'media-play.png')
		recPlayPixbuf = gtk.gdk.pixbuf_new_from_file(recPlayFile)
		self.__class__.recPlayImg = gtk.Image()
		self.__class__.recPlayImg.set_from_pixbuf( recPlayPixbuf )

		recPauseFile = os.path.join(self.__class__.gfxPath, 'media-pause.png')
		recPausePixbuf = gtk.gdk.pixbuf_new_from_file(recPauseFile)
		self.__class__.recPauseImg = gtk.Image()
		self.__class__.recPauseImg.set_from_pixbuf( recPausePixbuf )

		self._ts = self.__class__.TIMERS
		longestTime = self._ts[len(self._ts)-1]
		for i in range (0, longestTime):
			self.createCountdownPng( i )


	def createCountdownPng( self, num ):
		todisk = True

		w = self.__class__.dim_CONTROLBAR_HT
		h = w
		if (todisk):
			cimg = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
			ctx = cairo.Context(cimg)
		else:
			pixmap = gtk.gdk.Pixmap(None, w, h, 24)
			ctx = pixmap.cairo_create()
		ctx.rectangle(0, 0, w, h)
		ctx.set_source_rgb(0, 0, 0)
		ctx.fill()
		x = 0
		y = 4
		ctx.translate(x,y)
		ctx.set_source_surface (self.__class__.recCircleCairo, 0, 0)
		ctx.paint()
		ctx.translate(-x,-y)

		ctx.set_source_rgb(255, 255, 255)
		pctx = pangocairo.CairoContext(ctx)
		play = pctx.create_layout()
		font = pango.FontDescription("sans 30")
		play.set_font_description(font)
		play.set_text( ""+str(num) )
		dim = play.get_pixel_extents()
		ctx.translate( -dim[0][0], -dim[0][1] )
		xoff = (w-dim[0][2])/2
		yoff = (h-dim[0][3])/2
		ctx.translate( xoff, yoff )
		ctx.translate( -3, 0 )
		pctx.show_layout(play)

		img = gtk.Image()
		if (todisk):
			path = os.path.join(Instance.tmpPath, str(num)+".png")
			path = utils.getUniqueFilepath(path, 0)
			cimg.write_to_png(path)
			numPixbuf = gtk.gdk.pixbuf_new_from_file(path)
			img.set_from_pixbuf( numPixbuf )
		else:
			img.set_from_pixmap(pixmap, None)

		self.__class__.countdownImgs[int(num)] = img