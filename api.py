from authlib.integrations.flask_oauth2 import current_token
from flask import Blueprint, abort, request, session, url_for
from oauth import require_oauth
from wtf import csrf
from known_git_hosts import github
from models import db, CommitPost, Repo

api = Blueprint('api', __name__)
csrf.exempt(api)

@api.route('/blog/<sha>', methods=('PUT', ))
@require_oauth('blog')
def post_blog(sha):
    if current_token.blogger.is_authenticated:
        blogger = current_token.blogger
    else:
        abort(500, 'sorry, could not find the account for your access token')
    if origin := request.json.get('github'):
        repo = origin['repo']
    else:
        abort(400, 'only github ssh origin is supported for now')

    repo, repo_created = Repo.get_or_create(repo)
    commit = github.get_commit_from_api(repo, sha, blogger)
    if commit is None:
        abort(400, 'commit not found on github -- perhaps you need to push first?')

    db.session.add(commit)
    if repo_created:
        db.session.add(repo)
        db.session.add(Task(task='clone', details={'full_name': repo.full_name}))
    try:
        db.session.commit()
    except IntegrityError:
        abort(400, 'seems like it\'s already blogged!')

    post_url = url_for('blog.commit_post', _external=True,
        blogger=blogger.username, repo_name=repo.full_name, hex=sha)
    return { 'post': post_url }


@api.route('/blog/<sha>', methods=('DELETE', ))
@require_oauth('blog')
def unpost_blog(sha):
    if current_token.blogger.is_authenticated:
        blogger = current_token.blogger
    else:
        abort(500, 'sorry, could not find the account for your access token')
    if gh_origin := request.json.get('github'):
        repo = gh_origin['repo']
    else:
        abort(400, 'only github ssh origin is supported for now')

    commit = CommitPost.query.filter(
        CommitPost.hex==sha, Repo.full_name==repo).first_or_404()

    if commit.blogger is not blogger:
        abort(403, 'can only unpost your own posts')

    db.session.delete(commit)
    db.session.commit()

    return '', 204
