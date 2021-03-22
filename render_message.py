import bleach
import markdown
from bleach_whitelist import markdown_tags, markdown_attrs
from collections import defaultdict
from mdx_gh_links import GithubLinks


# increment for any update that changes rendered output
RENDER_CONFIG_VERSION = '0.1.1'
__version__ = f'{RENDER_CONFIG_VERSION}/markdown={markdown.__version__}'


ok_tags = markdown_tags + ['div', 'pre']
ok_attrs = defaultdict(list, **markdown_attrs)
ok_attrs['div'].append('class')
ok_attrs['span'].append('class')


base_extensions = (
    'codehilite',
    'fenced_code',
    'footnotes',
    'mdx_linkify',
    'mdx_breakless_lists',
)


def render_github(text, user, repo):
    extras = (
        GithubLinks(user=user, repo=repo),
    )
    html = markdown.markdown(text, extensions=base_extensions + extras)
    return bleach.clean(html, ok_tags, ok_attrs)
