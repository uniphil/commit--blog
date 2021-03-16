import bleach
import markdown
from bleach_whitelist import markdown_tags, markdown_attrs
from mdx_gh_links import GithubLinks


# increment for any update that changes rendered output
RENDER_CONFIG_VERSION = 0.1
__version__ = f'{RENDER_CONFIG_VERSION}/markdown={markdown.__version__}'


ok_tags = markdown_tags + ['div', 'pre']
ok_attrs = dict(markdown_attrs)
ok_attrs['div'] = ['class']
ok_attrs['span'] = ['class']


base_extensions = (
    'codehilite',
    'fenced_code',
    'footnotes',
)


def render_github(text, user, repo):
    html = markdown.markdown(
        text, extensions=base_extensions + (GithubLinks(user=user, repo=repo),))
    return bleach.clean(html, ok_tags, ok_attrs)
