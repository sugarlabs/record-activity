from sugar.p2p import network
from sugar.presence import presenceservice

xmlRpcPort = 8888
httpPort = 8889

class XMLRPCServer:
	def __init__( self, pc ):
		self.c = pc

		#this is ye olde xmlrpc server
		#listen to and talk through this port for xmlrpc, using this here info
		self.server = network.GlibXMLRPCServer(("", xmlRpcPort))
		self.server.register_instance(self) #anything witout an _ is callable by all the hos and joes out there

		#turn on http server here (to be moved elsewhere soon):
		hs = HttpServer( ("", httpPort), self.c.journalPath, self.c )

	def newPicNotice( self, arg1, arg2=None ):
		print "Request got " + str(arg1) + ", " + str(arg2)
		return "success"


class HttpServer(network.GlibTCPServer):
	def __init__(self, server_address, rootpath, pc):
		self.rootpath = rootpath
		self.c = pc
		network.GlibTCPServer.__init__(self, server_address, HttpReqHandler);


class HttpReqHandler(network.ChunkedGlibHTTPRequestHandler):
	#path is url to the path to the file being requested
	def translate_path(self, path):
		path = urlparse.urlparse(path)[2]
		path = posixpath.normpath(urllib.unquote(path))
		words = path.split('/')
		words = filter(None, words)
		print( words )

		#do some logic here to figure out what to do next

		#take a looksee at this coolness from our superclass (which is persistant mofo above..
		#who is always here whenever i wake up)
		print( self.server.rootpath )

		self.send_response(200)
		#self.send_header("Content-type", "jpeg/jpg")
		#self.send_header("Content-Disposition", 'attachment; filename="' + str(self.server.c.modFile) )

		#should be abs path... check it 1st
		fileToSend = self.server.c.modFile
		return fileToSend


class Client:

	def __init__( self, pc ):
		self.c = pc

		#stay alert!  buddies might show up at any time!
		self.my_acty = self.c._frame._shared_activity  #_pservice.get_activity(self.c.activity_id)
		self.my_acty.connect('buddy-joined', self.buddy_joined_cb)
		self.my_acty.connect('buddy-left', self.buddy_left_cb)

		#if you've just arrived at the playground, take a peruse around
		for buddy in self.my_acty.get_joined_buddies():
			print buddy.props.nick
			print buddy.props.ip4_address
			print buddy.props.owner #me boolean

	def buddy_joined_cb( self, activity, buddy ):
		pass

	def buddy_left_cb( self, activity, buddy ):
		pass

	#herein we notify our buddies of some cool stuff we got going on they mights wants to knows abouts
	def notifyBudsOfNewPic( self ):
		for buddy in self.my_acty.get_joined_buddies():
			bud = network.GlibServerProxy((buddy.props.ip4_address, xmlRpcPort))
			bud.newPicNotice("bar", reply_handler=self.notifyBudsOfNewPic_cb,
									error_handler=self.error_cb, user_data=bud)

	def notifyBudsOfNewPic_cb(self, response, bud):
		print "Response was %s, user_data was %s" % (response, user_data)

	def error_cb(self, error, bud):
		print "We've a no go erroro! ", bud

	def reqNewPhotoBits(self):
		#check i am not me, iterate till you get another dude
		bud = self.my_acty.get_joined_buddies()[0]
		getter = network.GlibURLDownloader("http://" + str(bud.props.ip4_address) + ":" + str(httpPort) + "/getStuff")
		getter.connect( "finished", self._download_result_cb, bud )
		getter.connect( "error", self._download_error_cb, bud )
		getter.start()

	def _download_result_cb(self, getter, tempfile, suggested_name, buddy):
		dest = os.path.join(os.path.expanduser("~"), suggested_name)
		shutil.copyfile(tempfile, dest)
		os.remove(tempfile)
		print( "downloaded and here it is: " + str(dest) )
		#self._load_document("file://%s" % dest)

	def _download_error_cb(self, getter, err, buddy):
		logging.debug("Error getting document from %s (%s): %s" % (buddy.props.nick, buddy.props.ip4_address, err))
		#gobject.idle_add(self._get_document)