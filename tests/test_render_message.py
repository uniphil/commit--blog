from render_message import render_github


def test_render_github_basic():
    out = render_github('hello', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    assert out == '<p>hello</p>'


def test_render_github_allows_some_tags():
    out = render_github('<ol><li>item one</li></ol>', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    assert out == '<ol><li>item one</li></ol>'


def test_render_github_escapes_other_tags():
    bodied = render_github('<body>breaks', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    assert bodied == '&lt;body&gt;breaks'
    xss = render_github('<script>;alert(1)</script>', 'uniphil', 'gotcha', '1337')
    assert xss == '&lt;script&gt;;alert(1)&lt;/script&gt;'


def test_render_github_tags_people():
    out = render_github('sup @rileyjshaw', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    expected = '<p>sup <a class="gh-link gh-mention" href="https://github.com/rileyjshaw" title="GitHub User: @rileyjshaw">@rileyjshaw</a></p>'
    assert out == expected


def test_render_github_links_issues():
    out = render_github('as seen in #123...', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    expected = '<p>as seen in <a class="gh-link gh-issue" href="https://github.com/uniphil/commit--blog/issues/123" title="GitHub Issue uniphil/commit--blog #123">#123</a>...</p>'
    assert out == expected


def test_render_fenced():
    out = render_github('''\
```
code in fences
```
''', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    assert '<code>' in out
    assert 'codehilite' in out
    hl = render_github('''\
```python
# ...no comment
```
''', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    assert 'class="c1"' in hl


def test_regression_render_autolink():
    out = render_github('for example: https://example.com.', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    expected = '<p>for example: <a href="https://example.com">https://example.com</a>.</p>'
    assert out == expected


def test_regression_render_lists():
    out = render_github('''\
ok:
- here is a list but
- i did not leave a blank line
- hope it will not break
''', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    expected = '''\
<p>ok:</p>
<ul>
<li>here is a list but</li>
<li>i did not leave a blank line</li>
<li>hope it will not break</li>
</ul>'''
    assert out == expected


def test_regression_render_gh_image():
    out = render_github('''\
POC: ![i am an image](static/img/dash-b.png)
''', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    expected = '''\
<p>POC: <img alt="i am an image" src="https://raw.githubusercontent.com/uniphil/commit--blog/b7caf89bfd8f67e459e8e86e684553f99533c495/static/img/dash-b.png"></p>'''
    assert out == expected

    out_abs = render_github('''\
![but abs urls don't change](https://example.com/an-image.png)
''', 'uniphil', 'commit--blog', 'b7caf89bfd8f67e459e8e86e684553f99533c495')
    expected_abs = '''\
<p><img alt="but abs urls don't change" src="https://example.com/an-image.png"></p>'''
    assert out_abs == expected_abs


def test_regression_only_proto_links():
    out = render_github('readme.md', 'uniphil', 'commit--blog', 'asdf')
    expected = '<p>readme.md</p>'
    assert out == expected


def test_regression_no_linkify_in_code():
    out = render_github('`https://example.com`', 'uniphil', 'commit--blog', 'asdf')
    expected = '<p><code>https://example.com</code></p>'
    assert out == expected


def test_regression_no_guessing():
    out = render_github('''\
```
const ANSWER = 42;
```
''', 'uniphil', 'commit--blog', 'asdf')
    expected = '<div class="codehilite"><pre><span></span><code>const ANSWER = 42;\n</code></pre></div>'
    assert out == expected
