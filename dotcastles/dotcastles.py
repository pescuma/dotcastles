import gc
import sys
import os
import shutil
import git
import argparse


def main():
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

    parser.add_argument('--version', action='version', version='%(prog)s 0.1.6')

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
        command_track(args.castle, args.file.name)


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
    if not git_url.startswith('http'):
        git_url = 'https://github.com/' + git_url + '.git'

    elif git_url.startswith('https://github.com/') and not git_url.endswith('.git'):
        git_url = git_url + '.git'

    name = git_url[git_url.rfind('/') + 1: git_url.rfind('.')]

    if name.isspace():
        print('Could not guess repository name')
        return

    castle = get_castle_path(name)

    if os.path.exists(castle):
        print(name, 'was already cloned')
        return

    print('Creating castle', name, '...')

    print('   Cloning', git_url, '...')
    progress = Progress('      ')
    git.Repo.clone_from(git_url, castle, progress=progress)
    progress.finish()

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
            yn = query_yes_no('Are you sure you want to remove it?', 'no')
            if not yn:
                return

    yn = query_yes_no('Do you want to keep the dotfiles in your home folder?', 'no')
    if not yn:
        print('Removing links from', name, '...')
        unlink_files(castle, '   ')

    print('Removing clone ...')
    if os.path.exists(castle):
        gc.collect()
        repo.git.clear_cache()
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
        progress = Progress('      ')
        repo.remotes['origin'].pull(progress=progress)
        progress.finish()

        if has_changes:
            print('   Popping stash changes ...')
            repo.git.stash('pop')

            print('   Changes:')
            print_changes(repo, '      ')
            message = input('   Commit message (leave empty to skip): ').strip()

            if len(message) > 0:
                print('   Committing ...')
                repo.git.add(A=True)
                repo.index.commit(message)

                print('   Pushing ...')
                progress = Progress('      ')
                repo.remotes['origin'].push(progress=progress)
                progress.finish()

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
    relative = os.path.relpath(os.path.realpath(file),
                               os.path.realpath(path))
    return not (relative == os.pardir
                or relative.startswith(os.pardir + os.sep))


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
            overwrite = query_yes_no(prefix + 'File ' + dest + ' already exists. Overwrite?', 'no')
            if overwrite:
                os.remove(dest)
            else:
                print(prefix + '   Skipping file ', dest)
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

    folders = list_all_sub_folders(path)
    folders.sort(key=lambda s: -len(s))

    for folder in folders:
        dest = os.path.join(home, folder)

        if not os.path.isdir(dest) or os.listdir(dest):
            continue

        os.rmdir(dest)


def list_all_files(path):
    return [os.path.relpath(os.path.join(r, f), path) for r, ds, fs in os.walk(path) for f in fs]


def list_all_sub_folders(path):
    return [os.path.relpath(os.path.join(r, d), path) for r, ds, fs in os.walk(path) for d in ds]


def list_castle_names():
    work = get_work_path()
    return [f for f in os.listdir(work) if os.path.isdir(os.path.join(work, f))]


def get_home_path():
    return os.path.expanduser('~')


def get_work_path():
    return os.path.join(get_home_path(), '.dotcastles')


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
        self.cols = shutil.get_terminal_size().columns

    def print(self, line):
        text = self.prefix + line
        if len(text) > self.cols - 1:
            text = text[0: self.cols - 4] + '...'
        text = text.ljust(self.cols - 1)
        print(text, end='\r')

    def line_dropped(self, line):
        self.print(line)

    def update(self, op_code, cur_count, max_count=None, message=''):
        self.print(self._cur_line)

    def finish(self):
        self.print('')


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


# https://stackoverflow.com/a/3041990
def query_yes_no(question, default="yes"):
    """Ask a yes/no question via input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


if __name__ == '__main__':
    main()
