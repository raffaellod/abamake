# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2017 Raffaello D. Di Napoli
#
# This file is part of Complemake.
#
# Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with Complemake. If not, see
# <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------------------------------------

"""This module contains the implementation of Complemake.

This file contains Complemake and other core classes.
"""

from __future__ import absolute_import

import os
import platform as pyplatform
import sys

FileNotFoundErrorCompat = getattr(__builtins__, 'FileNotFoundError', IOError)
if sys.hexversion >= 0x03000000:
   basestring = str


##############################################################################################################

def derived_classes(base_cls):
   """Iterates over all the classes that derive directly or indirectly from the specified one.

   This is probably rather slow, so it should not be abused.

   type base_cls
      Base class.
   type yield
      Class derived from base_cls.
   """

   yielded = set()
   classes_to_scan = [base_cls]
   while classes_to_scan:
      # Iterate over the direct subclasses of the first class to scan.
      for derived_cls in classes_to_scan.pop().__subclasses__():
         if derived_cls not in yielded:
            # We haven’t met or yielded this class before.
            yield derived_cls
            yielded.add(derived_cls)
            classes_to_scan.append(derived_cls)

_per_user_comk_dir = None

def get_per_user_comk_dir():
   """Returns the path to a per-user folder for Complemake to store files shared across projects.

   str return
      Per-user Complemake folder path.
   """

   global _per_user_comk_dir
   if not _per_user_comk_dir:
      if pyplatform.system() == 'Windows':
         import ctypes
         SHGetFolderPath = ctypes.windll.shell32.SHGetFolderPathW
         SHGetFolderPath.argtypes = (
            ctypes.wintypes.HWND, ctypes.c_int, ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD,
            ctypes.wintypes.LPCWSTR
         )
         # <user name>\Application Data
         CSIDL_APPDATA = 26

         path = ctypes.wintypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
         SHGetFolderPath(0, CSIDL_APPDATA, 0, 0, path)
         _per_user_comk_dir = os.path.join(path.value, 'Complemake')
      else:
         _per_user_comk_dir = os.path.join(os.environ['HOME'], '.comk')
   return _per_user_comk_dir

def makedirs(path):
   """Implementation of os.makedirs(exists_ok=True) for both Python 2.7 and 3.x.

   str path
      Full path to the directory that should exist.
   """

   try:
      os.makedirs(path)
   except OSError:
      if not os.path.isdir(path):
         raise
