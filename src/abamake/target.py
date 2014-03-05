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

"""Classes implementing different types of build target, each aware of how to build itself."""

import os
import re
import sys

import make



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


   def __init__(self, mk, sName = None):
      """Constructor. Generates the target’s file path by calling Target._generate_file_path(), then
      adds itself to the Make instance’s target lists.

      Make mk
         Make instance.
      str sName
         See Target.name.
      """

      self._m_sName = sName
      self._m_sFilePath = self._generate_file_path(mk)
      # Add self to any applicable targets lists.
      mk._add_target(self)


   def add_dependency(self, tgtDep):
      """Adds a target dependency.

      Target tgtDep
         Dependency.
      """

      if self._m_setDeps is None:
         self._m_setDeps = set()
      self._m_setDeps.add(tgtDep)


   def build(self, mk, iterBlockingJobs):
      """Builds the output, using the facilities provided by the specified Make instance and
      returning the last job scheduled.

      Make mk
         Make instance.
      iterable(Job*) iterBlockingJobs
         Jobs that should block the first one scheduled to build this target.
      Job return
         Last job scheduled if the target scheduled jobs to be rebuilt, of None if it was already
         current.
      """

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


   def _generate_file_path(self, mk):
      """Generates and returns a file path for the target, based on other member varialbes set
      beforehand and the configuration of the provided Make instance. Called by Target.__init__().

      The default implementation doesn’t generate a file path because no output file is assumed.

      Make mk
         Make instance.
      str return
         Target file path; same as Target.file_path.
      """

      # No output file.
      return None


   def _is_build_needed(self, mk, iterBlockingJobs, iterFilesToCheck):
      """Checks if a build of this target should be scheduled.

      Make mk
         Make instance.
      iterable(Job*) iterBlockingJobs
         Jobs that should block the first one scheduled to build this target.
      iterable(str*) iterFilesToCheck
         List of file paths to be checked for changes.
      tuple(bool, iterable(str*)) return
         Tuple containing the response (True if a build is needed, or False otherwise) and a list of
         changed files (or None if no file changes are detected).
      """

      # Get a list of changed files.
      if iterFilesToCheck:
         iterChangedFiles = mk.file_metadata_changed(iterFilesToCheck)
      else:
         iterChangedFiles = None

      # Choose a name to use for self, for logging purposes.
      sSelf = self._m_sFilePath or self._m_sName

      # See if this build is really necessary.
      if iterBlockingJobs:
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write(sSelf + ': rebuilding due to dependencies being rebuilt\n')
      elif iterChangedFiles:
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write(sSelf + ': rebuilding due to detected changes\n')
      elif mk.force_build:
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write(sSelf + ': up-to-date, but rebuild forced\n')
      else:
         # No dependencies being rebuilt, source up-to-date: no need to rebuild.
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write(sSelf + ': up-to-date\n')
         return False, None

      # Build needed.
      return True, iterChangedFiles


   def _get_name(self):
      return self._m_sName

   name = property(_get_name, doc = """Name of the target.""")


   def parse_makefile_child(self, mk, elt):
      """Validates and processes the specified child element of the target’s <target> element.

      Make mk
         Make instance.
      xml.dom.Element elt
         Element to parse.
      bool return
         True if elt was recognized and parsed, or False if it was not expected.
      """

      # Default implementation: expect no child elements.
      return False



####################################################################################################
# ProcessedSourceTarget

class ProcessedSourceTarget(Target):
   """Intermediate target generated by processing a source file. The output file will be placed in a
   int/ directory relative to the output base directory.
   """

   # See ProcessedSourceTarget.final_output_target.
   _m_clsFinalOutputTarget = None
   # See ProcessedSourceTarget.source_file_path.
   _m_sSourceFilePath = None


   def __init__(self, mk, sName, sSourceFilePath):
      """Constructor. See Target.__init__().

      Make mk
         Make instance.
      str sName
         See Target.name.
      str sSourceFilePath
         See ProcessedSourceTarget.source_file_path.
      """

      self._m_sSourceFilePath = sSourceFilePath
      super().__init__(mk, sName)


   def build(self, mk, iterBlockingJobs):
      """See Target.build()."""

      # TODO: check for additional changed external dependencies.
      bBuildNeeded, iterChangedFiles = self._is_build_needed(
         mk, iterBlockingJobs, (self.file_path, self.source_file_path)
      )
      if not bBuildNeeded:
         return None
      # Instantiate the appropriate tool, and have it schedule any applicable jobs.
      return self._get_tool(mk).schedule_jobs(mk, iterBlockingJobs, iterChangedFiles)


   def _get_final_output_target(self):
      return self._m_clsFinalOutputTarget

   def _set_final_output_target(self, clsFinalOutputTarget):
      self._m_clsFinalOutputTarget = clsFinalOutputTarget

   final_output_target = property(_get_final_output_target, _set_final_output_target, doc = """
      Kind of output that ProcessedSourceTarget.build() will aim for when generating the object
      file, e.g. by passing -fPIC for a C++ source file when compiling it for a shared object.
   """)


   def _generate_file_path(self, mk):
      """See Target._generate_file_path()."""

      return os.path.join(mk.output_dir, 'int', self._m_sSourceFilePath)


   def _get_tool(self, mk):
      """Instantiates and prepares the tool to build the target.

      Make mk
         Make instance.
      Tool return
         Ready-to-use tool.
      """

      cxx = mk.cxxcompiler()
      cxx.set_output(self.file_path, self.final_output_target)
      cxx.add_input(self.source_file_path)
      # TODO: add file-specific flags.
      return cxx


   def _get_source_file_path(self):
      return self._m_sSourceFilePath

   source_file_path = property(_get_source_file_path, doc = """
      Source from which the target is built.
   """)



####################################################################################################
# CxxPreprocessedTarget

class CxxPreprocessedTarget(ProcessedSourceTarget):
   """Preprocessed C++ source target."""

   def _generate_file_path(self, mk):
      """See ProcessedSourceTarget._generate_file_path()."""

      return super()._generate_file_path(mk) + '.i'


   def _get_tool(self, mk):
      """See ProcessedSourceTarget._get_tool(). Implemented using CxxObjectTarget._get_tool()."""

      cxx = CxxObjectTarget._get_tool(self, mk)
      cxx.add_flags(make.tool.CxxCompiler.CFLAG_PREPROCESS_ONLY)
      return cxx



####################################################################################################
# ObjectTarget

class ObjectTarget(ProcessedSourceTarget):
   """Intermediate object target."""

   def _generate_file_path(self, mk):
      """See ProcessedSourceTarget._generate_file_path()."""

      return super()._generate_file_path(mk) + mk.cxxcompiler.object_suffix



####################################################################################################
# CxxObjectTarget

class CxxObjectTarget(ObjectTarget):
   """C++ intermediate object target."""

   def _get_tool(self, mk):
      """See ObjectTarget._get_tool()."""

      cxx = mk.cxxcompiler()
      cxx.set_output(self.file_path, self.final_output_target)
      cxx.add_input(self.source_file_path)
      # TODO: add file-specific flags.
      return cxx



####################################################################################################
# ExecutableTarget

class ExecutableTarget(Target):
   """Executable program target. The output file will be placed in a bin/ directory relative to the
   output base directory.
   """

   # List of dynamic libraries against which the target will be linked. Each item is either a Target
   # instance (for libraries/object files that can be built by the same makefile) or a string (for
   # external files).
   _m_listLinkerInputs = None


   def add_linker_input(self, oLib):
      """Adds a library dependency. Similar to Target.add_dependency(), but does not implicitly add
      oLib as a dependency.

      object oLib
         Library dependency. Can be a Target(-derived class) instance or a string.
      """

      if self._m_listLinkerInputs is None:
         self._m_listLinkerInputs = []
      self._m_listLinkerInputs.append(oLib)


   def build(self, mk, iterBlockingJobs):
      """See Target.build()."""

      lnk = mk.linker()
      lnk.set_output(self.file_path, type(self))

      # Due to the different types of objects in _m_listLinkerInputs and the fact we want to iterate
      # over that list only once, combine building the list of files to be checked for changes with
      # collecting linker inputs.
      listFilesToCheck = [self.file_path]
      # At this point all the dependencies are available, so add them as inputs.
      for oDep in self._m_listLinkerInputs or []:
         if isinstance(oDep, str):
            listFilesToCheck.append(oDep)
            # Strings go directly to the linker’s command line, assuming that they are external
            # libraries to link to.
            lnk.add_input_lib(oDep)
         else:
            listFilesToCheck.append(oDep.file_path)
            if isinstance(oDep, ObjectTarget):
               lnk.add_input(oDep.file_path)
            elif isinstance(oDep, DynLibTarget):
               lnk.add_input_lib(oDep.name)
               # Since we’re linking to a library built by this makefile, make sure to add the
               # output lib/ directory to the library search path.
               lnk.add_lib_path(os.path.join(mk.output_dir, 'lib'))
            else:
               raise Exception('unclassified linker input: {}'.format(oDep.file_path))

      # TODO: check for additional changed external dependencies.
      bBuildNeeded, iterChangedFiles = self._is_build_needed(mk, iterBlockingJobs, listFilesToCheck)
      if not bBuildNeeded:
         return None

      return lnk.schedule_jobs(mk, iterBlockingJobs, iterChangedFiles)


   def _generate_file_path(self, mk):
      """See Target._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(mk.output_dir, 'bin', '' + self.name + '')


   def parse_makefile_child(self, mk, elt):
      """See Target.parse_makefile_child()."""

      if elt.nodeName == 'source':
         # Pick the correct target class based on the file name extension.
         sFilePath = elt.getAttribute('path')
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            clsObjTarget = CxxObjectTarget
         else:
            raise Exception('unsupported source file type')
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(mk, None, sFilePath)
         # Add the target as a dependency to this target.
         tgtObj.final_output_target = type(self)
         self.add_dependency(tgtObj)
         self.add_linker_input(tgtObj)
         return True
      if elt.nodeName == 'dynlib':
         # Check if this makefile can build this dynamic library.
         sName = elt.getAttribute('name')
         # If the library was in the dictionary (i.e. it’s built by this makefile), assign it as a
         # dependency of self; else just add the library name (hence passing sName as 2nd argument
         # to mk.get_target_by_name()).
         oDynLib = mk.get_target_by_name(sName, sName)
         if oDynLib is not sName:
            self.add_dependency(oDynLib)
         self.add_linker_input(oDynLib)
         return True
      if elt.nodeName == 'unittest':
         # A unit test must be built after the target it’s supposed to test.
         sName = elt.getAttribute('name')
         tgtUnitTest = mk.get_target_by_name(sName, None)
         if tgtUnitTest is None:
            raise Exception(
               'could not find definition of referenced unit test: {}'.format(sName)
            )
         tgtUnitTest.add_dependency(self)
         return True
      return super().parse_makefile_child(mk, elt)



####################################################################################################
# DynLibTarget

class DynLibTarget(ExecutableTarget):
   """Dynamic library target. The output file will be placed in a lib/ directory relative to the
   output base directory.
   """

   def _generate_file_path(self, mk):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change 'lib' + '.so' from hardcoded to computed by a Platform class.
      return os.path.join(mk.output_dir, 'lib', 'lib' + self.name + '.so')


   def parse_makefile_child(self, mk, elt):
      """See ExecutableTarget.parse_makefile_child()."""

      # This implementation does not allow more element types than the base class’ version.
      if not super().parse_makefile_child(mk, elt):
         return False
      # Apply additional logic on the recognized element.
      if elt.nodeName == 'unittest':
         sName = elt.getAttribute('name')
         tgtUnitTest = mk.get_target_by_name(sName)
         # If tgtUnitTest generates an executable, have it link to this library.
         if isinstance(tgtUnitTest, ExecutableTarget):
            tgtUnitTest.add_linker_input(self)
      return True



####################################################################################################
# UnitTestTarget

class UnitTestTarget(Target):
   """Generic unit test target."""


   def parse_makefile_child(self, mk, elt):
      """See Target.parse_makefile_child()."""

      if elt.nodeName == 'unittest':
         raise SyntaxError('<unittest> not allowed in <target type="unittest">')
      return super().parse_makefile_child(mk, elt)



####################################################################################################
# ComparisonUnitTestTarget

class ComparisonUnitTestTarget(UnitTestTarget):
   """Unit test target that compares the output of a tool (e.g. C preprocessor) against a file with
   the expected output.
   """

   # Path to the file containing the expected command output.
   _m_sExpectedOutputFilePath = None


   def build(self, mk, iterBlockingJobs):
      """See Target.build(). In addition to building the unit test, it also schedules its execution.
      """

      # Find the dependency target that generates the output we want to compare.
      for tgt in self._m_setDeps or []:
         if isinstance(tgt, ProcessedSourceTarget):
            tgtToCompare = tgt
            break

      bBuildNeeded, iterChangedFiles = self._is_build_needed(
         mk, iterBlockingJobs, (self._m_sExpectedOutputFilePath, tgtToCompare.file_path)
      )
      if not bBuildNeeded:
         return None

      listArgs = ['cmp', '-s', tgtToCompare.file_path, self._m_sExpectedOutputFilePath]
      return make.ExternalCommandJob(
         mk, iterBlockingJobs, ('CMP', self.name), iterChangedFiles, listArgs
      )


   def parse_makefile_child(self, mk, elt):
      """See UnitTestTarget.parse_makefile_child()."""

      if elt.nodeName == 'source':
         # Check if we already found a <source> child element (dependency).
         for tgt in self._m_setDeps or []:
            if isinstance(tgt, ProcessedSourceTarget):
               raise Exception(
                  ('a tool output comparison like “{}” unit test can only have a single <source> ' +
                     'element').format(self.name)
               )
         # Pick the correct target class based on the file name extension.
         sFilePath = elt.getAttribute('path')
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            clsObjTarget = CxxPreprocessedTarget
         else:
            raise Exception('unsupported source file type')
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(mk, None, sFilePath)
         # Add the target as a dependency to this target.
         self.add_dependency(tgtObj)
         return True
      if elt.nodeName == 'expected-output':
         self._m_sExpectedOutputFilePath = elt.getAttribute('path')
         return True
      return super().parse_makefile_child(mk, elt)



####################################################################################################
# ExecutableUnitTestTarget

class ExecutableUnitTestTarget(ExecutableTarget, UnitTestTarget):
   """Executable unit test target. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.
   """

   # Path to the script file that will be invoked to execute the unit test.
   _m_sScriptFilePath = None


   def build(self, mk, iterBlockingJobs):
      """See ExecutableTarget.build(). In addition to building the unit test, it also schedules its
      execution.
      """

      jobBuild = super().build(mk, iterBlockingJobs)
      # If to build the unit test executable we scheduled any jobs, make sure that the metadata for
      # the jobs’ output is updated and that the unit test execution depends on the build job(s).
      if jobBuild:
         tplBlockingJobs = (jobBuild, )
         tplDeps = (self.file_path, )
      else:
         # No need to block the unit test job with iterBlockingJobs: if jobBuild is None,
         # iterBlockingJobs must be None as well, or else we would’ve scheduled jobs in
         # Target.build().
         assert(not iterBlockingJobs)
         tplBlockingJobs = None
         tplDeps = None

      if self._m_sScriptFilePath:
         tplArgs = (self._m_sScriptFilePath, self.file_path)
      else:
         tplArgs = (self.file_path, )
      return make.ExternalCommandJob(mk, tplBlockingJobs, ('TEST', self.name), tplDeps, tplArgs)


   def _generate_file_path(self, mk):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(mk.output_dir, 'bin', 'unittest', '' + self.name + '')


   def parse_makefile_child(self, mk, elt):
      """See ExecutableTarget.parse_makefile_child() and UnitTestTarget.parse_makefile_child()."""

      if elt.nodeName == 'script':
         self._m_sScriptFilePath = elt.getAttribute('path')
         # TODO: support <script name="…"> to refer to a program built by the same makefile.
         # TODO: support more attributes, such as command-line args for the script.
         return True
      if ExecutableTarget.parse_makefile_child(self, mk, elt):
         return True
      return UnitTestTarget.parse_makefile_child(self, mk, elt)

