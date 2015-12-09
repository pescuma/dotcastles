import sys
import os
import shutil
import git


def main(argv):
    if len(argv) < 2:
        print('help')
        return

    cmd = argv[1]

    if cmd == 'add':
        if len(argv) != 3:
            raise 'Use dotfiles add <git repo>'

        command_add(argv[2])

    elif cmd == 'rem':
        if len(argv) != 3:
            raise 'Use dotfiles rem <castle>'

        command_remove(argv[2])

    elif cmd == 'sync':
        if len(argv) > 3:
            raise 'Use dotfiles sync <castle>?'

        command_sync(argv[2] if len(argv) > 2 else None)

    elif cmd == 'list':
        if len(argv) != 2:
            raise 'Use dotfiles list'

        command_list()

    else:
        print('help')


def command_list():
    for name in list_castle_names():
        castle = to_castle_path(name)
        repo = git.Repo(castle)
        print(name, '=>', repo.remotes['origin'].url)


def command_add(git_url):
    if git_url.find('.') == -1:
        git_url = 'https://github.com/' + git_url + '.git'

    name = git_url[git_url.rfind('/') + 1: git_url.rfind('.')]

    castle = to_castle_path(name)

    if os.path.exists(castle):
        print(name, 'was already cloned')
        return

    print('Cloning', git_url, '...')
    git.Repo.clone_from(git_url, castle, progress=Progress('   '))

    print('Linking files from', name, '...')
    link_files(castle, '   ')

    print('Done')


def command_remove(name):
    castle = to_castle_path(name)

    if not os.path.exists(castle):
        print(name, 'is not cloned')
        return

    repo = git.Repo(castle)
    has_changes = len(repo.untracked_files) > 0 or len(repo.head.commit.diff(None)) > 0
    if has_changes:
        yn = input(name + ' has uncommitted changes. Are you sure you want to remove it? [yn] ').strip()
        if yn != 'y':
            return

    print('Removing links from', name, '...')
    unlink_files(castle, '   ')

    print('Removing clone ...')
    if os.path.exists(castle):
        shutil.rmtree(castle, ignore_errors=True, onerror=onerror)
    if os.path.exists(castle):
        shutil.rmtree(castle, onerror=onerror)

    print('Done')


def command_sync(name):
    if name == None:
        names = list_castle_names()
    else:
        names = [name]

    for name in names:
        print('Syncing', name, '...')

        castle = to_castle_path(name)

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


def link_files(castle, prefix=''):
    path = os.path.join(castle, 'home')

    if not os.path.exists(path):
        return

    files = list_dotfiles(path)

    for file in files:
        orig = os.path.join(path, file)
        dest = os.path.join(os.path.expanduser('~'), file)

        if os.path.exists(dest):
            print(prefix + 'Skipping file', file, 'because it already exists')
            continue

        os.link(orig, dest)


def unlink_files(castle, prefix=''):
    path = os.path.join(castle, 'home')

    if not os.path.exists(path):
        return

    files = list_dotfiles(path)

    for file in files:
        orig = os.path.join(path, file)
        dest = os.path.join(os.path.expanduser('~'), file)

        if not os.path.exists(dest):
            print(prefix + 'Skipping file', file, 'because it isn\'t linked to this castle')
            continue

        if not os.path.samefile(dest, orig):
            print(prefix + 'Skipping file', file, 'because it isn\'t linked to this castle')
            continue

        os.unlink(dest)


def list_dotfiles(path):
    return [os.path.relpath(os.path.join(r, f), path) for r, ds, fs in os.walk(path) for f in fs]


def list_castle_names():
    home = os.path.join(os.path.expanduser('~'), '.homesick')
    return [f for f in os.listdir(home) if os.path.isdir(os.path.join(home, f))]


def to_castle_path(name):
    return os.path.join(os.path.expanduser('~'), '.homesick', name)


class Progress(git.RemoteProgress):
    def __init__(self, prefix=''):
        super().__init__()
        self.prefix = prefix

    def line_dropped(self, line):
        print(self.prefix + line)

    def update(self, *args):
        print(self.prefix + self._cur_line)


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
