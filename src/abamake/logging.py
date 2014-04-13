#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2014
# Raffaello D. Di Napoli
#
# This file is part of Application-Building Components (henceforth referred to as ABC).
#
# ABC is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ABC is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with ABC. If not, see
# <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""Logging-related classes."""

import threading
import sys



####################################################################################################
# LogGenerator

class LogGenerator(object):
   """Generator of logs. Only one instance of this class exists for each make.Make instance."""

   # Total count of failed test assertions.
   _m_cFailedTestAssertions = None
   # Total count of failed test cases.
   _m_cFailedTestCases = None
   # Lock that must be acquired prior to writing to stderr.
   _m_lockStdErr = None
   # Total count of test assertions performed.
   _m_cTotalTestAssertions = None
   # Total count of test cases executed.
   _m_cTotalTestCases = None


   def __init__(self):
      """Constructor."""

      self._m_cFailedTestAssertions = 0
      self._m_cFailedTestCases = 0
      self._m_lockStdErr = threading.Lock()
      self._m_cTotalTestAssertions = 0
      self._m_cTotalTestCases = 0
      self.verbosity = Logger.QUIET


   def add_testcase_result(self, sTitle, cTotalAssertions, cFailedAssertions):
      """Implementation of Logger.add_testcase_result()."""

      # Update the assertion counts.
      self._m_cTotalTestAssertions += cTotalAssertions
      self._m_cFailedTestAssertions += cFailedAssertions

      # Update the test cases counts.
      self._m_cTotalTestCases += 1
      if cFailedAssertions:
         self._m_cFailedTestCases += 1


   def _test_summary_counts(self, cTotal, cFailed):
      """Generates a total/passed/failed summary line.

      int cTotal
         Total count.
      int cFailed
         Count of failures.
      str return
         String with the summary counts.
      """

      cPassed = cTotal - cFailed
      return '{:5} total, {:5} passed ({:3}%), {:5} failed ({:3}%)'.format(
         cTotal,
         cPassed, (cPassed * 100 + 1) // cTotal,
         cFailed,  cFailed * 100      // cTotal,
      )


   # Selects a verbosity level (make.logging.Logger.*), affecting what is displayed about the
   # operations executed.
   verbosity = None


   def write(self, s):
      """Implementation of Logger._write()."""

      s += '\n'
      # Lock stderr and write to it.
      with self._m_lockStdErr as lock:
         sys.stderr.write(s)


   def write_test_summary(self):
      """Implementation of Logger.test_summary()."""

      if self._m_cTotalTestAssertions:
         self.write('make: test summary:')
         self.write('  Test cases: ' + self._test_summary_counts(
            self._m_cTotalTestCases, self._m_cFailedTestCases
         ))
         self.write('  Assertions: ' + self._test_summary_counts(
            self._m_cTotalTestAssertions, self._m_cFailedTestAssertions
         ))
      else:
         self.write('Test cases: no tests performed')



####################################################################################################
# Logger

class Logger(object):
   """Basic logger functor."""

   # LogGenerator instance to use for logging.
   _m_lg = None

   # No verbosity, i.e. quiet operation (default). Will display a short summary of each job being
   # executed, instead of its command-line.
   QUIET = 1
   # Print each job’s command-line as-is instead of a short summary.
   LOW = 2
   # Like LOW, and also describe what triggers the (re)building of each target.
   MEDIUM = 3
   # Like MED, and also show all the files that are being checked for changes.
   HIGH = 4


   def __init__(self, lg):
      """Constructor.

      object lg
         make.logging.LogGenerator instance, or make.logging.Logger whose LogGenerator is to be
         shared.
      """

      if isinstance(lg, LogGenerator):
         self._m_lg = lg
      else:
         self._m_lg = lg._m_lg


   def __call__(self, iLevel, sFormat, *iterArgs, **dictKwArgs):
      """Logs a formatted string. A new-line character will be automatically appended because due
      to concurrency, a thread should not expect to log a complete line with multiple log calls.

      int iLevel
         Minimum logging level. If the log verbosity setting is below this value, the log entry will
         not be printed. If this value is None, the message will be output unconditionally (useful
         to report errors, for example).
      str sFormat
         Format string.
      iter(object*) *iterArgs
         Forwarded to sFormat.format().
      dict(str: object) **dictKwArgs
         Forwarded to sFormat.format().
      """

      if iLevel is None or self._m_lg.verbosity >= iLevel:
         self._write(sFormat.format(*iterArgs, **dictKwArgs))


   def add_testcase_result(self, sTitle, cTotalAssertions, cFailedAssertions):
      """Stores the result of a test case for later display as part of the test summary.

      str sTitle
         Title of the test case.
      int cTotalAssertions
         Count of assertions performed.
      int cFailedAssertions
         Count of failed assertions.
      """

      self._m_lg.add_testcase_result(sTitle, cTotalAssertions, cFailedAssertions)


   def qm_tool_name(self, sToolName):
      """Returns a “prettier” string for the specified tool, to be displayed in quiet mode.

      str sToolName
         Tool name.
      str return
         “Prettified” tool name.
      """

      # TODO: support coloring in case stderr is a TTY.
      return '{:<8}'.format(sToolName)


   def test_summary(self):
      """Generates and logs a summary of success/failures for the tests performed."""

      self._m_lg.write_test_summary()


   def _get_verbosity(self):
      return self._m_lg.verbosity

   def _set_verbosity(self, iLevel):
      self._m_lg.verbosity = iLevel

   verbosity = property(_get_verbosity, _set_verbosity, doc = """
      Selects a verbosity level (make.logging.Logger.*), affecting what is displayed about the
      operations executed.
   """)


   def _write(self, s):
      """Unconditionally logs a string.

      str s
         Text to log.
      """

      self._m_lg.write(s)

