from feedwerk.atom import AtomFeed
from flask import Blueprint, abort, render_template, request, url_for
from models import Blogger, CommitPost, Repo


blog = Blueprint('blog', __name__)


@blog.route('/')
def list(blogger):
    blog_author = Blogger.from_subdomain(blogger) or abort(404)
    posts = CommitPost.query \
                .filter_by(blogger=blog_author) \
                .order_by(CommitPost.datetime.desc())
    return render_template('blog-list.html', posts=posts, blogger=blog_author)


@blog.route('/feed')
def feed(blogger):
    blog_author = Blogger.from_subdomain(blogger) or abort(404)
    posts = CommitPost.query \
                .filter_by(blogger=blog_author) \
                .order_by(CommitPost.datetime.desc())
    feed = AtomFeed('$ commits-by ' + (blog_author.name or blog_author.username),
                    feed_url=request.url, url=request.url_root)
    for post in posts:
        new_renderer = request.args.get('rr') == '1'
        feed.add(
            post.get_title(),
            post.get_body(markdown=True, new_renderer=new_renderer),
            content_type='html',
            author=blog_author.name or blog_author.username,
            url=url_for('blog.commit_post', _external=True,
                        blogger=blog_author.username,
                        repo_name=post.repo.full_name,
                        hex=post.hex),
            updated=post.datetime,
            published=post.datetime,
        )
    return feed.get_response()


@blog.route('/<path:repo_name>/<hex>')
def commit_post(blogger, repo_name, hex):
    blog_author = Blogger.from_subdomain(blogger) or abort(404)
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    post = CommitPost.query \
                .filter_by(blogger=blog_author, repo=repo, hex=hex) \
                .first() or abort(404)
    return render_template('blog-post.html', post=post, blogger=blog_author)
