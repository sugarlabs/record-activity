# Copyright (C) 2010, One Laptop per Child
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import subprocess

def _get_dmi(node):
    path = os.path.join('/sys/class/dmi/id', node)
    try:
        return open(path).readline().strip()
    except:
        return None

def _get_model():
    null = open(os.devnull, 'w')
    args = 'olpc-hwinfo model'.split(' ')
    try:
        model = subprocess.check_output(args, stderr=null).strip()
    except:
        model = None
    null.close()
    return model

def get_xo_version():
    version = None
    if _get_dmi('product_name') == 'XO':
        version = _get_dmi('product_version')
    if version is None:
        version = _get_model()
    if version == '1':
        return 1
    elif version == '1.5':
         return 1.5
    elif version == '1.75':
        return 1.75
    elif version == '4':
        return 4
    else:
        return 0

if __name__ == "__main__":
    print get_xo_version()
