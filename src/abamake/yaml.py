#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2015 Raffaello D. Di Napoli
#
# This file is part of Abamake.
#
# Abamake is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Abamake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
# the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Abamake. If not, see
# <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""YAML parser."""

import io
import os
import re
import unittest


####################################################################################################
# Non-member fuctions

def parse_file(sFilePath):
   """Loads and parses a YAML file.

   str sFilePath
      Path to the YAML file.
   object return
      Python object corresponding to the contents of the file.
   """

   with io.open(sFilePath, 'rt') as fileYaml:
      yp = YamlParser(sFilePath, fileYaml)
      return yp()

def parse_string(s):
   """Loads and parses a string containing YAML.

   str s
      YAML source.
   object return
      Python object corresponding to the contents of the string.
   """

   yp = YamlParser('<string>', iter(s.splitlines(True)))
   return yp()

####################################################################################################
# SyntaxError

class SyntaxError(Exception):
   """Indicates a syntactical or semantical error in a YAML source."""

   pass

####################################################################################################
# YamlParser

class YamlParser(object):
   """YAML parser. Only accepts a small subset of YAML 1.2 (sequences, maps, strings, comments),
   just enough to read Abamakefiles.
   """

   _smc_reComment = re.compile(r'[\t ]*#.*$')
   _smc_reIndent = re.compile(r'^[\t ]*')
   _smc_reMapKey = re.compile(r'^(?P<key>[^:]+) *: *')

   def __init__(self, sSourceName, iterLines):
      """Constructor.

      str sSourceName
         Name of the source for use in diagnostic messages.
      iterator(str) iterLines
         Object that yields YAML lines.
      """

      self._m_iLine = 0
      self._m_sLine = None
      self._m_iLineIndent = 0
      self._m_iCurrIndent = 0
      self._m_iterLines = iterLines
      self._m_sSourceName = sSourceName

   def __call__(self):
      self.find_and_consume_doc_start()
      if not self.next_line():
         return None
      return self.consume_object()

   def consume_map(self):
      # Save the current indentation, and use the line’s indentation + 1 as the new indentation.
      iCurrIndent = self._m_iCurrIndent
      self._m_iCurrIndent = self._m_iLineIndent
      dictRet = {}
      while True:
         match = self._smc_reMapKey.match(self._m_sLine)
         if not match:
            raise self.parsing_error('map key expected')
         # Grab the key and strip off the whole matched string.
         sKey = match.group('key')
         self._m_sLine = self._m_sLine[len(match.group()):]

         # Parse whatever is left; if spanning multiple lines, this will continue until the
         # indentation returns to iCurrIndent.
         dictRet[sKey] = self.consume_object()

         # consume_*() functions always quit after reading one last line, so check if we’re still in
         # the sequence.
         if self._m_sLine is None or self._m_iLineIndent < iCurrIndent:
            # No next line, or the next line is not part of the map.
            break
      self._m_iCurrIndent = iCurrIndent
      return dictRet

   def consume_object(self):
      if len(self._m_sLine) == 0:
         # The current container left no characters on the current line, so read another one.
         self.next_line()
      if self._m_sLine.startswith('- '):
         # Restart parsing this line as a sequence.
         return self.consume_sequence()
      elif ':' in self._m_sLine:
         # Restart parsing this line as a map.
         return self.consume_map()
      else:
         # Not a sequence and not a map, this line must contain a scalar.
         return self.consume_scalar()

   def consume_scalar(self):
      """Consumes a scalar.
      
      str return
         Raw scalar value.
      """

      sRet = self._m_sLine
      # A next line with same or more indentation is considered a continuation of the scalar.
      while self.next_line() and self._m_iLineIndent > self._m_iCurrIndent:
         # TODO: maybe validate that _m_sLine does not contain “:”?
         sRet += ' ' + self._m_sLine
      return sRet

   def consume_sequence(self):
      # Save the current indentation, and use the line’s indentation + len(“- ”) as the new
      # indentation.
      iCurrIndent = self._m_iCurrIndent
      self._m_iCurrIndent = self._m_iLineIndent + 2
      listRet = []
      while True:
         # Strip the “- ” prefix and any following whitespace.
         self._m_sLine = self._m_sLine[2:].lstrip(' ')

         # Parse whatever is left; if spanning multiple lines, this will continue until the
         # indentation returns to iCurrIndent.
         listRet.append(self.consume_object())

         # consume_*() functions always quit after reading one last line, so check if we’re still in
         # the sequence.
         if self._m_sLine is None or self._m_iLineIndent < iCurrIndent or not self._m_sLine.startswith('- '):
            # No next line, or the next line is not part of the sequence.
            break
      self._m_iCurrIndent = iCurrIndent
      return listRet

   def find_and_consume_doc_start(self):
      """Consumes and validates the start of the YAML document."""

      self.next_line()
      if self._m_sLine != '%YAML 1.2':
         raise self.parsing_error('expected %YAML directive')
      if not self.next_line():
         raise self.parsing_error('missing document start')
      if self._m_sLine != '---':
         raise self.parsing_error('unexpected directive')

   def next_line(self):
      """Attempts to read a new line from the YAML document, making it available as self._m_sLine
      after stripping from it any indentation, the length of which is stored in self._m_iLineIndent.

      bool return
         True if a new line was read, of False otherwise.
      """

      while True:
         self._m_iLine += 1
         sLine = next(self._m_iterLines, None)
         if sLine is None:
            # EOF has no indentation.
            self._m_iLineIndent = 0
         else:
            # Strip the trailing line terminator.
            sLine = sLine.rstrip('\n\r')
            # Strip trailing comments.
            # TODO: make this not peek inside quoted strings.
            sLine = self._smc_reComment.sub('', sLine)
            # If nothing’s left, move on to the next line; otherwise return True to consume it.
            if not sLine:
               continue
            # Determine the indentation of the line.
            self._m_iLineIndent = len(self._smc_reIndent.match(sLine).group())
            sLine = sLine[self._m_iLineIndent:]
         self._m_sLine = sLine
         return sLine is not None

   def parsing_error(self, sMessage):
      return SyntaxError('{}:{}: {}, found: “{}”'.format(
         self._m_sSourceName, self._m_iLine, sMessage, self._m_sLine
      ))

# (cd src && python -m unittest abamake/yaml.py)

class YamlParserTestCase(unittest.TestCase):
   def runTest(self):
      self.assertRaises(SyntaxError, parse_string, '')