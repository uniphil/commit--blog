from render_message import render_github


def test_render_github_basic():
    out = render_github('hello', 'uniphil', 'commit--blog')
    assert out == '<p>hello</p>'


def test_render_github_allows_some_tags():
    out = render_github('<ol><li>item one</li></ol>', 'uniphil', 'commit--blog')
    assert out == '<ol><li>item one</li></ol>'


def test_render_github_escapes_other_tags():
    bodied = render_github('<body>breaks', 'uniphil', 'commit--blog')
    assert bodied == '&lt;body&gt;breaks'
    xss = render_github('<script>;alert(1)</script>', 'uniphil', 'gotcha')
    assert xss == '&lt;script&gt;;alert(1)&lt;/script&gt;'


def test_render_github_tags_people():
    out = render_github('sup @rileyjshaw', 'uniphil', 'commit--blog')
    expected = '<p>sup <a href="https://github.com/rileyjshaw" title="GitHub User: @rileyjshaw">@rileyjshaw</a></p>'
    assert out == expected


def test_render_github_links_issues():
    out = render_github('as seen in #123...', 'uniphil', 'commit--blog')
    expected = '<p>as seen in <a href="https://github.com/uniphil/commit--blog/issues/123" title="GitHub Issue uniphil/commit--blog #123">#123</a>...</p>'
    assert out == expected


def test_render_fenced():
    out = render_github('''\
```
code in fences
```
''', 'uniphil', 'commit--blog')
    assert '<code>' in out
    assert 'codehilite' in out
    hl = render_github('''\
```python
# ...no comment
```
''', 'uniphil', 'commit--blog')
    assert 'class="c1"' in hl
