from __future__ import print_function
import subprocess
import os
import sys
import argparse
from jinja2 import Template
from pyspin.spin import make_spin, Default
import time


def package_root():
    return os.path.dirname(__file__) + '/'


def hooks_path(python_version, production):
    # if production:
    #     return '{}/lib/python{}/site-packages/cloudfn/hooks'.format(cache_dir(python_version), python_version)
    return '{}hooks'.format(package_root())


def cache_dir(python_version):
    return 'pip-cache-{}'.format((python_version))


def image_name(python_version):
    return 'pycloudfn-builder{}'.format(python_version)


def docker_path():
    return '{}docker/'.format(package_root())


def output_name():
    return 'func'


def get_django_settings():
    m = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    if m == '':
        return m
    return 'DJANGO_SETTINGS_MODULE={}'.format(m)


def dockerfile(python_version):
    return 'DockerfilePython{}'.format(python_version.replace('.', '-'))


def pip_prefix(python_version):
    return 'python{} -m '.format(python_version)


def build_in_docker(file_name, python_version, production_image):
    cwd = os.getcwd()
    cmds = []
    if not production_image:
        cmds.extend([
            'docker', 'build', '-f', docker_path() + dockerfile(python_version),
            '-t', image_name(python_version), docker_path(), '&&'
        ])

    cmds = cmds + ['docker', 'run', '--rm', '-ti', '-v', cwd + ':/app']

    if production_image:
        cmds.append(production_image)
    else:
        cmds.append(image_name(python_version))

    inner_cmd = ' '.join([
        'cd /app && \\\n',
        'test -d cloudfn || mkdir cloudfn && cd cloudfn && \\\n',
        'test -d {cache_dir} || virtualenv  -p python{python_version} {cache_dir} && \\\n',
        '. {cache_dir}/bin/activate && \\\n',
        'test -f ../requirements.txt && \\\n',
        '{pip_prefix}pip install -r ../requirements.txt || echo no requirements.txt present && \\\n',
        '{django_settings}',
        ' '.join(build(file_name, python_version, True)),
    ]).format(
        cache_dir=cache_dir(python_version),
        python_version=python_version,
        pip_prefix=pip_prefix(python_version),
        django_settings=get_django_settings()
    )
    cmds = cmds + [
        '/bin/bash',
        '-c',
        '\'{}\''.format(inner_cmd),
    ]
    return cmds


def build(file_name, python_version, production):
    cachedir = cache_dir(python_version)
    base = [
        'pyinstaller'.format(cachedir),
        '../{}'.format(file_name), '-y', '-n', output_name(),
        '--clean', '--onedir',
        '--paths', '../',
        '--additional-hooks-dir', hooks_path(python_version, production),
        '--runtime-hook',
        hooks_path(python_version, production) + '/unbuffered.py',
        '--hidden-import', 'htmlentitydefs',
        '--hidden-import', 'HTMLParser',
        '--hidden-import', 'Cookie',
        '--exclude-module', 'jinja2.asyncsupport',
        '--exclude-module', 'jinja2.asyncfilters',
    ]
    prefix = ''
    if os.path.isdir(prefix + './cloudfn-hooks'):
        base.append('--additional-hooks-dir')
        base.append('../cloudfn-hooks')
    if os.path.isfile(prefix + './.hidden-imports'):
        with open(prefix + '.hidden-imports') as f:
            for line in f:
                if not f == '':
                    base.append('--hidden-import')
                    base.append(line.rstrip())
    if not production:
        base.insert(0, 'test -d cloudfn || mkdir cloudfn && cd cloudfn && ')
    return base


def build_cmd(file_name, python_version, production, production_image):
    if production:
        return build_in_docker(file_name, python_version, production_image)
    return build(file_name, python_version, production)


def build_function(function_name, file_name, trigger_type, python_version, production, production_image, verbose):

    start = time.time()

    message = '\n'.join(['',
        r"                        _                 _         __       ",
        r"                       | |               | |       / _|      ",
        r" _ __  _   _ ______ ___| | ___  _   _  __| |______| |_ _ __  ",
        r"| '_ \| | | |______/ __| |/ _ \| | | |/ _` |______|  _| '_ \ ",
        r"| |_) | |_| |     | (__| | (_) | |_| | (_| |      | | | | | |",
        r"| .__/ \__, |      \___|_|\___/ \__,_|\__,_|      |_| |_| |_|",
        r"| |     __/ |                                                ",
        r"|_|    |___/                                                 ",
        '',
        'Function: {function_name}',
        'File: {file_name}',
        'Trigger: {trigger_type}',
        'Python version: {python_version}',
        'Production: {production}',
        'Production Image: {production_image}',
    ])
    print(message.format(
        function_name=function_name,
        file_name=file_name,
        trigger_type=trigger_type,
        python_version=python_version,
        production=production,
        production_image=production_image)
    )

    stdout = subprocess.PIPE
    stderr = subprocess.STDOUT
    if verbose:
        stdout = sys.stdout
        stderr = sys.stderr
        print('')
        print('Running build command:')
        print(' '.join(build_cmd(file_name, python_version, production, production_image)))

    (p, output) = run_build_cmd(
        ' '.join(build_cmd(file_name, python_version, production, production_image)),
        stdout,
        stderr)
    if p.returncode == 0:
        build_javascript(function_name, trigger_type)
    else:
        print('\n'.join([
            '',
            'Build failed!',
        ]))
        if output:
            print('See the build output below for what might have went wrong:')
            print(output[0])
        sys.exit(p.returncode)
    (c, co) = cleanup()
    if c.returncode == 0:
        end = time.time()
        message = '\n'.join([
            '',
            'Elapsed time: {elapsed}s',
            'Output: ./cloudfn/target/index.js'])
        print(message.format(elapsed=round((end - start), 1)))
    else:
        print('\nSomething went wrong when cleaning up: ' + co[0])
        sys.exit(c.returncode)


@make_spin(Default, 'Building, go grab a coffee...')
def run_build_cmd(cmd, stdout, stderr):
    p = subprocess.Popen(
        cmd,
        stdout=stdout,
        stderr=stderr,
        shell=True)
    output = p.communicate()
    return (p, output)


@make_spin(Default, 'Generating javascript...')
def build_javascript(function_name, trigger_type):
    js = open(package_root() + 'template/index.js').read()
    t = Template(js)
    rendered_js = t.render(config={
        'output_name': output_name(),
        'function_name': function_name,
        'trigger_http': trigger_type == 'http',
    })
    open('cloudfn/index.js', 'w').write(rendered_js)
    output = '\n'.join([
        '{',
        '  "name": "target",',
        '  "version": "1.0.0",',
        '  "description": "",',
        '  "main": "index.js",',
        '  "author": "",',
        '  "license": "ISC",',
        '  "dependencies": {',
        '    "google-auto-auth": "^0.7.0"',
        '  }',
        '}',
    ])
    open('cloudfn/package.json', 'w').write(output)


@make_spin(Default, 'Cleaning up...')
def cleanup():
    p = subprocess.Popen(
        'cd cloudfn && rm -rf target && mkdir target && mv index.js target ' +
        '&& mv package.json target && mv dist target',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True)
    output = p.communicate()
    return (p, output)


def main():
    parser = argparse.ArgumentParser(
        description='Build a GCP Cloud Function in python.'
    )
    parser.add_argument('function_name', type=str,
                        help='the name of your cloud function')
    parser.add_argument('trigger_type', type=str,
                        help='the trigger type of your cloud function',
                        choices=['http', 'pubsub', 'bucket'])
    parser.add_argument('-p', '--production', action='store_true',
                        help='Build function for production environment')
    parser.add_argument('-i', '--production_image', type=str,
                        help='Docker image to use for building production environment')
    parser.add_argument('-f', '--file_name', type=str, default='main.py',
                        help='The file name of the file you wish to build')
    parser.add_argument('--python_version', type=str, default='2.7',
                        help='The python version you are targeting, '
                        'only applies when building for production',
                        choices=['2.7', '3.5'])
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Build in verbose mode '
                        'showing full build output')

    args = parser.parse_args()
    build_function(args.function_name,
                   args.file_name,
                   args.trigger_type,
                   args.python_version,
                   args.production,
                   args.production_image,
                   args.verbose,
                   )
