import setuptools
from setuptools.command.install import install
import logging
import sys
import os
import subprocess
import shutil
import glob
import traceback

# Logging

logging.basicConfig()
_log = logging.getLogger('setup')

# Globals

version = open('VERSION').read().strip()
packages = setuptools.find_packages("lib")
g_with_jupyter = False

server_languages = ["python_server"]
client_languages = ["python", "javascript", "perl", "java"]

language_properties = {
    "python_server": {
        "style": "py:twisted",
        "generated_dir": "gen-py.twisted",
        "copy_files": ["constants.py", "ttypes.py", "thrift_service.py"]
    },
    "python": {
        "style": "py:new_style",
        "generated_dir": "gen-py",
        "copy_files": ["constants.py", "ttypes.py", "thrift_service.py"],
        "rename_files": {"thrift_service.py": "thrift_client.py"}
    },
    "javascript": {
        "style": "js:jquery",
        "generated_dir": "gen-js",
        "copy_files": ["taxon_types.js", "thrift_service.js"]
    },
    "perl": {
        "style": "perl",
        "generated_dir": "gen-perl",
        "copy_files": ["Constants.pm", "Types.pm", "thrift_service.pm"]
    },
    "java": {
        "style": "java:sorted_containers",
        "generated_dir": "gen-java",
        "copy_files": ["ServiceException.java", "taxonConstants.java", "thrift_service.java"]
    }
}


# Functions

def filter_args():
    global g_with_jupyter
    setup_args = sys.argv[1:]

    # TODO: Put this new option into --help output

    if "--jupyter" in setup_args:
        g_with_jupyter = True
        setup_args.remove("--jupyter")

    return setup_args


def get_dependencies():
    def parse_requirements(filename):
        packages = list()
    
        with open(filename, 'r') as req_file:
            req_lines = req_file.read().splitlines()
        
            for line in req_lines:
                if line.strip() == "":
                    pass
                elif line.startswith("-r"):
                    packages.extend(parse_requirements(line.split(" ")[-1]))
                else:
                    packages.append(line)
        return packages

    setup_args = sys.argv[1:]

    if g_with_jupyter:
        install_requires = parse_requirements(
            os.path.join(os.path.dirname(__file__),"requirements-jupyter.txt"))
        open(os.path.join(os.path.dirname(__file__),'exclude-tests.txt'), 'w').write('') # clear it
    else:
        _log.warn("--jupyter not specified, so using minimal install "
                  "without packages in doekbase.data_api.interactive")
        exclude_pkg = 'doekbase.data_api.interactive'

        global packages
        if exclude_pkg in packages:
            packages.remove(exclude_pkg)

        install_requires = parse_requirements(
            os.path.join(os.path.dirname(__file__),"requirements.txt"))
        open(os.path.join(os.path.dirname(__file__),'exclude-tests.txt'), 'w')\
            .write('lib/' + exclude_pkg.replace('.', '/'))
        # clear it

    return install_requires

def call_command(command, is_thrift=False):
    """Better exception when calling a command"""
    try:
        errno = subprocess.call(command)
    except Exception as err:
        if isinstance(command, list):
            cstr = ' '.join(command)
        else:
            cstr = command
        if is_thrift:
            sys.stderr.write("==\nUnable to run `thrift` executable, is Apache "
                             "Thrift installed? See https://thrift.apache.org/ "
                             "for help\n==\n")
            raise RuntimeError('Cannot run Thrift ({c}): {'
                               'e}'.format(c=cstr, e=err))
        else:
            raise RuntimeError('Command "{c}" failed: {e}'.format(c=cstr,
                                                                  e=err))
    return errno

class BuildThriftClients(setuptools.Command):
    """Build command for generating Thrift client code"""

    user_options = []

    def initialize_options(self):
        pass


    def finalize_options(self):
        pass


    def run(self):
        try:
            self._try_run()
        except Exception as err:
            print("ERROR in BuildThriftClients.run: {}".format(err))
            #traceback.print_exc()
            raise

    def _try_run(self):
        for dirpath, dirnames, filenames in os.walk("thrift/specs"):
            for f in filenames:
                if f.endswith(".thrift"):
                    spec_path = os.path.abspath(os.path.join(dirpath, f))
                    thrift_path = f.split(".")[0]

                    for target in client_languages:
                        command = ["thrift", "-r", "--gen", language_properties[target]["style"], spec_path]
                        _log.info("{}: Thrift command = {}".format(target,
                                                                   command))
                        errno = call_command(command, is_thrift=True)
                        if errno != 0:
                            raise Exception("Thrift build for {} failed with : {}".format(target, errno))

                        generated_files = glob.glob(language_properties[target]["generated_dir"] + "/*/*")

                        if len(generated_files) == 0:
                            generated_files = glob.glob(language_properties[target]["generated_dir"] + "/*")

                        copied = False
                        for x in generated_files:
                            for name in language_properties[target]["copy_files"]:
                                if name in x:
                                    destination = spec_path.rsplit("/",1)[0].replace("specs", "stubs/" + target)
                                    shutil.copyfile(x, os.path.join(destination, name))
                                    copied = True
                        if not copied:
                            raise Exception("Unable to find thrift generated files to copy!")
                        shutil.rmtree(language_properties[target]["generated_dir"])



class CustomInstall(install):
    """Custom install step for thrift generated code"""

    def run(self):
        try:
            self._try_run()
        except Exception as err:
            print("ERROR in CustomInstall.run: {}".format(err))
            #traceback.print_exc()
            raise

    def _try_run(self):

        start_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),"thrift/specs")

        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                if f.endswith(".thrift"):
                    #TODO - modify version string in .thrift before code generation
                    spec_path = os.path.abspath(os.path.join(dirpath, f))
                    thrift_path = f.split(".")[0]

                    command = ["thrift", "-r", "--gen", language_properties[
                        "python_server"]["style"], spec_path]
                    errno = call_command(command, is_thrift=True)
                    if errno != 0:
                        raise Exception("Thrift build for python service failed with : {}".format(errno))

                    generated_files = glob.glob(language_properties["python_server"]["generated_dir"] + "/*/*")

                    if len(generated_files) == 0:
                        generated_files = glob.glob(language_properties["python_server"]["generated_dir"] + "/*")

                    copied = False
                    for x in generated_files:
                        for name in language_properties["python_server"]["copy_files"]:
                            if name in x:
                                destination = os.path.join(dirpath.replace("thrift/specs", "lib/doekbase/data_api") + "/service/", name)
                                shutil.copyfile(x, destination)
                                copied = True
                    if not copied:
                        raise Exception("Unable to find thrift service generated files to copy!")
                    shutil.rmtree(language_properties["python_server"]["generated_dir"])

                    command = ["thrift", "-r", "--gen", language_properties["python"]["style"], spec_path]
                    errno = call_command(command, is_thrift=True)
                    if errno != 0:
                        raise Exception("Thrift build for python client failed with : {}".format(errno))

                    generated_files = glob.glob(language_properties["python"]["generated_dir"] + "/*/*")

                    if len(generated_files) == 0:
                        generated_files = glob.glob(language_properties["python"]["generated_dir"] + "/*")

                    renamed = False
                    for x in generated_files:
                        for name in language_properties["python"]["rename_files"]:
                            if name in x:
                                destination = os.path.join(dirpath.replace("thrift/specs", "lib/doekbase/data_api") + "/service/", language_properties["python"]["rename_files"][name])
                                shutil.copyfile(x, destination)
                                renamed = True
                    if not renamed:
                        raise Exception("Unable to find thrift client generated files to copy!")
                    shutil.rmtree(language_properties["python"]["generated_dir"])

        # adapted from http://stackoverflow.com/questions/14441955/how-to-perform-custom-build-steps-in-setup-py
        ret = None

        if self.old_and_unmanageable or self.single_version_externally_managed:
            ret = install.run(self)
        else:
            caller = sys._getframe(2)
            caller_module = caller.f_globals.get('__name__','')
            caller_name = caller.f_code.co_name

            if caller_module != "distutils.dist" or caller_name != "run_commands":
                install.run(self)
            else:
                self.do_egg_install()

        return ret

config = {
    "description": "KBase Data API",
    "author": "Matt Henderson",
    "url": "https://github.com/kbase/data_api/",
    "download_url": "https://github.com/kbase/data_api/stuff?download",
    "author_email": "mhenderson@lbl.gov",
    "version": version,
    "setup_requires": ["six"],
    "tests_require": ["nose", "nose-timer", "codecov"],
    "packages": packages,
    "scripts": ["bin/data_api_demo.py",
                "bin/data_api_benchmark.py",
                "bin/dump_wsfile",
                "bin/taxon_start_service.py",
                "bin/taxon_client_driver.py",
                "bin/extract_thrift_docs"],
    "name": "doekbase_data_api",
    "entry_points": {
        'nose.plugins.0.10': [
            'wsurl = doekbase.data_api.tests.nose_plugin_wsurl:WorkspaceURL'
        ]
    },
    "zip_safe": True
}

setuptools.setup(package_dir = {'': 'lib'},
                 script_args = filter_args(),
                 install_requires = get_dependencies(),
                 cmdclass = {'install': CustomInstall,
                             'build_thrift_clients': BuildThriftClients},
                 **config)
