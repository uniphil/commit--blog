from authlib.integrations.flask_oauth2 import current_token
from flask import Blueprint, abort, request, session
from oauth import require_oauth
from wtf import csrf
from known_git_hosts import github
from models import db, Repo

api = Blueprint('api', __name__)
csrf.exempt(api)

@api.route('/blog', methods=('POST', ))
@require_oauth('blog')
def post_blog():
    if origin := request.json['origin'].get('Github'):
        repo = origin['repo']
    else:
        abort(400, 'only github ssh origin is supported for now')
    sha = request.json['commit']
    assert current_token.blogger.is_authenticated

    repo, repo_created = Repo.get_or_create(request.json['origin']['Github']['repo'])
    commit = github.get_commit_from_api(repo, sha, current_token.blogger)
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
    return {'sup': 'yo'}
