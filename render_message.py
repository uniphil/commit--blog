import bleach
import markdown
from bleach_allowlist import markdown_tags
from collections import defaultdict
from functools import partial
from markdown.extensions import Extension, codehilite
from markdown.treeprocessors import Treeprocessor
from mdx_gh_links import GithubLinks


# increment for any update that changes rendered output
RENDER_CONFIG_VERSION = '0.2.2'
__version__ = f'{RENDER_CONFIG_VERSION}/markdown={markdown.__version__}'

LINK_PREFIXES = ('www.', 'http://', 'https://', 'mailto:')


base_extensions = (
    codehilite.CodeHiliteExtension(guess_lang=False),
    'fenced_code',
    'footnotes',
    'mdx_breakless_lists',
)

allowed_attrs = {
    '*': ['id', 'class'],
    'img': ['src', 'alt', 'title'],
    'a': ['href', 'alt', 'title'],
}


class GHImageProcessor(Treeprocessor):
    GH_IMG_ROOT = 'https://raw.githubusercontent.com'

    def __init__(self, config, md):
        super().__init__(md)
        self.config = config

    def run(self, root):
        user = self.config['user']
        repo = self.config['repo']
        sha = self.config['sha']
        for el in root.iter('img'):
            src = el.attrib['src']
            if src.startswith('http://') or src.startswith('https://'):
                continue  # leave absolute image urls alone
            el.set('src', f'{self.GH_IMG_ROOT}/{user}/{repo}/{sha}/{src}')


class GithubLinksAlsoImages(GithubLinks):
    def __init__(self, *args, **kwargs):
        self.config = {
            'user': ['', 'GitHub user or organization.'],
            'repo': ['', 'Repository name.'],
            'sha': ['', 'Sha-1 hash of commit.'],
        }
        Extension.__init__(self, *args, **kwargs)

    def extendMarkdown(self, md):
        super().extendMarkdown(md)
        md.treeprocessors.register(
            GHImageProcessor(self.getConfigs(), md), 'gh_image', 20)


def only_abs_link(attrs, new=False):
    if new is False or \
       any(attrs['_text'].startswith(p) for p in LINK_PREFIXES):
        return attrs


def render_github(text, user, repo, sha):
    extras = (GithubLinksAlsoImages(user=user, repo=repo, sha=sha),)
    html = markdown.markdown(text, extensions=base_extensions + extras)
    safe = bleach.clean(html, markdown_tags, allowed_attrs)
    return bleach.linkify(safe, callbacks=[only_abs_link], skip_tags=['code'])
