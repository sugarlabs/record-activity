from sugar import network
from sugar.presence import presenceservice

import urlparse
import urllib
import posixpath
import shutil
import os

xmlRpcPort = 8888
httpPort = 8889

class MeshXMLRPCServer:
	def __init__( self, pca ):
		self.ca = pca
		#this is ye olde xmlrpc server
		#listen to and talk through this port for xmlrpc, using this here info
		self.server = network.GlibXMLRPCServer(("", xmlRpcPort))
		self.server.register_instance(self) #anything witout an _ is callable by all the hos and joes out there

	def newPhotoNotice( self, arg1, arg2 ):
		print "Request got " + str(arg1) + ", " + str(arg2)
		self.ca.meshClient.reqNewPhotoBits( str(arg1), str(arg2) )
		print "requested new bits from that other buddy"
		return "successios"


class HttpServer(network.GlibTCPServer):
	def __init__(self, pca):
		self.ca = pca
		self.rootpath = self.ca.journalPath
		server_address = ("", httpPort)
		network.GlibTCPServer.__init__(self, server_address, HttpReqHandler);


class HttpReqHandler(network.ChunkedGlibHTTPRequestHandler):

	#from map...
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

#		result = self.server.acty.slogic.doServerLogic(self.path,urlPath,parama)
#		self.send_response(200)
#		for i in range (0, len(result.headers)):
#			self.send_header( result.headers[i][0], result.headers[i][1] )
#		self.end_headers()

		#should be abs path... check it 1st
		fileToSend = self.server.ca.ui.sendMeFedEx
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
									recd.thumbFilename,
									reply_handler=self.notifyBudsOfNewPicCb,
									error_handler=self.errorCb,
									user_data=bud)

	def notifyBudsOfNewPicCb(self, response, bud):
		print "Response was %s, user_data was %s" % (response, user_data)

	def errorCb(self, error, bud):
		print "We've a no go erroro! ", bud

	def reqNewPhotoBits(self, ip, file):
		#check i am not me, iterate till you get another dude
		#bud = self.my_acty.get_joined_buddies()[0]
		#todo: better way to get me?
		ps = presenceservice.get_instance()
		me = ps.get_owner()

		uri = "http://" + str(ip) + ":" + str(httpPort) + "/getStuff?" + str(file)
		print( uri )
		getter = network.GlibURLDownloader( uri )
		getter.connect( "finished", self.downloadResultCb, me )
		getter.connect( "error", self.downloadErrorCb, me )
		getter.start()

	def downloadResultCb(self, getter, tempfile, suggested_name, buddy):
		dest = os.path.join(os.path.expanduser("~"), suggested_name)
		shutil.copyfile(tempfile, dest)
		os.remove(tempfile)
		print( "downloaded and here it is: " + str(dest) )
		#self._load_document("file://%s" % dest)

	def downloadErrorCb(self, getter, err, buddy):
		logging.debug("Error getting document from %s (%s): %s" % (buddy.props.nick, buddy.props.ip4_address, err))
		#gobject.idle_add(self._get_document)