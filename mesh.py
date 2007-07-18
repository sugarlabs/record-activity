from sugar import network
from sugar.presence import presenceservice

import urlparse
import urllib
import posixpath
import shutil
import os

from recorded import Recorded
from color import Color

xmlRpcPort = 8888
httpPort = 8889


#todo: when you take a picture, transmit the name and who took it, and buddy colors too... all things to create a rec'd
#todo: then create a directory in which to put buddy photos
#todo: then display them as thumbs, but when you click them, do resolution on where to get them from...
#todo: on joining activity get all of the existing photos from who has them
#todo: when someone deletes a photo, delete all photos

class MeshXMLRPCServer:
	def __init__( self, pca ):
		self.ca = pca
		#this is ye olde xmlrpc server
		#listen to and talk through this port for xmlrpc, using this here info
		self.server = network.GlibXMLRPCServer(("", xmlRpcPort))
		self.server.register_instance(self) #anything witout an _ is callable by all the hos and joes out there

	def newPhotoNotice( self,
						ip,
						mediaFilename, thumbFilename, time, photographer, name, colorStroke, colorFill ):

		newRecd = Recorded()
		newRecd.type = self.ca.m.TYPE_PHOTO
		newRecd.buddy = True
		newRecd.mediaFilename = mediaFilename
		newRecd.thumbFilename = thumbFilename
		newRecd.time = time
		newRecd.photographer = photographer
		newRecd.name = name

		colorStrokeHex = colorStroke
		colorStroke = Color()
		colorStroke.init_hex( colorStrokeHex )
		newRecd.colorStroke = colorStroke
		colorFillHex = colorFill
		colorFill = Color()
		colorFill.init_hex( colorFillHex )
		newRecd.colorFill =  colorFill

		self.ca.meshClient.requestThumbBits( ip, newRecd )
		print "requested new bits from that other buddy"
		return "successios"


class HttpServer(network.GlibTCPServer):

	def __init__(self, pca):
		self.ca = pca
		server_address = ("", httpPort)
		network.GlibTCPServer.__init__(self, server_address, HttpReqHandler);


class HttpReqHandler(network.ChunkedGlibHTTPRequestHandler):

	def translate_path(self, path):
		urlp = urlparse.urlparse(path)
		urls = urlp[2]
		urls = posixpath.normpath(urllib.unquote(urls))
		urlPath = urls.split('/')
		urlPath = filter(None, urlPath)

		params = urlp[4]
		parama = []
		allParams = params.split('&')
		for i in range (0, len(allParams)):
			parama.append(allParams[i].split('='))

		#todo: test to make sure file still here and not deleted
		#should be abs path... check it 1st
		ff = parama[0][1]
		fileToSend = os.path.join( self.server.ca.journalPath, ff )
		return fileToSend


class MeshClient:

	def __init__( self, pca ):
		self.ca = pca

		#stay alert!  buddies might show up at any time!
		print("1 meshClient");
		print("1.1 meshClient: ", self.ca)
		self.my_acty = self.ca._shared_activity #_pservice.get_activity(self.c.activity_id)
		print("1.2 meshClient: ", self.my_acty)
		#self.my_acty_id = self.c._frame.activity_id
		#print( "uid:", self.my_acty_id )

		self.my_acty.connect('buddy-joined', self.buddyJoinedCb)
		print("1.3")
		self.my_acty.connect('buddy-left', self.buddyDepartedCb)
		print("1.4")

		print("1.5", len(self.my_acty.get_joined_buddies()) )
		#if you've just arrived at the playground, take a peruse around
		for buddy in self.my_acty.get_joined_buddies():
			print ("a", buddy.props.nick)
			print ("a", buddy.props.ip4_address)
			print ("a", buddy.props.owner) #me boolean

		print("1.6")

	def buddyJoinedCb( self, activity, buddy ):
		print ("b", buddy.props.nick)
		print ("b", buddy.props.ip4_address)
		print ("b", buddy.props.owner) #me boolean

	def buddyDepartedCb( self, activity, buddy ):
		print ("c", buddy.props.nick)
		print ("c", buddy.props.ip4_address)
		print ("c", buddy.props.owner) #me boolean

	#herein we notify our buddies of some cool stuff we got going on they mights wants to knows abouts
	def notifyBudsOfNewPhoto( self, recd ):

		ps = presenceservice.get_instance()
		me = ps.get_owner()

		for buddy in self.my_acty.get_joined_buddies():
			if (not buddy.props.owner):
				bud = network.GlibServerProxy( "http://%s:%d" % (buddy.props.ip4_address, xmlRpcPort))

				bud.newPhotoNotice(	str(me.props.ip4_address),
									recd.mediaFilename, recd.thumbFilename,
									recd.time, recd.photographer,
									recd.name,
									recd.colorStroke.hex, recd.colorFill.hex,
									reply_handler=self.notifyBudsOfNewPicCb,
									error_handler=self.errorCb,
									user_data=bud)


	def notifyBudsOfNewPicCb(self, response, user_data):
		print "Response was %s, user_data was %s" % (response, user_data)


	def errorCb(self, error, bud):
		print "We've a no go erroro! ", bud


	def requestThumbBits(self, ip, recd):
		ps = presenceservice.get_instance()
		me = ps.get_owner()

		#todo: differentiate which session
		uri = "http://" + str(ip) + ":" + str(httpPort) + "/thumb?thumbFilename=" + str(recd.thumbFilename)
		print( uri )
		getter = network.GlibURLDownloader( uri )
		getter.connect( "finished", self.downloadResultCb, recd )
		getter.connect( "error", self.downloadErrorCb, recd )
		getter.start()


	def downloadResultCb(self, getter, tempfile, suggested_name, recd):
		#todo: better way to disambiguate who took which photo (hash)?
		#dest = os.path.join(os.path.expanduser("~"), suggested_name)
		buddyDirPath = os.path.join( self.ca.journalPath, "buddies" )
		if (not os.path.exists(buddyDirPath)):
			os.makedirs(buddyDirPath)

		dest = os.path.join( buddyDirPath, suggested_name )
		shutil.copyfile(tempfile, dest)
		os.remove(tempfile)
		print( "downloaded and here it is: " + str(dest) )
		print( "recd: ", recd )
		self.ca.m.addPhoto( recd )


	def downloadErrorCb(self, getter, err, recd):
		logging.debug("Error getting document from %s (%s): %s" % (buddy.props.nick, buddy.props.ip4_address, err))
		#gobject.idle_add(self._get_document)