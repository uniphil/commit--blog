# commit --blog

Commit messages hold rich histories. They [document lines of code](https://mislav.net/2014/02/hidden-documentation/), express frustrations and victories, and record research, debates, and social context. If [code is more often read than written](https://devblogs.microsoft.com/oldnewthing/20070406-00/?p=27343), maybe its commit message annotations aren't read enough?

**commit --blog** is an experiment. It takes the writing we already do as programmers, and lifts it from the obscure depths of the terminal. Why must developer blogs live in a separate place from the content they’re about? And why can’t commit messages be as deep and context-filled as blog posts? Whether your goal is to share your writing with the world, or just to have a quiet feed of past commits to reflect on at the end of a project, **commit --blog** gets you started with the commits you’re already writing.

## Creating a commit --blog

If you use Git, you’ve already begun! To create a public **commit --blog** of your own, you don’t need to dive deeper into this repo. Go to https://commit--blog.com, follow the instructions there to create an account, and start picking some of your favourite commits to publish.

### Example blogs

To see what a **commit --blog** can look like, check out some active blogs:

- https://uniphil.commit--blog.com
- https://rileyjshaw.commit--blog.com
- Add your own by [submitting a pull request](https://github.com/uniphil/commit--blog/edit/master/readme.md)!

## Contributing

We’re still working on this part of the README. For now, you can [check out the project’s active issues](https://github.com/uniphil/commit--blog/issues).

### Local setup

1. Clone this repo
2. Pip install `dev-requirements.txt` (hopefully in a virtualenv)
3. Edit your OS `hosts` file (at `/etc/hosts`). I know, this sucks.
4. Register an application at GitHub
5. Set the redirect urls to your localhost setup
6. Set up environment variables (virtualenvwrapper's postactivate hook is sweet)

## License

…coming soon?
