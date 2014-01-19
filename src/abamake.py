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
import re
import subprocess
import sys
import time
import xml.dom
import xml.dom.minidom



####################################################################################################
# Tool

class Tool(object):
   """Abstract tool."""

   # Files to be processed by the tool.
   _m_listInputFilePaths = None
   # Output file path.
   _m_sOutputFilePath = None
   # Short name of the tool, to be displayed in quiet mode. If None, the tool file name will be
   # displayed.
   _smc_sQuietName = None
   # Associates a Tool-derived class to its executable file name.
   _sm_dictToolFilePaths = {}
   # Environment block (dictionary) modified to force programs to display output in US English.
   _sm_dictUSEngEnv = None


   def add_input(self, sInputFilePath):
      """Adds an input file to the tool input set."""

      if self._m_listInputFilePaths is None:
         self._m_listInputFilePaths = []
      self._m_listInputFilePaths.append(sInputFilePath)


   @classmethod
   def detect(cls, iterSupported):
      """Attempts to detect the presence of a tool’s executable from a list of supported ones,
      returning the corresponding class.
      """

      # TODO: accept a linker executable path provided via command line.
      # TODO: apply a cross-compiler prefix.

      for clsTool, iterArgs, sOutMatch in iterSupported:
         # Make sure we have a US English environment dictionary.
         if cls._sm_dictUSEngEnv is None:
            # Copy the current environment and add to it a locale override for US English.
            cls._sm_dictUSEngEnv = os.environ.copy()
            cls._sm_dictUSEngEnv['LC_ALL'] = 'en_US.UTF-8'

         try:
            with subprocess.Popen(
               iterArgs,
               stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True,
               env = cls._sm_dictUSEngEnv
            ) as procTool:
               sOut, sErr = procTool.communicate()
               iRet = procTool.returncode
         except FileNotFoundError:
            # This just means that the program is not installed; move on to the next candidate.
            continue
         if re.search(sOutMatch, sOut, re.MULTILINE):
            # Permanently associate the tool to the file path.
            cls._sm_dictToolFilePaths[clsTool] = iterArgs[0]
            # Return the selection.
            return clsTool

      # The executable’s output didn’t match any of the known strings above.
      raise Exception('unsupported linker')



   def _get_quiet_cmd(self):
      """Returns an iterable containing the short name and relevant (input or output) files for the
      tool, to be displayed in quiet mode.
      """

      if self._smc_sQuietName is None:
         sQuietName = os.path.basename(self._sm_dictToolFilePaths[self.__class__])
      else:
         sQuietName = self._smc_sQuietName
      return sQuietName, self._m_sOutputFilePath


   def _run_add_cmd_flags(self, listArgs):
      """Builds the flags portion of the tool’s command line.

      The default implementation does nothing – no flags can be applied to every tool.
      """

      pass


   def _run_add_cmd_inputs(self, listArgs):
      """Builds the input files portion of the tool’s command line.

      The default implementation adds the input file paths at the end of listArgs.
      """

      # Add the source file paths, if any.
      if self._m_listInputFilePaths:
         listArgs.extend(self._m_listInputFilePaths)


   def schedule_jobs(self, make, iterBlockingJobs):
      """Schedules one or more jobs that, when run, result in the execution of the tool.

      An implementation will create one or more chained ScheduledJob instances, blocking the first
      with iterBlockingJobs and returning the last one.

      The default implementation schedules a single job, the command line of which is composed by
      calling Tool._run_add_cmd_flags() and Tool._run_add_cmd_inputs().
      """

      # Make sure that the output directory exists.
      if self._m_sOutputFilePath:
         os.makedirs(os.path.dirname(self._m_sOutputFilePath), 0o755, True)

      # Build the arguments list.
      listArgs = [self._sm_dictToolFilePaths[self.__class__]]
      self._run_add_cmd_flags(listArgs)
      self._run_add_cmd_inputs(listArgs)
      if make.verbose:
         iterQuietCmd = None
      else:
         iterQuietCmd = self._get_quiet_cmd()
      return ScheduledJob(make, iterBlockingJobs, listArgs, iterQuietCmd)


   def set_output(self, sOutputFilePath):
      """Assigns the name of the tool output."""

      self._m_sOutputFilePath = sOutputFilePath



####################################################################################################
# CxxCompiler

class CxxCompiler(Tool):
   """Abstract C++ compiler."""

   # See ObjectTarget.final_output_type.
   _m_iFinalOutputType = None
   # Additional include directories.
   _m_listIncludeDirs = None
   # See Tool._smc_sQuietName.
   _smc_sQuietName = 'C++'


   def add_include_dir(self, sIncludeDirPath):
      """Adds an include directory to the compiler’s command line."""

      if self._m_listIncludeDirs is None:
         self._m_listIncludeDirs = []
      self._m_listIncludeDirs.append(sIncludeDirPath)


   def _get_quiet_cmd(self):
      """See Tool._get_quiet_cmd(). This override substitutes the output file path with the inputs,
      to show the source file path instead of the intermediate one.
      """

      iterQuietCmd = super()._get_quiet_cmd()
      return [iterQuietCmd[0]] + self._m_listInputFilePaths


   # Name suffix for intermediate object files.
   object_suffix = None


   def set_output(self, sOutputFilePath, iFinalOutputType):
      """See Tool.set_output(); also assigns the type of the final linker output."""

      super().set_output(sOutputFilePath)
      self._m_iFinalOutputType = iFinalOutputType



####################################################################################################
# GCC-driven GNU LD

class GxxCompiler(CxxCompiler):
   """GNU C++ compiler (G++)."""

   def __init__(self):
      """Constructor. See Linker.__init__()."""

      super().__init__()
      # TODO: remove hardcoded dirs.
      self.add_include_dir('include')


   # See CxxCompiler.object_suffix.
   object_suffix = '.o'


   def _run_add_cmd_flags(self, listArgs):
      """See CxxCompiler._run_add_cmd_flags()."""

      super()._run_add_cmd_flags(listArgs)

      # Add flags.
      listArgs.extend([
         '-c', '-std=c++0x', '-fnon-call-exceptions', '-fvisibility=hidden'
      ])
      listArgs.extend([
         '-ggdb', '-O0', '-DDEBUG=1'
      ])
      listArgs.extend([
         '-Wall', '-Wextra', '-pedantic', '-Wundef', '-Wshadow', '-Wconversion',
         '-Wsign-conversion', '-Wlogical-op', '-Wmissing-declarations', '-Wpacked',
         '-Wunreachable-code', '-Winline'
      ])
      if self._m_iFinalOutputType == Linker.OUTPUT_DYNLIB:
         listArgs.append('-fPIC')
      # TODO: add support for os.environ['CFLAGS'] and other vars ?
      # Add the include directories.
      for sDirPath in self._m_listIncludeDirs or []:
         listArgs.append('-I' + sDirPath)
      # Add the output file path.
      listArgs.append('-o')
      listArgs.append(self._m_sOutputFilePath)



####################################################################################################
# Linker

class Linker(Tool):
   """Abstract object code linker."""

   OUTPUT_EXE = 1
   OUTPUT_DYNLIB = 2


   # Additional libraries to link to.
   _m_listInputLibs = None
   # Directories to be included in the library search path.
   _m_listLibPaths = None
   # Type of output to generate.
   _m_iOutputType = None
   # See Tool._smc_sQuietName.
   _smc_sQuietName = 'LINK'


   def add_input_lib(self, sInputLibFilePath):
      """Appends a library to the linker’s command line."""

      if self._m_listInputLibs is None:
         self._m_listInputLibs = []
      self._m_listInputLibs.append(sInputLibFilePath)


   def add_lib_path(self, sLibPath):
      """Appends a directory to the library search path."""

      if self._m_listLibPaths is None:
         self._m_listLibPaths = []
      self._m_listLibPaths.append(sLibPath)


   def set_output(self, sOutputFilePath, iOutputType):
      """See Tool.set_output(); also assigns the type of the linker output."""

      super().set_output(sOutputFilePath)
      self._m_iOutputType = iOutputType



####################################################################################################
# GCC-driven GNU LD

class GnuLinker(Linker):
   """GCC-driven GNU object code linker (LD)."""


   def __init__(self):
      """Constructor. See Linker.__init__()."""

      super().__init__()


   def _run_add_cmd_flags(self, listArgs):
      """See Linker._run_add_cmd_flags()."""

      super()._run_add_cmd_flags(listArgs)

      listArgs.append('-Wl,--as-needed')
      listArgs.append('-ggdb')
      if self._m_iOutputType == Linker.OUTPUT_DYNLIB:
         listArgs.append('-shared')
      # TODO: add support for os.environ['LDFLAGS'] ?
      # Add the output file path.
      listArgs.append('-o')
      listArgs.append(self._m_sOutputFilePath)


   def _run_add_cmd_inputs(self, listArgs):
      """See Linker._run_add_cmd_inputs()."""

      # TODO: should not assume that GNU LD will only be used to build for POSIX.
      self.add_input_lib('dl')
      self.add_input_lib('pthread')

      super()._run_add_cmd_inputs(listArgs)

      # Add the library search directories.
      for sDir in self._m_listLibPaths or []:
         listArgs.append('-L' + sDir)
      # Add the libraries.
      for sLib in self._m_listInputLibs or []:
         listArgs.append('-l' + sLib)



####################################################################################################
# Target

class Target(object):
   """Abstract build target."""

   # See Target.dependencies.
   _m_setDeps = None
   # See Target.file_path.
   _m_sFilePath = None
   # See Target.name.
   _m_sName = None


   def add_dependency(self, tgtDep):
      """Adds a target dependency."""

      if self._m_setDeps is None:
         self._m_setDeps = set()
      self._m_setDeps.add(tgtDep)


   def build(self, make, iterBlockingJobs):
      """Builds the output, using the facilities provided by the specified Make instance. Returns a
      ScheduledJob instance (or a tree of that) if the target scheduled jobs to be rebuilt, of None
      if it was already current."""

      raise NotImplementedError('Target.build() must be overridden')


   def _get_dependencies(self):
      if self._m_setDeps is None:
         return None
      else:
         # Return a copy, so the caller can manipulate it as necessary.
         return list(self._m_setDeps)

   dependencies = property(_get_dependencies, doc = """
      List of targets on which this target depends.
   """)


   def _get_file_path(self):
      return self._m_sFilePath

   file_path = property(_get_file_path, doc = """Target file path.""")


   def generate_file_path(self, make):
      """Generates and returns a file path for the target, based on other properties set beforehand
      and the configuration of the provided Make instance.

      The default implementation doesn’t generate a file path because no output file is assumed.
      """

      # No output file.
      return None


   def _get_name(self):
      return self._m_sName

   def _set_name(self, sName):
      self._m_sName = sName

   name = property(_get_name, _set_name, doc = """Name of the target.""")


   def parse_makefile_child(self, elt, make):
      """Validates and processes the specified child element of the target’s <target> element."""

      # Default implementation: expect no child elements.
      raise SyntaxError('unexpected element: <{}>'.format(elt.nodeName))



####################################################################################################
# ObjectTarget

class ObjectTarget(Target):
   """Intermediate object target. The output file will be placed in a obj/ directory relative to the
   output base directory.
   """

   # See ObjectTarget.final_output_type.
   _m_iFinalOutputType = None
   # See ObjectTarget.source_file_path.
   _m_sSourceFilePath = None


   def _get_final_output_type(self):
      return self._m_iFinalOutputType

   def _set_final_output_type(self, iFinalOutputType):
      self._m_iFinalOutputType = iFinalOutputType

   final_output_type = property(_get_final_output_type, _set_final_output_type, doc = """
      Kind of output that ObjectTarget.build() will aim for when generating the object file, e.g. by
      passing -fPIC for a C++ source file when compiling it for a shared object.
   """)


   def generate_file_path(self, make):
      """See Target.generate_file_path()."""

      sFilePath = os.path.join(
         make.output_dir, 'obj', self._m_sSourceFilePath + make.cxxcompiler.object_suffix
      )
      self._m_sFilePath = sFilePath
      return sFilePath


   def _get_source_file_path(self):
      return self._m_sSourceFilePath

   def _set_source_file_path(self, sSourceFilePath):
      self._m_sSourceFilePath = sSourceFilePath

   source_file_path = property(_get_source_file_path, _set_source_file_path, doc = """
      Source from which the target is built.
   """)



####################################################################################################
# CxxObjectTarget

class CxxObjectTarget(ObjectTarget):
   """C++ intermediate object target."""

   def build(self, make, iterBlockingJobs):
      """See Target.build()."""

      # TODO: check for changed dependencies.
      if not iterBlockingJobs and False:
         return None

      cxx = make.cxxcompiler()
      cxx.set_output(self.file_path, self.final_output_type)
      cxx.add_input(self._m_sSourceFilePath)
      # TODO: add file-specific flags.
      return cxx.schedule_jobs(make, iterBlockingJobs)



####################################################################################################
# ExecutableTarget

class ExecutableTarget(Target):
   """Executable program target. The output file will be placed in a bin/ directory relative to the
   output base directory.
   """

   # See ExecutableTarget.linker_inputs.
   _m_listLinkerInputs = None


   def add_linker_input(self, tgtDep):
      """Adds a target dependency."""

      if self._m_listLinkerInputs is None:
         self._m_listLinkerInputs = []
      self._m_listLinkerInputs.append(tgtDep)


   def build(self, make, iterBlockingJobs):
      """See Target.build()."""

      # TODO: check for changed dependencies.
      if not iterBlockingJobs and False:
         return None

      lnk = make.linker()
      lnk.set_output(self.file_path, self.output_type)
      # At this point all the dependencies are available, so add them as inputs.
      for oDep in self._m_listLinkerInputs or []:
         if isinstance(oDep, ObjectTarget):
            lnk.add_input(oDep.file_path)
         elif isinstance(oDep, DynLibTarget):
            lnk.add_input_lib(oDep.name)
            # Since we’re linking to a library built by this makefile, make sure to add the output
            # lib/ directory to the library search path.
            lnk.add_lib_path(os.path.join(make.output_dir, 'lib'))
         elif isinstance(oDep, str):
            # Strings go directly to the linker’s command line, assuming that they are external
            # libraries to link to.
            lnk.add_input_lib(oDep)
         else:
            raise Exception('unclassified linker input: {}'.format(oDep.file_path))
      return lnk.schedule_jobs(make, iterBlockingJobs)


   def _get_linker_inputs(self):
      if self._m_listLinkerInputs is None:
         return None
      else:
         return self._m_listLinkerInputs

   linker_inputs = property(_get_linker_inputs, doc = """
      List of dynamic libraries against which the target will be linked.
   """)


   def generate_file_path(self, make):
      """See Target.generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      sFilePath = os.path.join(make.output_dir, 'bin', '' + self.name + '')
      self._m_sFilePath = sFilePath
      return sFilePath


   # Kind of output that ExecutableTarget.build() will tell the linker to generate.
   # TODO: rename to _smc_*, since it’s only used by this and derived classes.
   output_type = Linker.OUTPUT_EXE


   def parse_makefile_child(self, elt, make):
      """See Target.parse_makefile_child()."""

      if elt.nodeName == 'source':
         # Pick the correct target class based on the file name extension.
         sFilePath = elt.getAttribute('path')
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            clsObjTarget = CxxObjectTarget
         else:
            raise Exception('unsupported source file type')
         # Create an object target and add it as a dependency to the containing target.
         tgtObj = clsObjTarget()
         tgtObj.final_output_type = self.output_type
         self.add_dependency(tgtObj)
         self.add_linker_input(tgtObj)
         # Assign the file path as the source.
         tgtObj.source_file_path = sFilePath
         make._add_target(tgtObj)
      elif elt.nodeName == 'dynlib':
         # Check if this makefile can build this dynamic library.
         sName = elt.getAttribute('name')
         # If the library was in the dictionary (i.e. it’s built by this makefile), assign it as a
         # dependency of self; else just add the library name (hence passing sName as 2nd argument
         # to make.get_target_by_name()).
         oDynLib = make.get_target_by_name(sName, sName)
         if oDynLib is not sName:
            self.add_dependency(oDynLib)
         self.add_linker_input(oDynLib)
      elif elt.nodeName == 'unittest':
         # A unit test must be built after the target it’s supposed to test.
         sName = elt.getAttribute('name')
         tgtUnitTest = make.get_target_by_name(sName, None)
         if tgtUnitTest is None:
            raise Exception(
               'could not find definition of referenced unit test: {}'.format(sName)
            )
         tgtUnitTest.add_dependency(self)
      else:
         super().parse_makefile_child(elt, make)



####################################################################################################
# DynLibTarget

class DynLibTarget(ExecutableTarget):
   """Dynamic library target. The output file will be placed in a lib/ directory relative to the
   output base directory.
   """

   def generate_file_path(self, make):
      """See ExecutableTarget.generate_file_path()."""

      # TODO: change 'lib' + '.so' from hardcoded to computed by a Platform class.
      sFilePath = os.path.join(make.output_dir, 'lib', 'lib' + self.name + '.so')
      self._m_sFilePath = sFilePath
      return sFilePath


   def parse_makefile_child(self, elt, make):
      """See ExecutableTarget.parse_makefile_child()."""

      super().parse_makefile_child(elt, make)
      if elt.nodeName == 'unittest':
         sName = elt.getAttribute('name')
         tgtUnitTest = make.get_target_by_name(sName)
         # Make the unit test link to this library.
         tgtUnitTest.add_linker_input(self)


   # See ExecutableTarget.output_type.
   output_type = Linker.OUTPUT_DYNLIB



####################################################################################################
# UnitTestTarget

class UnitTestTarget(ExecutableTarget):
   """Executable unit test target. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.
   """

   def generate_file_path(self, make):
      """See ExecutableTarget.generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      sFilePath = os.path.join(make.output_dir, 'bin', 'unittest', '' + self.name + '')
      self._m_sFilePath = sFilePath
      return sFilePath


   def parse_makefile_child(self, elt, make):
      """See ExecutableTarget.parse_makefile_child()."""

      if elt.nodeName == 'unittest':
         raise SyntaxError('<unittest> not allowed in <target type="unittest">')
      elif elt.nodeName == 'runner':
         # TODO: assign the runner type.
         pass
      else:
         super().parse_makefile_child(elt, make)



####################################################################################################
# ScheduledJob

class ScheduledJob(object):
   """Schedules a job in the Make instance’s queue, keeping track of the jobs it must wait to
   complete.
   """

   # See ScheduledJob.command.
   _m_iterArgs = None
   # Jobs that this one is blocking.
   _m_setBlockedJobs = None
   # Count of jobs that block this one.
   _m_cBlocks = 0
   # See ScheduledJob.quiet_command.
   _m_iterQuietCmd = None


   def __init__(self, make, iterBlockingJobs, iterArgs, iterQuietCmd):
      """Constructor."""

      self._m_iterArgs = iterArgs
      self._m_iterQuietCmd = iterQuietCmd
      if iterBlockingJobs is not None:
         # Assign this job as “blocked” to the jobs it depends on, and store their count.
         for sjDep in iterBlockingJobs:
            sjDep._add_blocked(self)
         self._m_cBlocks = len(iterBlockingJobs)
      # Schedule this job.
      make._schedule_job(self)


   def _add_blocked(self, sj):
      """Adds a ScheduledJob to be released once this one completes."""

      if self._m_setBlockedJobs is None:
         self._m_setBlockedJobs = set()
      self._m_setBlockedJobs.add(sj)


   def _get_blocked(self):
      return self._m_cBlocks > 0

   blocked = property(_get_blocked, doc = """
      True if the job is blocked (i.e. requires other jobs to be run first), or False otherwise.
   """)


   def _get_command(self):
      return self._m_iterArgs

   command = property(_get_command, doc = """Command to be invoked, as a list of arguments.""")


   def _get_quiet_command(self):
      return self._m_iterQuietCmd

   quiet_command = property(_get_quiet_command, doc = """
      Command summary to print out in quiet mode.
   """)


   def release_blocked(self):
      """Release any jobs this one was blocking."""

      if self._m_setBlockedJobs:
         for sj in self._m_setBlockedJobs:
            sj._m_cBlocks -= 1



####################################################################################################
# Make

class Make(object):
   """Processes an ABC makefile (.abcmk) by parsing it, scheduling the necessary jobs to build any
   targets to be built, and then running the jobs with the selected degree of parallelism.

   Example usage:

      make = Make()
      make.parse('project.abcmk')
      make.schedule_target_jobs(make.get_target_by_name('projectbin'))
      make.run_scheduled_jobs()
   """

   # See Make.cxxcompiler.
   _m_clsCxxCompiler = None
   # See Make.dry_run.
   _m_bDryRun = False
   # See Make.force_build.
   _m_bForceBuild = False
   # See Make.ignore_errors.
   _m_bIgnoreErrors = False
   # See Make.keep_going.
   _m_bKeepGoing = False
   # See Make.linker.
   _m_clsLinker = None
   # Targets explicitly declared in the parsed makefile (name -> Target).
   _m_dictNamedTargets = None
   # See Make.output_dir.
   _m_sOutputDir = ''
   # Running jobs (Popen -> ScheduledJob).
   _m_dictRunningJobs = {}
   # Maximum count of running jobs, i.e. degree of parallelism.
   _m_cRunningJobsMax = 8
   # Scheduled jobs.
   _m_setScheduledJobs = None
   # “Last” scheduled jobs (Target -> ScheduledJob that completes it), i.e. jobs that are the last
   # in a chain of jobs scheduled to build a single target. The values are a subset of, or the same
   # as, Make._m_setScheduledJobs.
   _m_dictTargetLastScheduledJobs = None
   # All targets specified by the parsed makefile (file path -> Target), including implicit and
   # intermediate targets not explicitly declared with a <target> element.
   _m_dictTargets = None
   # See Make.verbose.
   _m_bVerbose = False

   # Special value used with get_target_by_*() to indicate that a target not found should result in
   # an exception.
   _RAISE_IF_NOT_FOUND = object()


   def __init__(self):
      """Constructor."""

      self._m_dictNamedTargets = {}
      self._m_setScheduledJobs = set()
      self._m_dictTargetLastScheduledJobs = {}
      self._m_dictTargets = {}


   def _add_target(self, tgt):
      """Lets a target generate its output file path, then adds it to the targets dictionary and the
      named targets dictionary (if the target has a name)."""

      sFilePath = tgt.generate_file_path(self)
      self._m_dictTargets[sFilePath] = tgt
      sName = tgt.name
      if sName:
         self._m_dictNamedTargets[sName] = tgt


   def _collect_completed_jobs(self, cJobsToComplete):
      """Returns only after the specified number of jobs completes and the respective cleanup
      operations (such as releasing blocked jobs) have been performed. If cJobsToComplete == 0, it
      only performs cleanup for jobs that have already completed, without waiting.

      Returns the count of failed jobs, unless Make._m_bIgnoreErrors == True, in which case it will
      always return 0.
      """

      # This loop alternates poll loop and sleeping.
      cCompletedJobs = 0
      cFailedJobs = 0
      # The termination condition is in the middle.
      while True:
         # This loop restarts the for loop, since we modify _m_dictRunningJobs. The termination
         # condition is a break statement.
         while True:
            # Poll each running job.
            for proc in self._m_dictRunningJobs.keys():
               if self._m_bDryRun:
                  # A no-ops is always successful.
                  iRet = 0
               else:
                  iRet = proc.poll()
               if iRet is not None:
                  # Remove the job from the running jobs.
                  sj = self._m_dictRunningJobs.pop(proc)
                  cCompletedJobs += 1
                  if iRet == 0 or self._m_bIgnoreErrors:
                     # The job completed successfully or we’re ignoring its failure: any dependent
                     # jobs can now be released.
                     sj.release_blocked()
                  else:
                     if self._m_bKeepGoing:
                        # Unschedule any dependent jobs, so we can continue ignoring this failure as
                        # long as we have scheduled jobs that don’t depend on it.
                        if sj._m_setBlockedJobs:
                           self._unschedule_jobs_blocked_by(sj)
                     cFailedJobs += 1
                  # Since we modified self._m_setScheduledJobs, we have to stop iterating over it.
                  # Iteration will be restarted by the inner while loop.
                  break
            else:
               # The for loop completed without interruptions, which means that no job slots were
               # freed, so break out of the inner while loop into the outer one to wait.
               break
         # If we freed up the requested count of slots, there’s nothing left to do.
         if cCompletedJobs >= cJobsToComplete:
            return cFailedJobs
         if not self._m_bDryRun:
            # Wait a small amount of time.
            # TODO: proper event-based waiting.
            time.sleep(0.1)


   def _get_cxxcompiler(self):
      if self._m_clsCxxCompiler is None:
         # TODO: what’s MSC’s output?
         self._m_clsCxxCompiler = Tool.detect((
            (GxxCompiler, ('g++', '--version'), r'^g\+\+ '),
            (object,      ('cl',  '/?'       ), r' CL '   ),
         ))
      return self._m_clsCxxCompiler

   cxxcompiler = property(_get_cxxcompiler, doc = """
      C++ compiler class to be used to build CxxObjectTarget instances.
   """)


   def _get_dry_run(self):
      return self._m_bDryRun

   def _set_dry_run(self, bDryRun):
      self._m_bDryRun = bDryRun

   dry_run = property(_get_dry_run, _set_dry_run, doc = """
      If True, commands will only be printed, not executed; if False, they will be printed and
      executed.
   """)


   def _get_force_build(self):
      return self._m_bForceBuild

   def _set_force_build(self, bForceBuild):
      self._m_bForceBuild = bForceBuild

   force_build = property(_get_force_build, _set_force_build, doc = """
      If True, targets are rebuilt unconditionally; if False, targets are rebuilt as needed.
   """)


   def get_target_by_file_path(self, sFilePaths, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a target given its path, raising an exception if no such target exists and no
      fallback value was provided."""

      tgt = self._m_dictTargets.get(sFilePath, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise NameError('unknown target: {}'.format(sFilePath))
      return tgt


   def get_target_by_name(self, sName, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a named (in the makefile) target given its name, raising an exception if no such
      target exists and no fallback value was provided."""

      tgt = self._m_dictNamedTargets.get(sName, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise NameError('undefined target: {}'.format(sName))
      return tgt


   def _get_ignore_errors(self):
      return self._m_bIgnoreErrors

   def _set_ignore_errors(self, bIgnoreErrors):
      self._m_bIgnoreErrors = bIgnoreErrors

   ignore_errors = property(_get_ignore_errors, _set_ignore_errors, doc = """
      If True, scheduled jobs will continue to be run even after a job they depend on fails. If
      False, a failed job causes execution to stop according to the value of Make.keep_going.
   """)


   @staticmethod
   def _is_node_whitespace(nd):
      """Returns True if a node is whitespace or a comment."""

      if nd.nodeType == xml.dom.Node.COMMENT_NODE:
         return True
      if nd.nodeType == xml.dom.Node.TEXT_NODE and re.match(r'^\s*$', nd.nodeValue):
         return True
      return False


   def _get_keep_going(self):
      return self._m_bKeepGoing

   def _set_keep_going(self, bKeepGoing):
      self._m_bKeepGoing = bKeepGoing

   keep_going = property(_get_keep_going, _set_keep_going, doc = """
      If True, scheduled jobs will continue to be run even after a failed job, as long as they don’t
      depend on a failed job. If False, a failed job causes execution to stop as soon as any other
      running jobs complete.
   """)


   def _get_linker(self):
      if self._m_clsLinker is None:
         # TODO: what’s MS Link’s output?
         self._m_clsLinker = Tool.detect((
            (GnuLinker, ('g++',  '-Wl,--version'), r'^GNU ld '),
            (GnuLinker, ('ld',   '--version'    ), r'^GNU ld '),
            (object,    ('link', '/?'           ), r' Link '  ),
         ))
      return self._m_clsLinker

   linker = property(_get_linker, doc = """
      Linker class to be used to build ExecutableTarget instances.
   """)


   def _get_named_targets(self):
      return self._m_dictNamedTargets.values()

   named_targets = property(_get_named_targets, doc = """
      Targets explicitly declared in the parsed makefile.
   """)


   def _get_output_dir(self):
      return self._m_sOutputDir

   def _set_output_dir(self, sOutputDir):
      self._m_sOutputDir = sOutputDir

   output_dir = property(_get_output_dir, _set_output_dir, doc = """
      Output base directory that will be used for both intermediate and final build results.
   """)


   def parse(self, sFilePath):
      """Parses an ABC makefile."""

      self.parse_doc(xml.dom.minidom.parse(sFilePath))


   def parse_doc(self, xd):
      """Parses a DOM representation of an ABC makefile."""

      xd.documentElement.normalize()

      # TODO: check whether and where this method should use contexts for the DOM nodes and/or
      # directly call unlink() on them.

      # Do a first scan of the top level elements, to find invalid nodes and unrecognized target
      # types. In the process, we instantiate all the target elements, so
      # Target.parse_makefile_child() can assign the dependencies even if they don’t appear in the
      # correct order in the makefile. This also allows to determine on-the-fly whether a referenced
      # <dynlib> is a target we should build or if we should expect to find it somewhere else.
      listNodesAndTargets = []
      for eltTarget in xd.documentElement.childNodes:
         if self._is_node_whitespace(eltTarget):
            # Skip whitespace/comment nodes.
            continue
         if eltTarget.nodeType != xml.dom.Node.ELEMENT_NODE:
            raise SyntaxError('expected <target>, found: {}'.format(eltTarget.nodeName))

         if eltTarget.nodeName == 'target':
            sType = eltTarget.getAttribute('type')
            # Instantiate a specialization of Target based on the “type” attribute.
            if sType == 'unittest':
               tgt = UnitTestTarget()
            elif sType == 'exe':
               tgt = ExecutableTarget()
            elif sType == 'dynlib':
               tgt = DynLibTarget()
            else:
               raise Exception('unsupported target type: {}'.format(sType))
            # Assign the target its name and add it to the targets.
            tgt.name = eltTarget.getAttribute('name')
            self._add_target(tgt)
            listNodesAndTargets.append((tgt, eltTarget))
         else:
            raise SyntaxError('expected <target>; found: <{}>'.format(eltTarget.nodeName))

      # Now that all the targets have been instantiated, we can have them parse their definitions.
      for tgt, eltTarget in listNodesAndTargets:
         for nd in eltTarget.childNodes:
            if self._is_node_whitespace(nd):
               # Skip whitespace/comment nodes.
               continue
            if nd.nodeType != xml.dom.Node.ELEMENT_NODE:
               raise Exception('expected element node, found: '.format(nd.nodeName))
            tgt.parse_makefile_child(nd, self)


   def print_targets_graph(self):
      """Prints to stdout a graph of target dependencies."""

      # Targets explicitly declared in the parsed makefile (name -> target).
      for sName, tgt in self._m_dictNamedTargets.items():
         print('Target “{}” {}'.format(sName, tgt.file_path))
      # All targets specified by the parsed makefile (file path -> Target), including implicit and
      # intermediate targets not explicitly declared with a <target> element.
      for sFilePath, tgt in self._m_dictTargets.items():
         print('Target {}'.format(tgt.file_path))



   def run_scheduled_jobs(self):
      """Executes any scheduled jobs."""

      # This is the earliest point we know we can reset this.
      self._m_dictTargetLastScheduledJobs.clear()

      cFailedJobsTotal = 0
      while self._m_setScheduledJobs:
         # Make sure any completed jobs are collected.
         cFailedJobs = self._collect_completed_jobs(0)
         # Make sure we have at least one free job slot.
         while len(self._m_dictRunningJobs) == self._m_cRunningJobsMax:
            # Wait for one or more jobs slots to free up.
            cFailedJobs += self._collect_completed_jobs(1)

         cFailedJobsTotal += cFailedJobs
         # Stop starting jobs in case of failed errors – unless overridden by the user.
         if cFailedJobs > 0 and not self._m_bKeepGoing:
            break

         # Find a job that is ready to be executed.
         for sj in self._m_setScheduledJobs:
            if not sj.blocked:
               iterArgs = sj.command
               if self._m_bVerbose:
                  sys.stdout.write(' '.join(iterArgs) + '\n')
               else:
                  iterQuietCmd = sj.quiet_command
                  sys.stdout.write('{:^8} {}\n'.format(iterQuietCmd[0], ' '.join(iterQuietCmd[1:])))
               if self._m_bDryRun:
                  # Create a placeholder instead of a real Popen instance.
                  proc = object()
               else:
                  proc = subprocess.Popen(iterArgs)
               # Move the job from scheduled to running jobs.
               self._m_dictRunningJobs[proc] = sj
               self._m_setScheduledJobs.remove(sj)
               # Since we modified self._m_setScheduledJobs, we have to stop iterating over it; the
               # outer while loop will get back here, eventually.
               break
      # There are no more scheduled jobs, just wait for the running ones to complete.
      cFailedJobsTotal += self._collect_completed_jobs(len(self._m_dictRunningJobs))
      return cFailedJobsTotal


   def _schedule_job(self, sj):
      """Used by ScheduledJob.__init__() to add itself to the set of scheduled jobs."""

      self._m_setScheduledJobs.add(sj)


   def schedule_target_jobs(self, tgt):
      """Schedules jobs for the specified target and all its dependencies, avoiding duplicate jobs.

      Recursively visits the dependency tree for the target in a leaves-first order, collecting
      (possibly chains of) ScheduledJob instances returned by Target.build() for all the
      dependencies, and making these block the ScheduledJob instance(s) for the specified target.
      """

      # Check if we already have a (last) ScheduledJob for this target.
      sj = self._m_dictTargetLastScheduledJobs.get(tgt)
      if sj is None:
         # Visit leaves.
         listBlockingJobs = None
         for tgtDep in tgt.dependencies or []:
            # Recursively schedule jobs for this dependency, returning and storing the last one.
            sjDep = self.schedule_target_jobs(tgtDep)
            if sjDep is not None:
               # Keep track of the dependencies’ jobs.
               if listBlockingJobs is None:
                  listBlockingJobs = []
               listBlockingJobs.append(sjDep)

         # Visit the node: give the target a chance to schedule jobs, letting it know which of its
         # dependencies scheduled jobs to be rebuilt, if any.
         sj = tgt.build(self, listBlockingJobs)
         # Store the job even if None.
         self._m_dictTargetLastScheduledJobs[tgt] = sj

      if sj is None:
         # If Target.build() did not return a job, there’s nothing to do for this target. This must
         # also mean that no dependencies scheduled any jobs.
         # TODO: how about phonies or “virtual targets”?
         assert(not listBlockingJobs)
      return sj


   def _unschedule_jobs_blocked_by(self, sj):
      """Recursively removes the jobs blocked by the specified job from the set of scheduled
      jobs.
      """

      for sjBlocked in sj._m_setBlockedJobs:
         # Use set.discard() instead of set.remove() since it may have already been removed due to a
         # previous unrelated call to this method, e.g. another job failed before the one that
         # caused this call.
         self._m_setScheduledJobs.discard(sjBlocked)
         if sjBlocked._m_setBlockedJobs:
            self._unschedule_jobs_blocked_by(sjBlocked._m_setBlockedJobs)


   def _get_verbose(self):
      return self._m_bVerbose

   def _set_verbose(self, bVerbose):
      self._m_bVerbose = bVerbose

   verbose = property(_get_verbose, _set_verbose, doc = """
      True if the exact commands invoked should be printed to stdout, of False if only a short
      description should.
   """)



####################################################################################################
# __main__

def _main(iterArgs):

   make = Make()
   iArg = 1
   iArgEnd = len(iterArgs)
   while iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.startswith('--'):
         if sArg == '--force-build':
            make.force_build = True
         elif sArg == '--dry-run':
            make.dry_run = True
         elif sArg == '--ignore-errors':
            make.ignore_errors = True
         elif sArg == '--keep-going':
            make.keep_going = True
         elif sArg == '--verbose':
            make.verbose = True
      elif sArg.startswith('-'):
         for sArgChar in sArg:
            if sArgChar == 'f':
               make.force_build = True
            elif sArgChar == 'i':
               make.ignore_errors = True
            elif sArgChar == 'k':
               make.keep_going = True
            elif sArgChar == 'n':
               make.dry_run = True
            elif sArgChar == 'v':
               make.verbose = True
      else:
         break
      iArg += 1

   # Expect the makefile path as the next argument.
   if iArg >= iArgEnd:
      sys.stderr.write('error: no makefile specified\n')
      return 1
   make.parse(iterArgs[iArg])
   iArg += 1

   # If there are more argument, they will be treated as target named, indicating that only a subset
   # of the targets should be built; otherwise all named targets will be built.
   if iArg < iArgEnd:
      iterTargets = set()
      while iArg < iArgEnd:
         iterTargets.add(make.get_target_by_name(sName))
         iArg += 1
   else:
      iterTargets = make.named_targets

   # Build all selected targets: first schedule the jobs building them, then run them.
   for tgt in iterTargets:
      make.schedule_target_jobs(tgt)
   return make.run_scheduled_jobs()


if __name__ == '__main__':
   sys.exit(_main(sys.argv))

