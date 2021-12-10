from authlib.integrations.flask_oauth2 import current_token
from flask import Blueprint, abort, request, session, url_for
from sqlalchemy.exc import IntegrityError
from oauth import require_oauth
from known_git_hosts import github
from models import db, CommitPost, Repo, Task

api = Blueprint('api', __name__)

@api.route('/blog/<sha>', methods=('PUT', ))
@require_oauth('blog')
def post_blog(sha):
    if current_token.blogger.is_authenticated:
        blogger = current_token.blogger
    else:
        return 'sorry, could not find the account for your access token', 500
    if origin := request.json.get('github'):
        repo = origin['repo']
    else:
        return 'only github ssh origin is supported for now', 500

    repo, repo_created = Repo.get_or_create(repo)
    commit = github.get_commit_from_api(repo, sha, blogger)
    if commit is None:
        return 'commit not found on github -- perhaps you need to push first?', 400

    db.session.add(commit)
    if repo_created:
        db.session.add(repo)
        db.session.add(Task(
            task='clone',
            details={'full_name': repo.full_name},
            creator=blogger))
    try:
        db.session.commit()
    except IntegrityError:
        return 'seems like it\'s already blogged!', 400

    post_url = url_for('blog.commit_post', _external=True,
        blogger=blogger.username, repo_name=repo.full_name, hex=sha)
    return { 'post': post_url }


@api.route('/blog/<sha>', methods=('DELETE', ))
@require_oauth('blog')
def unpost_blog(sha):
    if current_token.blogger.is_authenticated:
        blogger = current_token.blogger
    else:
        return 'sorry, could not find the account for your access token', 500
    if gh_origin := request.json.get('github'):
        repo = gh_origin['repo']
    else:
        return 'only github ssh origin is supported for now', 400

    commit = CommitPost.query.filter(
        CommitPost.hex==sha, Repo.full_name==repo).first()
    if commit is None:
        return 'could not find that post -- maybe it\'s already deleted?', 404

    if commit.blogger is not blogger:
        return 'can only unpost your own posts', 403

    db.session.delete(commit)
    db.session.commit()

    return '', 204
