#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014
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

"""Builds outputs and runs unit tests as specified in a .abcmk file."""

import os
import sys

import make



####################################################################################################
# __main__

def _main(iterArgs):
   """Implementation of __main__.

   iterable(str*) iterArgs
      Command-line arguments.
   int return
      Command return status.
   """

   mk = make.Make()
   iArg = 1
   iArgEnd = len(iterArgs)

   # Parse arguments, looking for option flags.
   while iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.startswith('--'):
         if sArg == '--force-build':
            mk.force_build = True
         elif sArg == '--dry-run':
            mk.dry_run = True
         elif sArg == '--ignore-errors':
            mk.ignore_errors = True
         elif sArg == '--keep-going':
            mk.keep_going = True
         elif sArg == '--verbose':
            mk.verbosity += 1
      elif sArg.startswith('-'):
         for sArgChar in sArg:
            if sArgChar == 'f':
               mk.force_build = True
            elif sArgChar == 'i':
               mk.ignore_errors = True
            elif sArgChar == 'k':
               mk.keep_going = True
            elif sArgChar == 'n':
               mk.dry_run = True
            elif sArgChar == 'v':
               mk.verbosity += 1
      else:
         break
      iArg += 1

   # Check for a makefile name.
   if iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.endswith('.abcmk'):
         # Save the argument as the makefile path and consume it.
         sMakefilePath = sArg
         iArg += 1
   else:
      # Check if the current directory contains a single ABC makefile.
      sMakefilePath = None
      for sFilePath in os.listdir():
         if sFilePath.endswith('.abcmk') and len(sFilePath) > len('.abcmk'):
            if sMakefilePath is None:
               sMakefilePath = sFilePath
            else:
               sys.stderr.write(
                  'error: multiple makefiles found in the current directory, please specify one ' +
                     'explicitly\n'
               )
               return 1
      if not sMakefilePath:
         sys.stderr.write('error: no makefile specified\n')
         return 1

   # Load the makefile.
   mk.parse(sMakefilePath)

   # If there are more argument, they will be treated as target named, indicating that only a subset
   # of the targets should be built; otherwise all named targets will be built.
   if iArg < iArgEnd:
      iterTargets = []
      while iArg < iArgEnd:
         sArg = iterArgs[iArg]
         iterTargets.add(mk.get_target_by_name(sArg, None) or mk.get_target_by_file_path(sArg))
         iArg += 1
   else:
      iterTargets = mk.named_targets

   # Build all selected targets: first schedule the jobs building them, then run them.
   for tgt in iterTargets:
      mk.schedule_target_jobs(tgt)
   return mk.run_scheduled_jobs()


if __name__ == '__main__':
   sys.exit(_main(sys.argv))

