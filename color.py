class Color:

	def __init__(self, r, g, b, a):
		self._ro = r
		self._go = g
		self._bo = b
		self._ao = a;
		self._r = self._ro / 255.0
		self._g = self._go / 255.0
		self._b = self._bo / 255.0
		self._a = self._ao / 255.0

		self._opaque = False
		if (self._a == 1):
			self.opaque = True

		rgb_tup = ( self._ro, self._go, self._bo )
		self._hex = self.rgb_to_hex( rgb_tup )


	def rgb_to_hex(self, rgb_tuple):
		hexcolor = '#%02x%02x%02x' % rgb_tuple
		# that's it! '%02x' means zero-padded, 2-digit hex values
		return hexcolor


	def hex_to_rgb(color):
		c = eval('0x' + color[1:])
		r = (c >> 16) & 0xFF
		g = (c >> 8) & 0xFF
		b = c & 0xFF
		return (r, g, b)