import bleach
import markdown
from bleach_whitelist import markdown_tags, markdown_attrs
from mdx_gh_links import GithubLinks


# increment for any update that changes rendered output
RENDER_CONFIG_VERSION = 0.1
__version__ = f'{RENDER_CONFIG_VERSION}/markdown={markdown.__version__}'


def render_github(text, user, repo):
    html = markdown.markdown(
        text, extensions=[GithubLinks(user=user, repo=repo)])
    return bleach.clean(html, markdown_tags, markdown_attrs)
