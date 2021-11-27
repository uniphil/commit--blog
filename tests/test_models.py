import pytest
from models import Blogger, db


def test_blogger_model(app_ctx):
    bloggers = Blogger.query.all()
    assert len(bloggers) == 0
    jim = Blogger(username='jim')
    db.session.add(jim)
    db.session.commit()
    jim_id = jim.id

    jim_sd = Blogger.from_subdomain('jim')
    assert jim_id == jim_sd.id

    assert Blogger.from_subdomain('abc') is None


def test_db_did_reset(app_ctx):
    bloggers = Blogger.query.all()
    assert len(bloggers) == 0
