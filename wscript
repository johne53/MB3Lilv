#!/usr/bin/env python

import os
import shutil
import subprocess
import sys

from waflib import Options, Logs
from waflib.extras import autowaf

# Library and package version (UNIX style major, minor, micro)
# major increment <=> incompatible changes
# minor increment <=> compatible changes (additions)
# micro increment <=> no interface changes
LILV_VERSION       = '0.24.5'
LILV_MAJOR_VERSION = '0'

# Mandatory waf variables
APPNAME = 'lilv'        # Package name for waf dist
VERSION = LILV_VERSION  # Package version for waf dist
top     = '.'           # Source directory
out     = 'build'       # Build directory

test_plugins = [
    'bad_syntax',
    'failed_instantiation',
    'failed_lib_descriptor',
    'lib_descriptor',
    'missing_descriptor',
    'missing_name',
    'missing_plugin',
    'missing_port',
    'missing_port_name',
    'new_version',
    'old_version'
]

def options(ctx):
    ctx.load('compiler_c')
    ctx.load('compiler_cxx')
    ctx.load('python')
    autowaf.set_options(ctx, test=True)
    opt = ctx.get_option_group('Configuration options')
    autowaf.add_flags(
        opt,
        {'no-utils':           'do not build command line utilities',
         'bindings':           'build python bindings',
         'dyn-manifest':       'build support for dynamic manifests',
         'no-bash-completion': 'do not install bash completion script',
         'static':             'build static library',
         'no-shared':          'do not build shared library',
         'static-progs':       'build programs as static binaries'})

    opt.add_option('--default-lv2-path', type='string', default='',
                   dest='default_lv2_path',
                   help='default LV2 path to use if LV2_PATH is unset')

def configure(conf):
    autowaf.display_header('Lilv Configuration')
    conf.load('compiler_c', cache=True)
    try:
        conf.load('compiler_cxx', cache=True)
    except:
        pass

    if Options.options.bindings:
        try:
            conf.load('python', cache=True)
            conf.check_python_headers()
            autowaf.define(conf, 'LILV_PYTHON', 1);
        except:
            Logs.warn('Failed to configure Python (%s)\n' % sys.exc_info()[1])

    conf.load('autowaf', cache=True)
    autowaf.set_c_lang(conf, 'c99')

    conf.env.BASH_COMPLETION = not Options.options.no_bash_completion
    conf.env.BUILD_UTILS     = not Options.options.no_utils
    conf.env.BUILD_SHARED    = not Options.options.no_shared
    conf.env.STATIC_PROGS    = Options.options.static_progs
    conf.env.BUILD_STATIC    = (Options.options.static or
                                Options.options.static_progs)

    if not conf.env.BUILD_SHARED and not conf.env.BUILD_STATIC:
        conf.fatal('Neither a shared nor a static build requested')

    autowaf.check_pkg(conf, 'lv2', uselib_store='LV2',
                      atleast_version='1.14.0', mandatory=True)
    autowaf.check_pkg(conf, 'serd-0', uselib_store='SERD',
                      atleast_version='0.18.0', mandatory=True)
    autowaf.check_pkg(conf, 'sord-0', uselib_store='SORD',
                      atleast_version='0.14.0', mandatory=True)
    autowaf.check_pkg(conf, 'sratom-0', uselib_store='SRATOM',
                      atleast_version='0.4.0', mandatory=True)
    autowaf.check_pkg(conf, 'sndfile', uselib_store='SNDFILE',
                      atleast_version='1.0.0', mandatory=False)

    defines = ['_POSIX_C_SOURCE=200809L', '_BSD_SOURCE', '_DEFAULT_SOURCE']
    if conf.env.DEST_OS == 'darwin':
        defines += ['_DARWIN_C_SOURCE']

    rt_lib  = ['rt']
    if conf.env.DEST_OS == 'darwin' or conf.env.DEST_OS == 'win32':
        rt_lib = []

    autowaf.check_function(conf, 'c', 'lstat',
                           header_name = ['sys/stat.h'],
                           defines     = defines,
                           define_name = 'HAVE_LSTAT',
                           mandatory   = False)

    autowaf.check_function(conf, 'c', 'flock',
                           header_name = 'sys/file.h',
                           defines     = defines,
                           define_name = 'HAVE_FLOCK',
                           mandatory   = False)

    autowaf.check_function(conf, 'c', 'fileno',
                           header_name = 'stdio.h',
                           defines     = defines,
                           define_name = 'HAVE_FILENO',
                           mandatory   = False)

    autowaf.check_function(conf, 'c', 'clock_gettime',
                           header_name  = ['sys/time.h','time.h'],
                           defines      = ['_POSIX_C_SOURCE=200809L'],
                           define_name  = 'HAVE_CLOCK_GETTIME',
                           uselib_store = 'CLOCK_GETTIME',
                           lib          = rt_lib,
                           mandatory    = False)

    conf.check_cc(define_name = 'HAVE_LIBDL',
                  lib         = 'dl',
                  mandatory   = False)

    if Options.options.dyn_manifest:
        autowaf.define(conf, 'LILV_DYN_MANIFEST', 1)

    lilv_path_sep = ':'
    lilv_dir_sep  = '/'
    if conf.env.DEST_OS == 'win32':
        lilv_path_sep = ';'
        lilv_dir_sep = '\\\\'

    autowaf.define(conf, 'LILV_PATH_SEP', lilv_path_sep)
    autowaf.define(conf, 'LILV_DIR_SEP',  lilv_dir_sep)

    # Set default LV2 path
    lv2_path = Options.options.default_lv2_path
    if lv2_path == '':
        if conf.env.DEST_OS == 'darwin':
            lv2_path = lilv_path_sep.join(['~/Library/Audio/Plug-Ins/LV2',
                                           '~/.lv2',
                                           '/usr/local/lib/lv2',
                                           '/usr/lib/lv2',
                                           '/Library/Audio/Plug-Ins/LV2'])
        elif conf.env.DEST_OS == 'haiku':
            lv2_path = lilv_path_sep.join(['~/.lv2',
                                           '/boot/common/add-ons/lv2'])
        elif conf.env.DEST_OS == 'win32':
            lv2_path = lilv_path_sep.join(['%APPDATA%\\\\LV2',
                                           '%COMMONPROGRAMFILES%\\\\LV2'])
        else:
            libdirname = os.path.basename(conf.env.LIBDIR)
            lv2_path = lilv_path_sep.join(['~/.lv2',
                                           '/usr/%s/lv2' % libdirname,
                                           '/usr/local/%s/lv2' % libdirname])
    autowaf.define(conf, 'LILV_DEFAULT_LV2_PATH', lv2_path)

    autowaf.set_lib_env(conf, 'lilv', LILV_VERSION)
    conf.write_config_header('lilv_config.h', remove=False)

    autowaf.display_summary(
        conf,
        {'Default LV2_PATH':         conf.env.LILV_DEFAULT_LV2_PATH,
         'Utilities':                bool(conf.env.BUILD_UTILS),
         'Unit tests':               bool(conf.env.BUILD_TESTS),
         'Dynamic manifest support': bool(conf.env.LILV_DYN_MANIFEST),
         'Python bindings':          conf.is_defined('LILV_PYTHON')})

    conf.undefine('LILV_DEFAULT_LV2_PATH')  # Cmd line errors with VC++

def build_util(bld, name, defines, libs=''):
    obj = bld(features     = 'c cprogram',
              source       = name + '.c',
              includes     = ['.', './src', './utils'],
              use          = 'liblilv',
              target       = name,
              defines      = defines,
              install_path = '${BINDIR}')
    autowaf.use_lib(bld, obj, 'SERD SORD SRATOM LV2 ' + libs)
    if not bld.env.BUILD_SHARED or bld.env.STATIC_PROGS:
        obj.use = 'liblilv_static'
    if bld.env.STATIC_PROGS:
        if not bld.env.MSVC_COMPILER:
            obj.lib = ['m']
            obj.env.SHLIB_MARKER = obj.env.STLIB_MARKER
            obj.linkflags        = ['-static', '-Wl,--start-group']
    return obj

def build(bld):
    # C/C++ Headers
    includedir = '${INCLUDEDIR}/lilv-%s/lilv' % LILV_MAJOR_VERSION
    bld.install_files(includedir, bld.path.ant_glob('lilv/*.h'))
    bld.install_files(includedir, bld.path.ant_glob('lilv/*.hpp'))

    lib_source = '''
        src/collections.c
        src/instance.c
        src/lib.c
        src/node.c
        src/plugin.c
        src/pluginclass.c
        src/port.c
        src/query.c
        src/scalepoint.c
        src/state.c
        src/ui.c
        src/util.c
        src/world.c
        src/zix/tree.c
    '''.split()

    lib      = []
    libflags = ['-fvisibility=hidden']
    defines  = []
    if bld.is_defined('HAVE_LIBDL'):
        lib    += ['dl']
    if bld.env.DEST_OS == 'win32':
        lib = []
    if bld.env.MSVC_COMPILER:
        libflags = []

    # Pkgconfig file
    autowaf.build_pc(bld, 'LILV', LILV_VERSION, LILV_MAJOR_VERSION, [],
                     {'LILV_MAJOR_VERSION' : LILV_MAJOR_VERSION,
                      'LILV_PKG_DEPS'      : 'lv2 serd-0 sord-0 sratom-0',
                      'LILV_PKG_LIBS'      : ' -l'.join([''] + lib)})

    # Shared Library
    if bld.env.BUILD_SHARED:
        obj = bld(features        = 'c cshlib',
                  export_includes = ['.'],
                  source          = lib_source,
                  includes        = ['.', './src'],
                  name            = 'liblilv',
                  target          = 'lilv-%s' % LILV_MAJOR_VERSION,
                  vnum            = LILV_VERSION,
                  install_path    = '${LIBDIR}',
                  defines         = ['LILV_SHARED', 'LILV_INTERNAL'],
                  cflags          = libflags,
                  lib             = lib)
        autowaf.use_lib(bld, obj, 'SERD SORD SRATOM LV2')

    # Static library
    if bld.env.BUILD_STATIC:
        obj = bld(features        = 'c cstlib',
                  export_includes = ['.'],
                  source          = lib_source,
                  includes        = ['.', './src'],
                  name            = 'liblilv_static',
                  target          = 'lilv-%s' % LILV_MAJOR_VERSION,
                  vnum            = LILV_VERSION,
                  install_path    = '${LIBDIR}',
                  defines         = defines + ['LILV_INTERNAL'])
        autowaf.use_lib(bld, obj, 'SERD SORD SRATOM LV2')

    # Python bindings
    if bld.is_defined('LILV_PYTHON'):
        bld(features     = 'subst',
            is_copy      = True,
            source       = 'bindings/python/lilv.py',
            target       = 'lilv.py',
            install_path = '${PYTHONDIR}')

    if bld.env.BUILD_TESTS:
        import re

        test_libs      = lib
        test_cflags    = ['']
        test_linkflags = ['']
        if not bld.env.NO_COVERAGE:
            test_cflags    += ['--coverage']
            test_linkflags += ['--coverage']

        # Make a pattern for shared objects without the 'lib' prefix
        module_pattern = re.sub('^lib', '', bld.env.cshlib_PATTERN)
        shlib_ext = module_pattern[module_pattern.rfind('.'):]

        for p in ['test'] + test_plugins:
            obj = bld(features     = 'c cshlib',
                      source       = 'test/%s.lv2/%s.c' % (p, p),
                      name         = p,
                      target       = 'test/%s.lv2/%s' % (p, p),
                      install_path = None,
                      defines      = defines,
                      cflags       = test_cflags,
                      linkflags    = test_linkflags,
                      lib          = test_libs,
                      uselib       = 'LV2')
            obj.env.cshlib_PATTERN = module_pattern

        for p in test_plugins:
            if not bld.path.find_node('test/%s.lv2/test_%s.c' % (p, p)):
                continue

            obj = bld(features     = 'c cprogram',
                      source       = 'test/%s.lv2/test_%s.c' % (p, p),
                      target       = 'test/test_%s' % p,
                      includes     = ['.', './src'],
                      use          = 'liblilv_profiled',
                      install_path = None,
                      defines      = defines,
                      cflags       = test_cflags,
                      linkflags    = test_linkflags,
                      lib          = test_libs,
                      uselib       = 'LV2')
            autowaf.use_lib(bld, obj, 'SERD SORD SRATOM LV2')

        # Test plugin data files
        for p in ['test'] + test_plugins:
            for i in [ 'manifest.ttl.in', p + '.ttl.in' ]:
                bundle = 'test/%s.lv2/' % p
                bld(features     = 'subst',
                    source       = bundle + i,
                    target       = bundle + i.replace('.in', ''),
                    install_path = None,
                SHLIB_EXT    = shlib_ext)

        # Static profiled library (for unit test code coverage)
        obj = bld(features     = 'c cstlib',
                  source       = lib_source,
                  includes     = ['.', './src'],
                  name         = 'liblilv_profiled',
                  target       = 'lilv_profiled',
                  install_path = None,
                  defines      = defines + ['LILV_INTERNAL'],
                  cflags       = test_cflags,
                  linkflags    = test_linkflags,
                  lib          = test_libs)
        autowaf.use_lib(bld, obj, 'SERD SORD SRATOM LV2')

        # Unit test program
        testdir = os.path.abspath(autowaf.build_dir(APPNAME, 'test'))
        bpath   = os.path.join(testdir, 'test.lv2')
        bpath   = bpath.replace('\\', '/')
        testdir = testdir.replace('\\', '/')
        obj = bld(features     = 'c cprogram',
                  source       = 'test/lilv_test.c',
                  includes     = ['.', './src'],
                  use          = 'liblilv_profiled',
                  lib          = test_libs,
                  target       = 'test/lilv_test',
                  install_path = None,
                  defines      = (defines + ['LILV_TEST_BUNDLE=\"%s/\"' % bpath] +
                                  ['LILV_TEST_DIR=\"%s/\"' % testdir]),
                  cflags       = test_cflags,
                  linkflags    = test_linkflags)
        autowaf.use_lib(bld, obj, 'SERD SORD SRATOM LV2')

        # C++ API test
        if 'COMPILER_CXX' in bld.env:
            obj = bld(features     = 'cxx cxxprogram',
                      source       = 'test/lilv_cxx_test.cpp',
                      includes     = ['.', './src'],
                      use          = 'liblilv_profiled',
                      lib          = test_libs,
                      target       = 'test/lilv_cxx_test',
                      install_path = None,
                      cxxflags     = test_cflags,
                      linkflags    = test_linkflags)
            autowaf.use_lib(bld, obj, 'SERD SORD SRATOM LV2')

        if bld.is_defined('LILV_PYTHON'):
            # Copy Python unittest files
            for i in [ 'test_api.py' ]:
                bld(features     = 'subst',
                    is_copy      = True,
                    source       = 'bindings/test/python/' + i,
                    target       = 'bindings/' + i,
                    install_path = None)

            # Build bindings test plugin
            obj = bld(features     = 'c cshlib',
                      source       = 'bindings/test/bindings_test_plugin.c',
                      name         = 'bindings_test_plugin',
                      target       = 'bindings/bindings_test_plugin.lv2/bindings_test_plugin',
                      install_path = None,
                      defines      = defines,
                      cflags       = test_cflags,
                      linkflags    = test_linkflags,
                      lib          = test_libs,
                      uselib       = 'LV2')
            obj.env.cshlib_PATTERN = module_pattern

            # Bindings test plugin data files
            for i in [ 'manifest.ttl.in', 'bindings_test_plugin.ttl.in' ]:
                bld(features     = 'subst',
                    source       = 'bindings/test/' + i,
                    target       = 'bindings/bindings_test_plugin.lv2/' + i.replace('.in', ''),
                    install_path = None,
                    SHLIB_EXT    = shlib_ext)


    # Utilities
    if bld.env.BUILD_UTILS:
        utils = '''
            utils/lilv-bench
            utils/lv2info
            utils/lv2ls
        '''
        for i in utils.split():
            build_util(bld, i, defines)

        if bld.env.HAVE_SNDFILE:
            obj = build_util(bld, 'utils/lv2apply', defines, 'SNDFILE')

        # lv2bench (less portable than other utilities)
        if bld.is_defined('HAVE_CLOCK_GETTIME') and not bld.env.STATIC_PROGS:
            obj = build_util(bld, 'utils/lv2bench', defines)
            if bld.env.DEST_OS != 'win32' and bld.env.DEST_OS != 'darwin':
                obj.lib = ['rt']

    # Documentation
    autowaf.build_dox(bld, 'LILV', LILV_VERSION, top, out)

    # Man pages
    bld.install_files('${MANDIR}/man1', bld.path.ant_glob('doc/*.1'))

    # Bash completion
    if bld.env.BASH_COMPLETION:
        bld.install_as(
            '${SYSCONFDIR}/bash_completion.d/lilv', 'utils/lilv.bash_completion')

    bld.add_post_fun(autowaf.run_ldconfig)
    if bld.env.DOCS:
        bld.add_post_fun(fix_docs)

def fix_docs(ctx):
    if ctx.cmd == 'build':
        autowaf.make_simple_dox(APPNAME)

def upload_docs(ctx):
    import glob
    os.system('rsync -ravz --delete -e ssh build/doc/html/ drobilla@drobilla.net:~/drobilla.net/docs/lilv/')
    for page in glob.glob('doc/*.[1-8]'):
        os.system('soelim %s | pre-grohtml troff -man -wall -Thtml | post-grohtml > build/%s.html' % (page, page))
        os.system('rsync -avz --delete -e ssh build/%s.html drobilla@drobilla.net:~/drobilla.net/man/' % page)

def test(ctx):
    assert ctx.env.BUILD_TESTS, "You have run waf configure without the --test flag. No tests were run."
    autowaf.pre_test(ctx, APPNAME)
    if ctx.is_defined('LILV_PYTHON'):
        os.environ['LD_LIBRARY_PATH'] = os.getcwd()
        autowaf.run_tests(ctx, APPNAME, ['python -m unittest discover bindings/'])
    os.environ['PATH'] = 'test' + os.pathsep + os.getenv('PATH')

    Logs.pprint('GREEN', '')
    autowaf.run_test(ctx, APPNAME, 'lilv_test', dirs=['./src','./test'], name='lilv_test')

    for p in test_plugins:
        test_prog = 'test_' + p + ' ' + ('test/%s.lv2/' % p)
        if os.path.exists('test/test_' + p):
            autowaf.run_test(ctx, APPNAME, test_prog, 0,
                             dirs=['./src','./test','./test/%s.lv2' % p])

    autowaf.post_test(ctx, APPNAME)
    try:
        shutil.rmtree('state')
    except:
        pass

def lint(ctx):
    "checks code for style issues"
    import subprocess
    cmd = ("clang-tidy -p=. -header-filter=.* -checks=\"*," +
           "-clang-analyzer-alpha.*," +
           "-google-readability-todo," +
           "-llvm-header-guard," +
           "-llvm-include-order," +
           "-misc-unused-parameters," +
           "-readability-else-after-return\" " +
           "$(find .. -name '*.c')")
    subprocess.call(cmd, cwd='build', shell=True)

def posts(ctx):
    path = str(ctx.path.abspath())
    autowaf.news_to_posts(
        os.path.join(path, 'NEWS'),
        {'title'        : 'Lilv',
         'description'  : autowaf.get_blurb(os.path.join(path, 'README')),
         'dist_pattern' : 'http://download.drobilla.net/lilv-%s.tar.bz2'},
        { 'Author' : 'drobilla',
          'Tags'   : 'Hacking, LAD, LV2, Lilv' },
        os.path.join(out, 'posts'))
