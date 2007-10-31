import os
import gtk
from gettext import gettext as _

import sugar.graphics.style
from sugar.activity import activity

from instance import Instance
from sugar import profile
from color import Color
import utils

class Constants:

	SERVICE = "org.laptop.RecordActivity"

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
	colorHilite = Color()
	colorHilite.init_gdk( sugar.graphics.style.COLOR_BUTTON_GREY )

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

	thumbPhotoSvgData = None
	thumbPhotoSvg = None
	thumbVideoSvg = None
	maxEnlargeSvg = None
	maxReduceSvg = None
	infoOnSvg = None
	xoGuySvgData = None
	camImg = None
	micImg = None

	def __init__( self, ca ):
		thumbPhotoSvgPath = os.path.join(self.__class__.gfxPath, 'thumb_photo.svg')
		thumbPhotoSvgFile = open(thumbPhotoSvgPath, 'r')
		self.__class__.thumbPhotoSvgData = thumbPhotoSvgFile.read()
		self.__class__.thumbPhotoSvg = utils.loadSvg(self.__class__.thumbPhotoSvgData, Instance.colorStroke.hex, Instance.colorFill.hex)
		thumbPhotoSvgFile.close()

		thumbVideoSvgPath = os.path.join(self.__class__.gfxPath, 'thumb_video.svg')
		thumbVideoSvgFile = open(thumbVideoSvgPath, 'r')
		self.__class__.thumbVideoSvgData = thumbVideoSvgFile.read()
		self.__class__.thumbVideoSvg = utils.loadSvg(self.__class__.thumbVideoSvgData, Instance.colorStroke.hex, Instance.colorFill.hex)
		thumbVideoSvgFile.close()

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

		infoOnSvgPath = os.path.join(self.__class__.gfxPath, 'info-on.svg')
		infoOnSvgFile = open(infoOnSvgPath, 'r')
		infoOnSvgData = infoOnSvgFile.read()
		self.__class__.infoOnSvg = utils.loadSvg(infoOnSvgData, None, None )
		infoOnSvgFile.close()

		#todo: load from sugar, query its size for my purposes
		#handle = self._load_svg(icon_info.file_name)
		#dimensions = handle.get_dimension_data()
		#icon_width = int(dimensions[0])
		#icon_height = int(dimensions[1])
		xoGuySvgPath = os.path.join(self.__class__.gfxPath, 'xo-guy.svg')
		xoGuySvgFile = open(xoGuySvgPath, 'r')
		self.__class__.xoGuySvgData = xoGuySvgFile.read()
		xoGuySvgFile.close()

		camImgFile = os.path.join(self.__class__.gfxPath, 'device-camera.png')
		camImgPixbuf = gtk.gdk.pixbuf_new_from_file(camImgFile)
		self.__class__.camImg = gtk.Image()
		self.__class__.camImg.set_from_pixbuf( camImgPixbuf )

		micImgFile = os.path.join(self.__class__.gfxPath, 'device-microphone.png')
		micImgPixbuf = gtk.gdk.pixbuf_new_from_file(micImgFile)
		self.__class__.micImg = gtk.Image()
		self.__class__.micImg.set_from_pixbuf( micImgPixbuf )

