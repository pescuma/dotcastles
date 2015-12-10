import sys
import os
import shutil
import git
import argparse


def main(argv):
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest='cmd', title='commands')

    cmd = subparsers.add_parser('list', description='list all castles and their git urls')

    cmd = subparsers.add_parser('add', description='add dotfiles from a git repository')
    cmd.add_argument('url', help='git url or, if from github, username/repository')

    cmd = subparsers.add_parser('rem', description='remove dotfiles from a git repository previously added')
    cmd.add_argument('castle', help='name of the castle')

    cmd = subparsers.add_parser('sync', description='fetch changes from remote repository and send local changes')
    cmd.add_argument('castle', nargs='?', default='', help='name of the castle (leave empty for all)')

    cmd = subparsers.add_parser('track', description='add one more file to a castle')
    cmd.add_argument('castle', help='name of the castle')
    cmd.add_argument('file', type=argparse.FileType('r'), help='file name (must be inside home folder)')

    parser.add_argument('--version', action='version', version='%(prog)s 0.1')

    if len(sys.argv) < 2:
        sys.argv.append('--help')

    args = parser.parse_args()

    if args.cmd == 'add':
        command_add(args.url)

    elif args.cmd == 'rem':
        command_remove(args.castle)

    elif args.cmd == 'sync':
        command_sync(args.castle)

    elif args.cmd == 'list':
        command_list()

    elif args.cmd == 'track':
        command_track(args.castle, args.file)


def command_list():
    names = list_castle_names()

    if not names:
        print('No castles were added')
        return

    for name in names:
        castle = get_castle_path(name)
        repo = git.Repo(castle)
        print(name, '=>', repo.remotes['origin'].url)


def command_add(git_url):
    if git_url.find('.') == -1:
        git_url = 'https://github.com/' + git_url + '.git'

    name = git_url[git_url.rfind('/') + 1: git_url.rfind('.')]

    castle = get_castle_path(name)

    if os.path.exists(castle):
        print(name, 'was already cloned')
        return

    print('Creating castle', name, '...')

    print('   Cloning', git_url, '...')
    git.Repo.clone_from(git_url, castle, progress=Progress('      '))

    print('   Linking files from', name, '...')
    link_files(castle, '      ')

    print('Done')


def command_remove(name):
    castle = get_castle_path(name)

    if not os.path.exists(castle):
        print('Castle', name, 'does not exist')
        return

    if os.path.exists(os.path.join(castle, '.git')):
        repo = git.Repo(castle)
        has_changes = len(repo.untracked_files) > 0 or len(repo.head.commit.diff(None)) > 0
        if has_changes:
            print(name + ' has uncommitted changes:')
            print_changes(repo, '   ')
            yn = input('Are you sure you want to remove it? [yN] ').strip()
            if yn.lower() != 'y':
                return

    yn = input('Do you want to keep the dotfiles in your home folder? [yN] ').strip()
    if yn.lower() != 'y':
        print('Removing links from', name, '...')
        unlink_files(castle, '   ')

    print('Removing clone ...')
    if os.path.exists(castle):
        shutil.rmtree(castle, onerror=onerror)

    print('Done')


def command_sync(name):
    if not name:
        names = list_castle_names()
    else:
        names = [name]

    if not names:
        print('No castles were added')
        return

    for name in names:
        print('Syncing', name, '...')

        castle = get_castle_path(name)

        if not os.path.exists(castle):
            print('Castle', name, 'does not exist')
            continue

        repo = git.Repo(castle)

        print('   Removing links ...')
        unlink_files(castle, '      ')

        has_changes = len(repo.untracked_files) > 0 or len(repo.head.commit.diff(None)) > 0
        if has_changes:
            print('   Stashing changes ...')
            repo.git.stash('save', '-u')

        print('   Pulling ...')
        repo.remotes['origin'].pull(progress=Progress('      '))

        if has_changes:
            print('   Popping stash changes ...')
            repo.git.stash('pop')

            print('   Changes:')
            print_changes(repo, '      ')
            message = input('   Commit message (leave empty to skip): ').strip()

            if len(message) > 0:
                print('   Adding files ...')
                repo.git.add(u=True)

                print('   Committing ...')
                repo.git.commit(m=message)

                print('   Pushing ...')
                repo.remotes['origin'].push(progress=Progress('      '))

        print('   Linking files ...')
        link_files(castle, '      ')

    print('Done')


def command_track(name, file):
    castle = get_castle_path(name)

    if not os.path.exists(castle):
        print('Castle', name, 'does not exist')
        return

    file = os.path.realpath(file)

    if not os.path.exists(file):
        print(file, 'does not exist')
        return

    if not os.path.isfile(file):
        print(file, 'have to be a file')
        return

    home = get_home_path()
    work = get_work_path()

    if not is_inside(file, home):
        print(file, 'have to be inside home folder')
        return

    if is_inside(file, work):
        print(file, 'can not be inside work folder (', work, ')')
        return

    rel = os.path.relpath(file, home)

    orig = os.path.join(home, file)
    dest = os.path.join(castle, 'home', rel)

    if os.path.exists(dest):
        print('The file', rel, 'already exists inside', name)
        return

    link_file(orig, dest)
    print('Done')


def is_inside(file, path):
    if not file.startswith(path):
        return False

    return not os.path.relpath(file, path).startswith(os.pardir)


def link_files(castle, prefix=''):
    path = os.path.join(castle, 'home')

    if not os.path.exists(path):
        return

    files = list_all_files(path)
    home = get_home_path()

    for file in files:
        orig = os.path.join(path, file)
        dest = os.path.join(home, file)

        if os.path.exists(dest):
            print(prefix + 'Skipping file', file, 'because it already exists')
            continue

        link_file(orig, dest)


def link_file(orig, dest):
    dest_dir = os.path.dirname(dest)
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    os.link(orig, dest)


def unlink_files(castle, prefix=''):
    path = os.path.join(castle, 'home')

    if not os.path.exists(path):
        return

    files = list_all_files(path)
    home = get_home_path()

    for file in files:
        orig = os.path.join(path, file)
        dest = os.path.join(home, file)

        if not os.path.exists(dest):
            print(prefix + 'Skipping file', file, 'because it is not linked to this castle')
            continue

        if not os.path.samefile(dest, orig):
            print(prefix + 'Skipping file', file, 'because it is not linked to this castle')
            continue

        os.unlink(dest)


def list_all_files(path):
    return [os.path.relpath(os.path.join(r, f), path) for r, ds, fs in os.walk(path) for f in fs]


def list_castle_names():
    work = get_work_path()
    return [f for f in os.listdir(work) if os.path.isdir(os.path.join(work, f))]


def get_home_path():
    return os.path.expanduser('~')


def get_work_path():
    return os.path.join(get_home_path(), '.dotfiles')


def get_castle_path(name):
    return os.path.join(get_work_path(), name)


def print_changes(repo, prefix):
    for f in repo.untracked_files:
        print(prefix + 'added', f)

    for d in repo.head.commit.diff(None):
        print(prefix + 'modified', d.b_path)


class Progress(git.RemoteProgress):
    def __init__(self, prefix=''):
        super().__init__()
        self.prefix = prefix

    def line_dropped(self, line):
        print(self.prefix + line)

    def update(self, *args):
        print(self.prefix + self._cur_line)


# http://stackoverflow.com/a/2656405
def onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


if __name__ == '__main__':
    main(sys.argv)
