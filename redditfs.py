import fuse
import errno
import stat
import time
import sys
import urlparse
import collections
import requests
import os.path
from fsfile import *


class RedditFS(fuse.Operations):
	PERMS = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
	DIR_PERMS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

	def __init__(self, subreddit):
		self.subreddit = subreddit
		self.fd = 0

		self.fs = FSDirectory('/', RedditFS.PERMS | RedditFS.DIR_PERMS, time.time())
		self._populate_fs()

	@property
	def dirlist(self):
		if not self._dirlist:
			self._dirlist = self._populate_dirlist()
		return self._dirlist

	def open(self, path, flags):
		self.fd += 1
		return self.fd

	def getattr(self, path, fh=None):
		f = self._traverse(path)

		if f is None:
			raise fuse.FuseOSError(errno.ENOENT)

		return f.getattr()

	def read(self, path, size, offset, fh):
		f = self._traverse(path)
		if f is None:
			raise fuse.FuseOSError(errno.ENOENT)
		if f.dir():
			raise fuse.FuseOSError(errno.EISDIR)

		return f.read(size, offset)

	def readdir(self, path, fh):
		f = self._traverse(path)
		if f is None:
			raise fuse.FuseOSError(errno.ENOENT)
		if not f.dir():
			raise fuse.FuseOSError(errno.ENOTDIR)

		return f.readdir()

	def _traverse(self, path):
		path = path.strip('/')

		if path == '':
			return self.fs

		obj = self.fs
		for fn in path.split('/'):
			if not obj.dir():
				return None
			if not obj.get_child(fn):
				return None

			obj = obj.get_child(fn)

		return obj

	def _populate_fs(self):
		# TODO Some sort of cache invalidation
		r = requests.get('http://api.reddit.com/r/{}/hot'.format(self.subreddit))
		r.raise_for_status()

		links = [link['data'] for link in r.json()['data']['children']]
		for zelda in links:
			self._add_reddit_link_to_fs(zelda)

	def _add_reddit_link_to_fs(self, zelda):
		title    = zelda['title']
		filename = self._sanitize_path(title)

		permalink = urlparse.urljoin(
			'http://www.reddit.com/',
			zelda['permalink']
		)
		url = zelda['url']
		selftext = zelda['selftext']

		root_file = FSDirectory(
			filename=filename,
			mode=RedditFS.PERMS | RedditFS.DIR_PERMS,
			ctime=zelda['created_utc'],
		)

		permalink_file = FSFile(
			filename='permalink',
			mode=RedditFS.PERMS,
			content=permalink,
			ctime=zelda['created_utc'],
		)

		url_file = FSFile(
			filename='url',
			mode=RedditFS.PERMS,
			content=url,
			ctime=zelda['created_utc'],
		)

		selftext_file = FSFile(
			filename='selftext',
			mode=RedditFS.PERMS,
			content=selftext,
			ctime=zelda['created_utc'],
		)

		for f in (permalink_file, url_file, selftext_file):
			root_file.add_child(f)
		self.fs.add_child(root_file)

	def _sanitize_path(self, path):
		replace = (
			('/', ''),
			(' ', '_'),
			("'", ''),
			('"', ''),
			('.', ''),
			('', ''),
		)
		for r in replace:
			path = path.replace(*r)
		return path


def main():
	fuse.FUSE(RedditFS(sys.argv[2]), sys.argv[1], foreground=True)


if __name__ == '__main__':
	main()